#!/usr/bin/env python3
"""Screenshot every reveal step of a kit deck in headless Chromium (Playwright).

Usage:
    shot.py DECK.html PREFIX [N]          entry shot + N ArrowRight advances (default 8)
Options:
    --all             advance until the last step of the last slide instead of N (no count
                      to guess); stops early if an advance changes nothing
    --size WxH        viewport, default 1280x720 (use 1024x768 for the off-aspect check)
    --start K         jump to the K-th <section class="slide"> in document order before the
                      entry shot (1-based, not 0-based; the kit's go(K-1)). --start K counts
                      every slide in the file; it equals the on-screen number unless a backup
                      (data-offpath) slide comes earlier. --start-id / --start-title avoid the
                      counting. "slide:K" in --then counts the same way
    --start-id ID     jump to the slide with data-id="ID" before the entry shot
    --start-title T   jump to the slide with data-title="T" (exact; must be unique). With
                      --start-id too, both must name the same slide. A name that matches no
                      slide exits 1 with "error" in the JSON. Not combinable with --start
    --click SELECTOR  after the advances: click SELECTOR, then screenshot (repeatable;
                      e.g. '[data-goto=attn]' then '#back' to verify a drill-down). When the
                      element has no box ("not visible", e.g. an empty SVG <g data-goto>) or
                      a point click would land on its own ancestor (an SVG <g> whose shapes
                      have fill:none), the click is dispatched in JS on the element instead;
                      the shot then carries "click": "js-dispatch (...)" and stderr a NOTE
    --frames T1,T2,.. extra screenshots of the entry state at T ms after slide entry (the
                      load, or the --start jump), for autoplay or looping slides; taken
                      before the entry shot, saved as PREFIX_00_tNNNNN.png, listed in
                      "shots" with action "frame", "t_ms" (asked) and "t_actual_ms"
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
                      Also warns (does not fail) on visible text rendered below 12 px;
                      an element with data-small-ok="reason" (on it or an ancestor) is
                      exempt and listed with its reason in the shot's "small_ok" and in
                      check.small_ok instead.
    --check-size WxH  extra --check size (repeatable); "none" for no extra pass
    --wait MS         wait after each action, default 1200 (kit fades take 0.5 s, spotlight
                      layout 0.4 s; use 1700 on slides with their own animations)
    --step-timeout S  give up when one load/action/screenshot makes no progress for S
                      seconds (default 30; a slide script stuck in a loop freezes the page);
                      prints the shots taken so far plus "hang" and "stuck_at", exit 1
    --load-timeout S  limit for the page load itself (default: the larger of 30 and
                      --step-timeout; a big deck on a loaded machine can need > 30 s). The
                      load waits for DOMContentLoaded, then for web fonts
                      (document.fonts.ready) and pending <img> loads, all within S; a DOM
                      that is not ready in S ends like a hang, with "stuck_at": "load";
                      fonts/images still loading after S only print a WARNING
    --json FILE       write the JSON result to FILE instead of stdout; FILE (a path) is
                      required (stdout stays empty; a one-line summary goes to stderr)

Environment:
    SLIDES_SHOT_SLOTS     at most this many shot.py runs drive Chromium at once on the
                          machine (default 2; 0 = no limit); a run waits for a free slot
                          with a message on stderr (parallel Chromium runs crash on a small
                          VM). Slots are flock()ed files, released when the process ends.
    SLIDES_SHOT_LOCK_DIR  where the slot files live (default /tmp/slides-shot-slots)

Writes PREFIX_00_entry.png, PREFIX_01.png, ...  Prints JSON:
    {"shots":[{"png","slide","step","action"[,"spot"]}], "real_errors":[...], "check":{...}}
"spot" appears only on slides with spotlight markers: the lit targets' data-spot
selectors (" @x,y,w,h" appended for a sub-rect, " [no ring]" for a data-ring="none"
hole); [] when none is lit.
Diagnostics ("REAL ERRORS: NONE" or the list, warnings) go to stderr. Font/network
failures (offline web fonts) are filtered out of real_errors. A font, image, stylesheet
or media file that fails to load (a missing local file, or HTTP status >= 400) prints a
WARNING and is listed in "failed_assets" [{url, type, reason}] (the key appears only then;
a remote URL that fails only because the machine is offline is not listed). Exit codes: 0 pass, 1 real errors,
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
  const s=document.querySelector('#stage .slide.active'); if(!s) return {paths:[],low:[],overflow:[],small:[],small_ok:[]};
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
  const overflow=[], small=[], small_ok=[], rg=document.createRange();
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
    if(f<minPx-0.05){ const okEl=el.closest('[data-small-ok]');      /* author opt-out, with a reason */
      if(okEl) small_ok.push({tag:el.tagName.toLowerCase(), px:Math.round(f*10)/10, text:txt,
                              reason:okEl.getAttribute('data-small-ok')});
      else small.push({tag:el.tagName.toLowerCase(), px:Math.round(f*10)/10, text:txt}); }
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
  return {paths, low, overflow, small, small_ok};
}"""

# --click: can a point click reach the element? 'ok', 'not visible' (no box) or 'ancestor'
# (the centre hits an ancestor, e.g. an SVG <g> whose shapes have fill:none), else 'covered'
CLICK_PROBE_JS = """el => {
  const r=el.getBoundingClientRect(); if(r.width<1||r.height<1) return 'not visible';
  const h=document.elementFromPoint(r.left+r.width/2, r.top+r.height/2);
  if(!h) return 'not visible'; if(el.contains(h)) return 'ok'; if(h.contains(el)) return 'ancestor';
  return 'covered';
}"""

CLICK_DISPATCH_JS = """el => { const r=el.getBoundingClientRect();
  el.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true, composed:true, view:window,
                                            clientX:r.left+r.width/2, clientY:r.top+r.height/2})); }"""

# after DOMContentLoaded: wait for web fonts and pending <img> loads, at most ms; false on timeout
READY_JS = """ms => Promise.race([
  Promise.all([document.fonts ? document.fonts.ready : null].concat([...document.images]
    .filter(i => !i.complete).map(i => new Promise(r => { i.addEventListener('load', r, {once:true});
                                                          i.addEventListener('error', r, {once:true}); }))))
    .then(() => true),
  new Promise(r => setTimeout(() => r(false), ms))])"""

# --start-id / --start-title -> index into the kit's slides[]
FIND_JS = """([id, title]) => { const sl=[...document.querySelectorAll('#stage .slide')];
  const i = id ? sl.findIndex(s => s.getAttribute('data-id') === id) : null;
  const m = title ? sl.map((s, k) => s.getAttribute('data-title') === title ? k : -1).filter(k => k >= 0) : null;
  return {i, m}; }"""

ASSET_TYPES = ('font', 'image', 'stylesheet', 'media')
# a remote URL failing with one of these is the machine being offline, not a broken deck
OFFLINE = ('ERR_NAME_NOT_RESOLVED', 'ERR_INTERNET_DISCONNECTED', 'ERR_CONNECTION', 'ERR_NETWORK',
           'ERR_TIMED_OUT', 'ERR_ADDRESS_UNREACHABLE', 'ERR_PROXY', 'ERR_ABORTED')
SLOT_DIR = '/tmp/slides-shot-slots'


def acquire_slot(log=sys.stderr):
    """Block until one of SLIDES_SHOT_SLOTS machine-wide slots is free; returns (fd or None, waited s).
    The fd holds an flock until the process exits (os._exit in the watchdog included)."""
    try:
        n = int(os.environ.get('SLIDES_SHOT_SLOTS', '2'))
    except ValueError:
        n = 2
    try:
        import fcntl
    except ImportError:                                   # Windows: no flock, no limit
        return None, 0.0
    if n <= 0:
        return None, 0.0
    d = pathlib.Path(os.environ.get('SLIDES_SHOT_LOCK_DIR') or SLOT_DIR)
    try:
        d.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(d, 0o1777)                           # shared by every user of the machine
        except OSError:
            pass
        fds = []
        for k in range(n):
            q = d / ('slot-%d' % k)
            fd = os.open(str(q), os.O_RDONLY | os.O_CREAT, 0o666)   # read-only: works on another user's file
            try:
                os.chmod(q, 0o666)
            except OSError:
                pass
            fds.append(fd)
    except OSError as e:
        print('shot.py: WARNING: no Chromium slot lock (%s); running unlimited' % e, file=log, flush=True)
        return None, 0.0
    t0, told = time.monotonic(), False
    while True:
        for fd in fds:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                continue
            for other in fds:
                if other != fd:
                    os.close(other)
            return fd, time.monotonic() - t0
        if not told:
            print('shot.py: waiting for a Chromium slot: %d run(s) busy (SLIDES_SHOT_SLOTS=%d, lock dir %s)'
                  % (n, n, d), file=log, flush=True)
            told = True
        time.sleep(0.25)


def parse_frames(s):
    try:
        out = sorted({int(x) for x in s.split(',') if x.strip()})
    except ValueError:
        out = None
    if not out or out[0] < 0:
        raise SystemExit(json.dumps({'error': '--frames takes ms after slide entry, e.g. 0,500,1500: %s' % s}))
    return out


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
                                        'click:SELECTOR | key:KEY | slide:K. Environment: '
                                        'SLIDES_SHOT_SLOTS = how many shot.py runs may drive Chromium '
                                        'at once on this machine (default 2; 0 = no limit), '
                                        'SLIDES_SHOT_LOCK_DIR = where the slot lock files live '
                                        '(default %s). Full option list: the docstring at the head of '
                                        'this file.' % SLOT_DIR)
    ap.add_argument('html')
    ap.add_argument('prefix')
    ap.add_argument('advances', nargs='?', type=int, default=8)
    ap.add_argument('--all', action='store_true', help='advance until the last step of the deck')
    ap.add_argument('--size', default='1280x720')
    ap.add_argument('--start', type=int, default=0, metavar='K',
                    help='jump to the K-th slide in document order (1-based, = go(K-1)); counts every '
                         'slide in the file, so it equals the on-screen number unless a backup '
                         '(data-offpath) slide comes earlier')
    ap.add_argument('--start-id', metavar='ID', help='jump to the slide with data-id="ID"')
    ap.add_argument('--start-title', metavar='TITLE', help='jump to the slide with data-title="TITLE" (unique)')
    ap.add_argument('--click', action=Collect, dest='actions', metavar='SELECTOR')
    ap.add_argument('--then', action=Collect, dest='actions', metavar='ACTION')
    ap.add_argument('--check', action='store_true', help='arrows, safe area, box fit (+ --check-size pass)')
    ap.add_argument('--check-size', action='append', metavar='WxH',
                    help='extra --check size (repeatable; default %s; "none" for none)' % EXTRA_SIZE)
    ap.add_argument('--wait', type=int, default=1200, help='settle wait after each action, ms (default 1200)')
    ap.add_argument('--step-timeout', type=float, default=30,
                    help='seconds one load/action/screenshot may take before it counts as a hang (default 30)')
    ap.add_argument('--load-timeout', type=float, metavar='S',
                    help='page-load limit in seconds (default: the larger of 30 and --step-timeout)')
    ap.add_argument('--frames', metavar='T1,T2,...',
                    help='extra entry-state shots at these ms after slide entry (autoplay/loop slides)')
    ap.add_argument('--json', metavar='FILE',
                    help='write the JSON result to FILE (a path, required) instead of stdout')
    a = ap.parse_args()
    actions = parse_actions(a.actions or [])
    if a.start and (a.start_id or a.start_title):
        raise SystemExit(json.dumps({'error': '--start does not combine with --start-id/--start-title'}))
    by_name = bool(a.start_id or a.start_title)
    frames = parse_frames(a.frames) if a.frames else []
    load_timeout = a.load_timeout if a.load_timeout is not None else max(30.0, a.step_timeout)
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
    shots, errs, failed_assets = [], [], {}
    slot_fd, slot_wait = acquire_slot()              # held (flock) until this process exits

    # Watchdog: a slide script stuck in a loop blocks every Playwright call forever, so a
    # thread checks that each stage (load, action, screenshot) finishes in --step-timeout.
    # Launching Chromium is not a slide's fault and can take long on a busy machine: that stage
    # gets at least LAUNCH_S.
    progress = {'t': time.monotonic(), 'stage': 'launch browser', 'limit': max(a.step_timeout, LAUNCH_S)}

    def tick(stage, limit=None):
        progress['t'], progress['stage'] = time.monotonic(), stage
        progress['limit'] = a.step_timeout if limit is None else limit

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

    def wait_until(pg, t_end):
        ms = (t_end - time.monotonic()) * 1000
        if ms > 0:
            pg.wait_for_timeout(ms)

    def drive(pg, snap, tag=''):
        """Load, optional --start, timed --frames, entry shot, advances (N or --all), then the actions."""
        tick('load' + tag, load_timeout + 10)          # the goto timeout below fires first
        try:
            # 'load' waits for every subresource and timed out on a 5 MB deck: wait for the DOM,
            # then (below) for fonts and pending images, all within --load-timeout
            pg.goto(url, wait_until='domcontentloaded', timeout=load_timeout * 1000)
        except Exception as e:
            if 'Timeout' not in type(e).__name__ and 'Timeout' not in str(e):
                raise
            emit({'shots': shots, 'real_errors': errs, 'size': '%dx%d' % (w, h), 'hang': True,
                  'stuck_at': 'load' + tag, 'load_timeout_s': load_timeout})
            print('HANG: the page did not load within --load-timeout %gs%s' % (load_timeout, tag),
                  file=sys.stderr, flush=True)
            kill_descendants(os.getpid())
            os._exit(1)
        left = max(1.0, load_timeout - (time.monotonic() - progress['t']))
        if not pg.evaluate(READY_JS, left * 1000):
            print('shot.py: WARNING: fonts/images still loading after --load-timeout %gs%s; shooting anyway'
                  % (load_timeout, tag), file=sys.stderr, flush=True)
        jump = a.start - 1 if a.start > 1 else None
        if by_name:
            f = pg.evaluate(FIND_JS, [a.start_id, a.start_title])
            err = None
            if f['i'] is not None and f['i'] < 0:
                err = 'no slide with data-id="%s"' % a.start_id
            elif f['m'] is not None and len(f['m']) != 1:
                err = ('no slide with data-title="%s"' if not f['m'] else
                       '%d slides with data-title="%%s"' % len(f['m'])) % a.start_title
            elif f['i'] is not None and f['m'] is not None and f['i'] != f['m'][0]:
                err = '--start-id %s and --start-title "%s" name different slides' % (a.start_id, a.start_title)
            if err:
                emit({'shots': shots, 'real_errors': errs, 'size': '%dx%d' % (w, h), 'error': err})
                print('shot.py: ' + err, file=sys.stderr, flush=True)
                kill_descendants(os.getpid())
                os._exit(1)
            jump = f['i'] if f['i'] is not None else f['m'][0]
        t_entry = time.monotonic()
        if jump is not None:
            pg.wait_for_timeout(700)
            pg.evaluate('i => go(i, false)', jump)
            t_entry = time.monotonic()
        for t in frames:
            tick('frame %d ms%s' % (t, tag), a.step_timeout + t / 1000)
            wait_until(pg, t_entry + t / 1000)
            snap('00_t%05d' % t, 'frame',
                 {'t_ms': t, 't_actual_ms': int(round((time.monotonic() - t_entry) * 1000))})
        wait_until(pg, t_entry + ((a.wait + 200) if jump is not None else 700) / 1000)
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
            note = None
            if kind == 'click':
                loc = pg.locator(val)
                probe = loc.first.evaluate(CLICK_PROBE_JS) if loc.count() else 'missing'
                if probe in ('not visible', 'ancestor'):
                    loc.first.evaluate(CLICK_DISPATCH_JS)     # a point click would miss or time out
                    note = 'js-dispatch (%s)' % ('element not visible' if probe == 'not visible'
                                                 else 'point click lands on an ancestor')
                    print('shot.py: NOTE: --click %s: %s' % (val, note), file=sys.stderr, flush=True)
                else:
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
            snap('%02d' % n, '%s:%s' % (kind, val), {'click': note} if note else None)

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
        if c['small_ok']:
            rec['small_ok'] = c['small_ok']

    with sync_playwright() as p:
        b = p.chromium.launch(args=['--no-sandbox', '--disable-gpu'])
        pg = b.new_page(viewport={'width': w, 'height': h})
        pg.on('console', lambda m: errs.append(m.type + ':' + m.text) if m.type == 'error' else None)
        pg.on('pageerror', lambda e: errs.append('PAGEERR:' + str(e)))

        def asset_failed(req, reason):
            if req.resource_type not in ASSET_TYPES or req.url in failed_assets:
                return
            local = req.url.startswith('file:')
            if not local and any(k in reason for k in OFFLINE):
                return                                  # offline, not a broken deck
            failed_assets[req.url] = {'url': req.url, 'type': req.resource_type, 'reason': reason}

        pg.on('requestfailed', lambda r: asset_failed(r, r.failure or 'failed'))
        pg.on('response', lambda r: asset_failed(r.request, 'HTTP %d' % r.status) if r.status >= 400 else None)
        main_paths = {}

        def snap(name, action, extra=None):
            png = '%s_%s.png' % (a.prefix, name)
            tick('screenshot %s (after %s)' % (name, action))
            pg.screenshot(path=png)
            st = pg.evaluate(STATE_JS)
            rec = {'png': png, 'slide': st['slide'], 'step': st['step'], 'action': action}
            rec.update(extra or {})
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

            def esnap(name, action, extra=None, epg=epg, key=key, tag=tag, epaths=epaths, fails=fails):
                tick('check %s (after %s)%s' % (name, action, tag))
                st = epg.evaluate(STATE_JS)
                rec, kinds = {'slide': st['slide'], 'step': st['step'], 'action': action}, set()
                rec.update(extra or {})
                checker(epg, rec, kinds, epaths)
                if kinds:
                    rec['png'] = '%s_%s@%s.png' % (a.prefix, name, key)
                    epg.screenshot(path=rec['png'])
                if kinds:                               # small text is size-independent: main pass only
                    rec.pop('small_text', None)
                    rec.pop('small_ok', None)
                    fails.append(rec)

            drive(epg, esnap, tag)
            sizes[key] = {'shots': fails, 'pass': not fails}
            epg.close()
        tick('closing browser')
        b.close()

    # web fonts fail offline -> system fallback; not a slide error
    real = [e for e in errs if 'net::' not in e and 'ERR_' not in e and 'fonts.g' not in e]
    result = {'shots': shots, 'real_errors': real, 'size': '%dx%d' % (w, h)}
    if failed_assets:
        result['failed_assets'] = list(failed_assets.values())
    if slot_wait >= 0.5:
        result['slot_wait_s'] = round(slot_wait, 1)
    if a.check:
        moved = [s['png'] for s in shots if s.get('arrows_moved')]
        low_hits = [s['png'] for s in shots if s.get('below_safe_area')]
        over = [s['png'] for s in shots if s.get('overflow')]
        small = [s['png'] for s in shots if s.get('small_text')]
        result['check'] = {'arrows_moved': moved, 'below_safe_area': low_hits, 'overflow': over,
                           'small_text': small, 'sizes': sizes,
                           'pass': not moved and not low_hits and not over
                                   and all(v['pass'] for v in sizes.values())}
        oks = {}
        for s in shots:
            for o in s.get('small_ok', []):
                oks.setdefault((o['text'], o['reason']), {'text': o['text'], 'px': o['px'], 'reason': o['reason']})
        if oks:
            result['check']['small_ok'] = list(oks.values())
    emit(result)
    print('REAL ERRORS:', real or 'NONE', file=sys.stderr)
    if failed_assets:
        fa = list(failed_assets.values())
        print('WARNING: %d asset(s) failed to load (fonts/images/CSS; the shots use fallbacks), e.g. %s (%s)'
              % (len(fa), fa[0]['url'], fa[0]['reason']), file=sys.stderr)
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
