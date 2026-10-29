#!/usr/bin/env python3
"""Screenshot every reveal step of a kit deck in headless Chromium (Playwright).

Usage:
    shot.py DECK.html PREFIX [N]          entry shot + N ArrowRight advances (default 8)
Options:
    --all             advance until the last step of the last slide instead of N (no count
                      to guess); stops early if an advance changes nothing
    --size WxH        viewport, default 1280x720 (use 1024x768 for the off-aspect check)
    --start K         jump to slide K (1-based) before the entry shot
    --click SELECTOR  after the advances: click SELECTOR, then screenshot (repeatable;
                      e.g. '[data-goto=attn]' then '#back' to verify a drill-down)
    --then ACTION     after the advances: one action + screenshot (repeatable, kept in
                      order together with --click). ACTION is one of
                        right | left | right*K | left*K | click:SELECTOR | key:KEY | slide:K
    --check           also assert (a) SVG <path d> are identical across the shots of one
                      slide (arrows and spotlight rings never move), (b) no visible
                      element of the active slide extends below canvas y=620 (bottom logo
                      band; the spotlight veil is exempt, its ring/leader/caption are not)
                      and (c) box fit: no visible HTML text runs outside the nearest box
                      that frames it (border, background or clipped overflow) by > 1.5
                      canvas px. Then replays the same sequence at each --check-size
                      (default 1906x1000, a desktop Chrome window) with (a)-(c), saving a
                      PNG there only for a failing shot (PREFIX_NN@WxH.png).
                      Also warns (does not fail) on visible text rendered below 12 px.
    --check-size WxH  extra --check size (repeatable); "none" for no extra pass
    --wait MS         wait after each action, default 1200 (kit fades take 0.5 s, spotlight
                      layout 0.4 s; use 1700 on slides with their own animations)
    --step-timeout S  give up when one load/action/screenshot makes no progress for S
                      seconds (default 30; a slide script stuck in a loop freezes the page);
                      prints the shots taken so far plus "hang" and "stuck_at", exit 1
    --json FILE       write the JSON result to FILE instead of stdout (stdout stays empty;
                      a one-line summary goes to stderr)

Writes PREFIX_00_entry.png, PREFIX_01.png, ...  Prints JSON:
    {"shots":[{"png","slide","step","action"[,"spot"]}], "real_errors":[...], "check":{...}}
"spot" appears only on slides with spotlight markers: the lit targets' data-spot
selectors (" @x,y,w,h" appended for a sub-rect, " [no ring]" for a data-ring="none"
hole); [] when none is lit.
Diagnostics ("REAL ERRORS: NONE" or the list, warnings) go to stderr. Font/network
failures (offline web fonts) are filtered out. Exit codes: 0 pass, 1 real errors,
failed check or a hang (--step-timeout), 2 Playwright missing.
"""
import argparse
import json
import os
import pathlib
import sys
import threading
import time

INSTALL_HINT = 'pip install playwright && python -m playwright install chromium'
EXTRA_SIZE = '1906x1000'
MIN_TEXT_PX = 12
MAX_ADVANCES = 5000          # --all safety cap
LAUNCH_S = 60                # watchdog limit for the browser launch

STATE_JS = """() => {
  const sl=[...document.querySelectorAll('#stage .slide')];
  const i=sl.findIndex(s=>s.classList.contains('active'));
  const sp=i<0?null:sl[i].querySelector('.spot-layer');   /* only on slides with spotlight markers */
  const veil=sp&&sp.querySelector('.spot-g.on .spot-veil');           /* the lit bucket's veil */
  const mask=veil&&document.getElementById(veil.getAttribute('mask').slice(5,-1));
  return {slide:i+1, step:i<0?0:(sl[i]._p||0),
          spot:sp?(mask?[...mask.querySelectorAll('path[data-for]')].map(h=>h.getAttribute('data-for')
                +(h.getAttribute('data-ring')==='none'?' [no ring]':'')):[]):null};
}"""

# true on the last slide once all of its reveal buckets are shown (same grouping as the kit)
END_JS = """() => {
  const sl=[...document.querySelectorAll('#stage .slide')];
  const i=sl.findIndex(s=>s.classList.contains('active')); if(i!==sl.length-1) return false;
  const keys=new Set(); let n=0;
  sl[i].querySelectorAll('.step').forEach(e=>{ const k=e.dataset.step;
    if(k===undefined) n++; else if(!keys.has(k)){ keys.add(k); n++; } });
  return (sl[i]._p||0)>=n;
}"""

CHECK_JS = """([minPx]) => {
  const s=document.querySelector('#stage .slide.active'); if(!s) return {paths:[],low:[],overflow:[],small:[]};
  const sr=s.getBoundingClientRect(), k=720/sr.height;
  const paths=[...s.querySelectorAll('svg path')].map(p=>p.getAttribute('d')||'');
  function op(el){ let o=1; for(let e=el;e&&e!==document.body;e=e.parentElement){
      const cs=getComputedStyle(e); if(cs.display==='none'||cs.visibility==='hidden') return 0;
      o*=parseFloat(cs.opacity);} return o; }
  const low=[];
  s.querySelectorAll('*').forEach(el=>{
    if(el.children.length||el.closest('.notes-src,.spot-veil')) return;   /* the veil covers the canvas by design */
    if(['STYLE','SCRIPT','defs','marker','DEFS'].includes(el.tagName)||el.closest('defs')) return;
    const r=el.getBoundingClientRect(); if(r.width<1||r.height<1) return;
    const b=(r.bottom-sr.top)*k; if(b>621 && op(el)>0.05)
      low.push({tag:el.tagName.toLowerCase(), cls:(el.getAttribute('class')||''), bottom:Math.round(b),
                text:(el.textContent||'').trim().slice(0,30)});
  });
  /* box fit + text size: every element with its own visible text */
  const overflow=[], small=[], rg=document.createRange();
  function framed(e){ const cs=getComputedStyle(e);
    const bg=cs.backgroundColor!=='rgba(0, 0, 0, 0)'&&cs.backgroundColor!=='transparent'||cs.backgroundImage!=='none';
    const bd=['Top','Right','Bottom','Left'].some(x=>parseFloat(cs['border'+x+'Width'])>0&&cs['border'+x+'Style']!=='none');
    return bg||bd||cs.overflowX!=='visible'||cs.overflowY!=='visible'; }
  s.querySelectorAll('*').forEach(el=>{
    if(el.closest('.notes-src,defs,style,script,.spot-layer,title,desc,metadata')) return;   /* not rendered */
    const own=[...el.childNodes].filter(n=>n.nodeType===3&&n.textContent.trim());
    if(!own.length||op(el)<=0.05) return;
    const svg=el instanceof SVGElement;   /* HTML in a <foreignObject> is not: it takes the HTML path */
    /* rendered size in canvas px: CSS font size times every transform between el and the canvas */
    let f=parseFloat(getComputedStyle(el).fontSize);
    if(svg){ const m=typeof el.getScreenCTM==='function'?el.getScreenCTM():null; if(m) f*=Math.hypot(m.a,m.b)*k; }
    else if(el.offsetWidth) f*=el.getBoundingClientRect().width*k/el.offsetWidth;
    const txt=own.map(n=>n.textContent.trim()).join(' ').slice(0,30);
    if(f<minPx-0.05) small.push({tag:el.tagName.toLowerCase(), px:Math.round(f*10)/10, text:txt});
    if(svg) return;                                         /* box fit: HTML text only */
    let box=null; for(let e=el;e&&e!==s;e=e.parentElement){ if(framed(e)){ box=e; break; } }
    if(!box) return;
    const b=box.getBoundingClientRect(); let t={l:1e9,t:1e9,r:-1e9,b:-1e9};
    own.forEach(n=>{ rg.selectNodeContents(n); [...rg.getClientRects()].forEach(q=>{ if(!q.width) return;
      t={l:Math.min(t.l,q.left),t:Math.min(t.t,q.top),r:Math.max(t.r,q.right),b:Math.max(t.b,q.bottom)}; }); });
    if(t.r<t.l) return;
    const out=Math.max(b.left-t.l,t.r-b.right,b.top-t.t,t.b-b.bottom)*k;
    if(out>1.5) overflow.push({tag:el.tagName.toLowerCase(), box:box.tagName.toLowerCase()+
      (box.getAttribute('class')?'.'+box.getAttribute('class').trim().split(/\\s+/).join('.'):''),
      by:Math.round(out*10)/10, text:txt});
  });
  return {paths, low, overflow, small};
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


def parse_size(s):
    try:
        w, h = (int(x) for x in s.lower().split('x'))
        return w, h
    except ValueError:
        raise SystemExit(json.dumps({'error': 'size must be WxH, e.g. 1024x768: %s' % s}))


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
                                        'click:SELECTOR | key:KEY | slide:K. Full option list: the '
                                        'docstring at the head of this file.')
    ap.add_argument('html')
    ap.add_argument('prefix')
    ap.add_argument('advances', nargs='?', type=int, default=8)
    ap.add_argument('--all', action='store_true', help='advance until the last step of the deck')
    ap.add_argument('--size', default='1280x720')
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--click', action=Collect, dest='actions', metavar='SELECTOR')
    ap.add_argument('--then', action=Collect, dest='actions', metavar='ACTION')
    ap.add_argument('--check', action='store_true', help='arrows, safe area, box fit (+ --check-size pass)')
    ap.add_argument('--check-size', action='append', metavar='WxH',
                    help='extra --check size (repeatable; default %s; "none" for none)' % EXTRA_SIZE)
    ap.add_argument('--wait', type=int, default=1200, help='settle wait after each action, ms (default 1200)')
    ap.add_argument('--step-timeout', type=float, default=30)
    ap.add_argument('--json', metavar='FILE', help='write the JSON result to FILE, not stdout')
    a = ap.parse_args()
    actions = parse_actions(a.actions or [])
    w, h = parse_size(a.size)
    extra = []
    if a.check:
        for s in (a.check_size or [EXTRA_SIZE]):
            if s.lower() != 'none' and parse_size(s) != (w, h) and parse_size(s) not in extra:
                extra.append(parse_size(s))

    def emit(result):
        text = json.dumps(result, indent=1)
        if a.json:
            pathlib.Path(a.json).parent.mkdir(parents=True, exist_ok=True)
            pathlib.Path(a.json).write_text(text + '\n', encoding='utf-8')
        else:
            print(text, flush=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        emit({'error': 'playwright not installed', 'install': INSTALL_HINT})
        sys.exit(2)

    url = pathlib.Path(a.html).resolve().as_uri()
    pathlib.Path(a.prefix).parent.mkdir(parents=True, exist_ok=True)
    shots, errs = [], []

    # Watchdog: a slide script stuck in a loop blocks every Playwright call forever, so a
    # thread checks that each stage (load, action, screenshot) finishes in --step-timeout.
    # Launching Chromium is not a slide's fault and can take long on a busy machine: that stage
    # gets at least LAUNCH_S.
    progress = {'t': time.monotonic(), 'stage': 'launch browser', 'limit': max(a.step_timeout, LAUNCH_S)}

    def tick(stage):
        progress['t'], progress['stage'], progress['limit'] = time.monotonic(), stage, a.step_timeout

    def watchdog():
        while True:
            time.sleep(0.5)
            if time.monotonic() - progress['t'] > progress['limit']:
                emit({'shots': shots, 'real_errors': errs, 'size': '%dx%d' % (w, h),
                      'hang': True, 'stuck_at': progress['stage'], 'step_timeout_s': a.step_timeout})
                print('HANG: no progress for %gs at %s (a slide script may loop forever)'
                      % (progress['limit'], progress['stage']), file=sys.stderr, flush=True)
                kill_descendants(os.getpid())   # the looping renderer outlives the driver otherwise
                os._exit(1)

    threading.Thread(target=watchdog, daemon=True).start()

    def drive(pg, snap, tag=''):
        """Load, optional --start, entry shot, advances (N or --all), then the actions."""
        tick('load' + tag)
        pg.goto(url)
        pg.wait_for_timeout(700)
        if a.start > 1:
            pg.evaluate('k => go(k-1, false)', a.start)
            pg.wait_for_timeout(a.wait + 200)
        snap('00_entry', 'entry')
        n = 0

        def more():
            return n < MAX_ADVANCES and not pg.evaluate(END_JS) if a.all else n < a.advances
        while more():
            n += 1
            tick('advance %d (ArrowRight)%s' % (n, tag))
            before = pg.evaluate(STATE_JS)
            pg.keyboard.press('ArrowRight')
            pg.wait_for_timeout(a.wait)
            snap('%02d' % n, 'right')
            if a.all and pg.evaluate(STATE_JS) == before:
                break                                   # nothing moved: a deck without the kit engine
        for kind, val in actions:
            n += 1
            tick('action %d (%s:%s)%s' % (n, kind, val, tag))
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

    def checker(pg, rec, bucket, per_slide_paths):
        """--check on the current frame: fills rec with the findings, bucket with their kinds."""
        c = pg.evaluate(CHECK_JS, [MIN_TEXT_PX])
        prev = per_slide_paths.get(rec['slide'])
        if prev is not None and c['paths'] and prev != c['paths']:
            rec['arrows_moved'] = True
            bucket.add('arrows_moved')
        if c['paths']:
            per_slide_paths[rec['slide']] = c['paths']
        if c['low']:
            rec['below_safe_area'] = c['low'][:5]
            bucket.add('below_safe_area')
        if c['overflow']:
            rec['overflow'] = c['overflow'][:5]
            bucket.add('overflow')
        if c['small']:
            rec['small_text'] = c['small'][:5]

    with sync_playwright() as p:
        b = p.chromium.launch(args=['--no-sandbox', '--disable-gpu'])
        pg = b.new_page(viewport={'width': w, 'height': h})
        pg.on('console', lambda m: errs.append(m.type + ':' + m.text) if m.type == 'error' else None)
        pg.on('pageerror', lambda e: errs.append('PAGEERR:' + str(e)))
        main_paths = {}

        def snap(name, action):
            png = '%s_%s.png' % (a.prefix, name)
            tick('screenshot %s (after %s)' % (name, action))
            pg.screenshot(path=png)
            st = pg.evaluate(STATE_JS)
            rec = {'png': png, 'slide': st['slide'], 'step': st['step'], 'action': action}
            if st.get('spot') is not None:
                rec['spot'] = st['spot']
            if a.check:
                checker(pg, rec, set(), main_paths)
            shots.append(rec)

        drive(pg, snap)
        sizes = {}
        for ew, eh in extra:
            key = '%dx%d' % (ew, eh)
            tag = ' @' + key
            epg = b.new_page(viewport={'width': ew, 'height': eh})
            epg.on('pageerror', lambda e: None)        # page errors are reported by the main pass
            epaths, fails = {}, []

            def esnap(name, action, epg=epg, key=key, tag=tag, epaths=epaths, fails=fails):
                tick('check %s (after %s)%s' % (name, action, tag))
                st = epg.evaluate(STATE_JS)
                rec, kinds = {'slide': st['slide'], 'step': st['step'], 'action': action}, set()
                checker(epg, rec, kinds, epaths)
                if kinds:
                    rec['png'] = '%s_%s@%s.png' % (a.prefix, name, key)
                    epg.screenshot(path=rec['png'])
                if kinds:                               # small text is size-independent: main pass only
                    rec.pop('small_text', None)
                    fails.append(rec)

            drive(epg, esnap, tag)
            sizes[key] = {'shots': fails, 'pass': not fails}
            epg.close()
        tick('closing browser')
        b.close()

    # web fonts fail offline -> system fallback; not a slide error
    real = [e for e in errs if 'net::' not in e and 'ERR_' not in e and 'fonts.g' not in e]
    result = {'shots': shots, 'real_errors': real, 'size': '%dx%d' % (w, h)}
    if a.check:
        moved = [s['png'] for s in shots if s.get('arrows_moved')]
        low_hits = [s['png'] for s in shots if s.get('below_safe_area')]
        over = [s['png'] for s in shots if s.get('overflow')]
        small = [s['png'] for s in shots if s.get('small_text')]
        result['check'] = {'arrows_moved': moved, 'below_safe_area': low_hits, 'overflow': over,
                           'small_text': small, 'sizes': sizes,
                           'pass': not moved and not low_hits and not over
                                   and all(v['pass'] for v in sizes.values())}
    emit(result)
    print('REAL ERRORS:', real or 'NONE', file=sys.stderr)
    if a.check:
        c = result['check']
        if c['small_text']:
            print('WARNING: text below %d px in %d shot(s), e.g. %s' % (MIN_TEXT_PX, len(c['small_text']),
                  c['small_text'][0]), file=sys.stderr)
        for k, v in sizes.items():
            if not v['pass']:
                print('CHECK FAILED at %s: see check.sizes["%s"]' % (k, k), file=sys.stderr)
    ok = not real and (not a.check or result['check']['pass'])
    if a.json:
        print('shot.py: wrote %s (%d shots, %s)' % (a.json, len(shots), 'pass' if ok else 'FAIL'),
              file=sys.stderr)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
