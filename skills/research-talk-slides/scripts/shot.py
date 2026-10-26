#!/usr/bin/env python3
"""Screenshot every reveal step of a kit deck in headless Chromium (Playwright).

Usage:
    shot.py DECK.html PREFIX [N]          entry shot + N ArrowRight advances (default 8)
Options:
    --size WxH        viewport, default 1280x720 (use 1024x768 for the off-aspect check)
    --start K         jump to slide K (1-based) before the entry shot
    --click SELECTOR  after the advances: click SELECTOR, then screenshot (repeatable;
                      e.g. '[data-goto=attn]' then '#back' to verify a drill-down)
    --then ACTION     after the advances: one action + screenshot (repeatable, kept in
                      order together with --click). ACTION is one of
                        right | left | right*K | left*K | click:SELECTOR | key:KEY | slide:K
    --check           also assert (a) SVG <path d> are identical across the shots of one
                      slide (arrows never move) and (b) no visible element of the active
                      slide extends below canvas y=620 (bottom logo band)
    --wait MS         wait after each action, default 550
    --step-timeout S  give up when one load/action/screenshot makes no progress for S
                      seconds (default 30; a slide script stuck in a loop freezes the page);
                      prints the shots taken so far plus "hang" and "stuck_at", exit 1

Writes PREFIX_00_entry.png, PREFIX_01.png, ...  Prints JSON:
    {"shots":[{"png","slide","step","action"}], "real_errors":[...], "check":{...}}
and "REAL ERRORS: NONE" (or the list) on stderr. Font/network failures (offline
web fonts) are filtered out. Exit codes: 0 pass, 1 real errors, failed check or a
hang (--step-timeout), 2 Playwright missing.
"""
import argparse
import json
import os
import pathlib
import sys
import threading
import time

INSTALL_HINT = 'pip install playwright && python -m playwright install chromium'

STATE_JS = """() => {
  const sl=[...document.querySelectorAll('#stage .slide')];
  const i=sl.findIndex(s=>s.classList.contains('active'));
  return {slide:i+1, step:i<0?0:(sl[i]._p||0)};
}"""

CHECK_JS = """() => {
  const s=document.querySelector('#stage .slide.active'); if(!s) return {paths:[],low:[]};
  const sr=s.getBoundingClientRect(), k=720/sr.height;
  const paths=[...s.querySelectorAll('svg path')].map(p=>p.getAttribute('d')||'');
  function op(el){ let o=1; for(let e=el;e&&e!==document.body;e=e.parentElement){
      const cs=getComputedStyle(e); if(cs.display==='none'||cs.visibility==='hidden') return 0;
      o*=parseFloat(cs.opacity);} return o; }
  const low=[];
  s.querySelectorAll('*').forEach(el=>{
    if(el.children.length||el.closest('.notes-src')) return;
    if(['STYLE','SCRIPT','defs','marker','DEFS'].includes(el.tagName)||el.closest('defs')) return;
    const r=el.getBoundingClientRect(); if(r.width<1||r.height<1) return;
    const b=(r.bottom-sr.top)*k; if(b>621 && op(el)>0.05)
      low.push({tag:el.tagName.toLowerCase(), cls:(el.getAttribute('class')||''), bottom:Math.round(b),
                text:(el.textContent||'').trim().slice(0,30)});
  });
  return {paths, low};
}"""


def parse_actions(argv_actions):
    out = []
    for kind, val in argv_actions:
        if kind == 'click':
            out.append(('click', val))
            continue
        v = val.strip()
        if v.startswith('click:'):
            out.append(('click', v[6:]))
        elif v.startswith('key:'):
            out.append(('key', v[4:]))
        elif v.startswith('slide:'):
            out.append(('slide', int(v[6:])))
        elif v.split('*')[0] in ('right', 'left'):
            name, _, n = v.partition('*')
            out.append((name, int(n or 1)))
        else:
            raise SystemExit(json.dumps({'error': 'unknown --then action: %s' % v}))
    return out


class Collect(argparse.Action):
    def __call__(self, parser, ns, values, option_string=None):
        seq = getattr(ns, 'actions', None) or []
        seq.append(('click' if option_string == '--click' else 'then', values))
        ns.actions = seq


def kill_descendants(pid):
    """SIGKILL every process below pid (driver, Chromium, renderers); pgrep is on Linux and macOS."""
    import signal
    import subprocess
    try:
        kids = subprocess.run(['pgrep', '-P', str(pid)], capture_output=True, text=True).stdout.split()
    except OSError:
        return
    for k in kids:
        kill_descendants(int(k))
        try:
            os.kill(int(k), signal.SIGKILL)
        except OSError:
            pass


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog='Actions for --then: right | left | right*K | left*K | '
                                        'click:SELECTOR | key:KEY | slide:K')
    ap.add_argument('html')
    ap.add_argument('prefix')
    ap.add_argument('advances', nargs='?', type=int, default=8)
    ap.add_argument('--size', default='1280x720')
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--click', action=Collect, dest='actions', metavar='SELECTOR')
    ap.add_argument('--then', action=Collect, dest='actions', metavar='ACTION')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--wait', type=int, default=550)
    ap.add_argument('--step-timeout', type=float, default=30)
    a = ap.parse_args()
    actions = parse_actions(a.actions or [])

    try:
        w, h = (int(x) for x in a.size.lower().split('x'))
    except ValueError:
        raise SystemExit(json.dumps({'error': '--size must be WxH, e.g. 1024x768'}))

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(json.dumps({'error': 'playwright not installed', 'install': INSTALL_HINT}))
        sys.exit(2)

    url = pathlib.Path(a.html).resolve().as_uri()
    pathlib.Path(a.prefix).parent.mkdir(parents=True, exist_ok=True)
    shots, errs, per_slide_paths, low_hits = [], [], {}, []

    # Watchdog: a slide script stuck in a loop blocks every Playwright call forever, so a
    # thread checks that each stage (load, action, screenshot) finishes in --step-timeout.
    progress = {'t': time.monotonic(), 'stage': 'load'}

    def tick(stage):
        progress['t'], progress['stage'] = time.monotonic(), stage

    def watchdog():
        while True:
            time.sleep(0.5)
            if time.monotonic() - progress['t'] > a.step_timeout:
                print(json.dumps({'shots': shots, 'real_errors': errs, 'size': '%dx%d' % (w, h),
                                  'hang': True, 'stuck_at': progress['stage'],
                                  'step_timeout_s': a.step_timeout}, indent=1), flush=True)
                print('HANG: no progress for %gs at %s (a slide script may loop forever)'
                      % (a.step_timeout, progress['stage']), file=sys.stderr, flush=True)
                kill_descendants(os.getpid())   # the looping renderer outlives the driver otherwise
                os._exit(1)

    threading.Thread(target=watchdog, daemon=True).start()

    with sync_playwright() as p:
        b = p.chromium.launch(args=['--no-sandbox', '--disable-gpu'])
        pg = b.new_page(viewport={'width': w, 'height': h})
        pg.on('console', lambda m: errs.append(m.type + ':' + m.text) if m.type == 'error' else None)
        pg.on('pageerror', lambda e: errs.append('PAGEERR:' + str(e)))
        pg.goto(url)
        pg.wait_for_timeout(700)
        if a.start > 1:
            pg.evaluate('k => go(k-1, false)', a.start)
            pg.wait_for_timeout(a.wait + 200)

        def snap(name, action):
            png = '%s_%s.png' % (a.prefix, name)
            tick('screenshot %s (after %s)' % (name, action))
            pg.screenshot(path=png)
            st = pg.evaluate(STATE_JS)
            rec = {'png': png, 'slide': st['slide'], 'step': st['step'], 'action': action}
            if a.check:
                c = pg.evaluate(CHECK_JS)
                prev = per_slide_paths.get(st['slide'])
                if prev is not None and c['paths'] and prev != c['paths']:
                    rec['arrows_moved'] = True
                if c['paths']:
                    per_slide_paths[st['slide']] = c['paths']
                if c['low']:
                    rec['below_safe_area'] = c['low'][:5]
                    low_hits.append(png)
            shots.append(rec)

        snap('00_entry', 'entry')
        n = 0
        for _ in range(a.advances):
            n += 1
            tick('advance %d (ArrowRight)' % n)
            pg.keyboard.press('ArrowRight')
            pg.wait_for_timeout(a.wait)
            snap('%02d' % n, 'right')
        for kind, val in actions:
            n += 1
            tick('action %d (%s:%s)' % (n, kind, val))
            if kind == 'click':
                pg.click(val)
            elif kind == 'key':
                pg.keyboard.press(val)
            elif kind == 'slide':
                pg.evaluate('k => go(k-1, false)', val)
            else:
                for _ in range(val):
                    pg.keyboard.press('ArrowRight' if kind == 'right' else 'ArrowLeft')
                    pg.wait_for_timeout(120)
            pg.wait_for_timeout(a.wait)
            snap('%02d' % n, '%s:%s' % (kind, val))
        tick('closing browser')
        b.close()

    # web fonts fail offline -> system fallback; not a slide error
    real = [e for e in errs if 'net::' not in e and 'ERR_' not in e and 'fonts.g' not in e]
    moved = [s['png'] for s in shots if s.get('arrows_moved')]
    result = {'shots': shots, 'real_errors': real, 'size': '%dx%d' % (w, h)}
    if a.check:
        result['check'] = {'arrows_moved': moved, 'below_safe_area': low_hits,
                           'pass': not moved and not low_hits}
    print(json.dumps(result, indent=1))
    print('REAL ERRORS:', real or 'NONE', file=sys.stderr)
    ok = not real and (not a.check or result['check']['pass'])
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
