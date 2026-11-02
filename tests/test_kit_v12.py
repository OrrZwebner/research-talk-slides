#!/usr/bin/env python3
"""Behavioural tests for the v1.2 kit features (assets/kit.html), through Playwright.

Same contract as test_scripts.py: every expected value follows from how the fixture in
tests/fixtures/k12_*.html was constructed (see its header comment), never from recorded output.

Features: data-offpath, the replay guard in go(), data-autoplay + --anim-speed, data-toggle,
data-hide-at (+ .swap), data-topic + body.ov-topics, .pbox, the below-title caption lane,
.illus + body.no-illus; plus a backwards-compatibility check against the v1.1.0 kit
(tests/fixtures/k12_kit_v110.html, a verbatim copy of the 1.1.0 assets/kit.html).

Run:  python3 -m unittest discover -s tests -p 'test_kit_v12.py' -v
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / 'skills' / 'research-talk-slides' / 'scripts'
FIX = ROOT / 'tests' / 'fixtures'

STATE = ("() => { const sl=[...document.querySelectorAll('#stage .slide')]; "
         "const i=sl.findIndex(s=>s.classList.contains('active')); return [i+1, sl[i]._p||0]; }")


def assemble(*args):
    r = subprocess.run([sys.executable, str(SCRIPTS / 'assemble.py')] + [str(a) for a in args],
                       capture_output=True, text=True)
    return r.returncode, json.loads(r.stdout)


def have_playwright():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch().close()
        return True
    except Exception:
        return False


@unittest.skipUnless(os.environ.get('REQUIRE_PLAYWRIGHT') == '1' or have_playwright(),
                     'Playwright + Chromium not installed')
class TestKitV12(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(args=['--no-sandbox', '--disable-gpu'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self.td.name)
        self.pages = []

    def tearDown(self):
        for pg in self.pages:
            pg.close()
        self.td.cleanup()

    def deck(self, frag, *extra, kit=None):
        out = self.tmp / (pathlib.Path(str(frag)).name + '.deck.html')
        args = (['--kit', kit] if kit else []) + list(extra) + [FIX / frag if isinstance(frag, str) else frag, out]
        code, _ = assemble(*args)
        self.assertEqual(code, 0)
        return out

    def page(self, deck, w=1280, h=720, wait=700):
        pg = self.browser.new_page(viewport={'width': w, 'height': h})
        self.pages.append(pg)
        pg.errors = []
        pg.on('console', lambda m: pg.errors.append(m.text) if m.type == 'error' else None)
        pg.goto(deck.as_uri())
        pg.wait_for_timeout(wait)
        return pg

    @staticmethod
    def key(pg, k, n=1, wait=120):
        for _ in range(n):
            pg.keyboard.press(k)
            pg.wait_for_timeout(wait)

    def state(self, pg):
        return tuple(pg.evaluate(STATE))

    # ------------------------------------------------------------------ 1. data-offpath
    def test_offpath_linear_walk_skips_backups(self):
        pg = self.page(self.deck('k12_offpath.html'))
        seq = [self.state(pg)]
        for _ in range(7):
            self.key(pg, 'ArrowRight')
            seq.append(self.state(pg))
        self.assertEqual(seq, [(1, 0), (2, 0), (2, 1), (4, 0), (5, 0), (5, 1), (7, 0), (7, 0)])
        back = []
        for _ in range(6):
            self.key(pg, 'ArrowLeft')
            back.append(self.state(pg))
        self.assertEqual(back, [(5, 1), (5, 0), (4, 0), (2, 1), (2, 0), (1, 0)])

    def test_offpath_exit_returns_to_the_hub_that_opened_it(self):
        pg = self.page(self.deck('k12_offpath.html'))
        back_shown = "() => document.getElementById('back').classList.contains('show')"
        # forward exit: hub one -> backup -> past its last step -> hub one, fully revealed
        self.key(pg, 'ArrowRight')
        pg.click('.op2 .lk')
        pg.wait_for_timeout(150)
        self.assertEqual(self.state(pg), (3, 0))
        self.assertTrue(pg.evaluate(back_shown))
        seq = []
        for _ in range(3):
            self.key(pg, 'ArrowRight')
            seq.append(self.state(pg))
        self.assertEqual(seq, [(3, 1), (3, 2), (2, 1)])
        self.assertFalse(pg.evaluate(back_shown))
        # backward exit: ← before the first step returns too
        pg.click('.op2 .lk')
        pg.wait_for_timeout(150)
        self.key(pg, 'ArrowLeft')
        self.assertEqual(self.state(pg), (2, 1))
        # second hub: history wins over DOM order (hub two, not hub one)
        self.key(pg, 'ArrowRight', 3)
        self.assertEqual(self.state(pg), (5, 1))
        pg.click('.op5 .lk')
        pg.wait_for_timeout(150)
        self.assertEqual(self.state(pg), (3, 0))
        self.key(pg, 'ArrowRight', 3)
        self.assertEqual(self.state(pg), (5, 1))
        # a backup with no steps: → returns at once
        pg.click('.op5 .lk2')
        pg.wait_for_timeout(150)
        self.assertEqual(self.state(pg), (6, 0))
        self.key(pg, 'ArrowRight')
        self.assertEqual(self.state(pg), (5, 1))
        # after a return the walk goes on past the hub
        self.key(pg, 'ArrowRight')
        self.assertEqual(self.state(pg), (7, 0))

    def test_offpath_without_history_returns_to_first_linking_hub(self):
        pg = self.page(self.deck('k12_offpath.html'))
        pg.evaluate('() => go(2, false)')           # jump straight onto the backup (as shot.py --start)
        pg.wait_for_timeout(150)
        self.assertEqual(self.state(pg), (3, 0))
        self.key(pg, 'ArrowRight', 3)
        self.assertEqual(self.state(pg), (2, 1))
        pg.evaluate('() => go(5, false)')           # backup two: only hub two links to it
        pg.wait_for_timeout(150)
        self.key(pg, 'ArrowLeft')
        self.assertEqual(self.state(pg), (5, 1))

    def test_offpath_numbers_bar_dots_and_overview_ignore_backups(self):
        deck = self.deck('k12_offpath.html', '--body-class', 'slide-numbers progress')
        js = """() => { const n=document.getElementById('kit-num'), d=document.getElementById('kit-bar');
          return [getComputedStyle(n).display==='none'?null:n.textContent, parseFloat(d.firstElementChild.style.width)]; }"""
        pg = self.page(deck)
        want = [(None, 0), ('2', 100 / 6), ('2', 200 / 6), ('3', 300 / 6), ('4', 400 / 6), ('4', 500 / 6), ('5', 100)]
        for k, (num, width) in enumerate(want):
            if k:
                self.key(pg, 'ArrowRight')
            got = pg.evaluate(js)
            with self.subTest(k=k):
                self.assertEqual(got[0], num)
                self.assertAlmostEqual(got[1], width, delta=0.01)
        self.key(pg, 'ArrowLeft', 4)                 # back on hub one, step 1 shown: 2/6
        self.assertEqual(self.state(pg), (2, 1))
        pg.click('.op2 .lk')
        pg.wait_for_timeout(150)
        got = pg.evaluate(js)
        self.assertIsNone(got[0])                    # no number on a backup
        self.assertAlmostEqual(got[1], 200 / 6, delta=0.01)   # the bar stays at the hub
        self.key(pg, 'ArrowRight')
        self.assertAlmostEqual(pg.evaluate(js)[1], 200 / 6, delta=0.01)
        # overview and dots: on-path slides only
        tiles = pg.evaluate("() => [...document.querySelectorAll('#ovgrid .ovitem .tt')].map(e=>e.textContent)")
        self.assertEqual(tiles, ['Title', 'Hub one', 'Middle', 'Hub two', 'End'])
        dots = pg.evaluate("() => [...document.querySelectorAll('#dots button')].map(b=>getComputedStyle(b).display!=='none')")
        self.assertEqual(dots, [True, True, False, True, True, False, True])

    def test_offpath_top_progress_bar_counts_on_path_only(self):
        pg = self.page(self.deck('k12_offpath.html'))
        w = "() => parseFloat(document.getElementById('prog').style.width)"
        widths = []
        for _ in range(4):                       # (1,0) (2,0) (2,1) (4,0) (5,0)
            self.key(pg, 'ArrowRight')
            widths.append(pg.evaluate(w))
        self.assertEqual([round(x, 2) for x in widths], [25.0, 25.0, 50.0, 75.0])

    # ------------------------------------------------------------------ 2. replay guard
    def test_replay_guard_shows_end_states_when_arriving_backwards(self):
        pg = self.page(self.deck('k12_replay.html'))
        js = """() => { const s=document.querySelector('.rp1'), bar=s.querySelector('.rp-bar'), spin=s.querySelector('.rp-spin');
          const a=bar.getAnimations(), sp=spin.getAnimations();
          return [a.length?a[0].playState:'none', getComputedStyle(bar).width,
                  parseFloat(getComputedStyle(s.querySelector('.rp-fade')).opacity),
                  sp.length?sp[0].playState:'none',
                  s.getAnimations().length]; }"""
        self.key(pg, 'ArrowRight', 1, wait=100)
        st = pg.evaluate(js)
        self.assertEqual(st[0], 'running')           # forward: the build plays
        self.key(pg, 'ArrowRight', 2, wait=100)      # fade step, then slide 2
        entry = pg.evaluate("() => document.querySelector('.rp2 .rp-entry').getAnimations().map(a=>a.playState)")
        self.assertEqual(entry, ['running'])         # forward arrival, step 0: not finished
        pg.keyboard.press('ArrowLeft')               # back onto slide 1, all steps shown
        pg.wait_for_timeout(60)
        bar_state, width, fade_op, spin_state, own = pg.evaluate(js)
        self.assertEqual(bar_state, 'finished')
        self.assertEqual(width, '400px')
        self.assertEqual(fade_op, 1)                 # the .5 s fade jumped to its end
        self.assertEqual(spin_state, 'running')      # infinite animation left running
        self.assertEqual(own, 1)                     # the slide's own cross-fade is not cut

    def test_replay_guard_on_drill_back(self):
        # ‹ back lands on the hub fully revealed: its finite transitions are finished too
        pg = self.page(self.deck('k12_offpath.html'))
        self.key(pg, 'ArrowRight', 2)
        pg.click('.op2 .lk')
        pg.wait_for_timeout(700)
        pg.click('#back')
        pg.wait_for_timeout(60)
        op = pg.evaluate("() => parseFloat(getComputedStyle(document.querySelector('.op2 .step')).opacity)")
        self.assertEqual(op, 1)

    # ------------------------------------------------------------------ 3. data-autoplay
    def test_autoplay_plays_on_entry_and_restarts(self):
        pg = self.page(self.deck('k12_autoplay.html'))
        js = """() => ['.ap-loop','.ap-once'].map(c=>{ const e=document.querySelector('.ap2 '+c), a=e.getAnimations();
          return [e.classList.contains('playing'), a.length?a[0].playState:'none', a.length?a[0].currentTime:null]; })"""
        loop, once = pg.evaluate(js)
        self.assertEqual((loop[0], once[0]), (False, False))     # not on the slide yet
        self.key(pg, 'ArrowRight', 1, wait=50)
        loop, once = pg.evaluate(js)
        self.assertEqual((loop[0], loop[1]), (True, 'running'))
        self.assertEqual((once[0], once[1]), (True, 'running'))
        self.assertLess(once[2], 500)
        pg.wait_for_timeout(900)
        self.assertGreater(pg.evaluate(js)[0][2], 800)
        self.key(pg, 'ArrowRight', 1, wait=50)                    # leave: class removed
        loop, once = pg.evaluate(js)
        self.assertEqual((loop[0], once[0]), (False, False))
        self.assertEqual((loop[1], once[1]), ('none', 'none'))
        self.assertTrue(pg.evaluate("() => document.querySelector('.ap3').classList.contains('playing')"))
        pg.keyboard.press('ArrowLeft')                            # back: the loop restarts from 0
        pg.wait_for_timeout(50)
        loop, once = pg.evaluate(js)
        self.assertEqual((loop[0], loop[1]), (True, 'running'))
        self.assertLess(loop[2], 400)
        self.assertEqual(once[1], 'finished')                     # replay guard: finite one at its end
        self.assertFalse(pg.evaluate("() => document.querySelector('.ap3').classList.contains('playing')"))
        self.key(pg, 'ArrowLeft', 1, wait=50)
        self.key(pg, 'ArrowRight', 1, wait=50)                    # forward again: finite one from 0
        once = pg.evaluate(js)[1]
        self.assertEqual(once[1], 'running')
        self.assertLess(once[2], 500)

    def test_anim_speed_variable(self):
        pg = self.page(self.deck('k12_autoplay.html'))
        self.key(pg, 'ArrowRight')
        dur = "() => getComputedStyle(document.querySelector('.ap2 .ap-loop')).animationDuration"
        self.assertEqual(pg.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--anim-speed').trim()"), '1')
        self.assertEqual(pg.evaluate(dur), '2s')
        pg.evaluate("() => document.documentElement.style.setProperty('--anim-speed','4')")
        self.assertEqual(pg.evaluate(dur), '0.5s')

    # ------------------------------------------------------------------ 4. data-toggle
    def test_toggle_click_does_not_advance_and_resets(self):
        pg = self.page(self.deck('k12_toggle.html'))
        cls = "() => ['alt','b2','dflt'].filter(c=>document.querySelector('.tg1').classList.contains(c))"
        self.assertEqual(pg.evaluate(cls), ['dflt'])
        pg.mouse.click(180, 325)                       # the button
        pg.wait_for_timeout(100)
        self.assertEqual(self.state(pg), (1, 0))
        self.assertEqual(pg.evaluate(cls), ['alt', 'dflt'])
        self.assertEqual(pg.get_attribute('.tgb', 'aria-pressed'), 'true')
        self.assertFalse(pg.evaluate("() => document.activeElement===document.querySelector('.tgb')"))
        pg.mouse.click(180, 325)
        pg.wait_for_timeout(100)
        self.assertEqual(pg.evaluate(cls), ['dflt'])
        pg.mouse.click(780, 325)                       # toggles off a class the slide starts with
        pg.mouse.click(480, 325)
        pg.wait_for_timeout(100)
        self.assertEqual(self.state(pg), (1, 0))
        self.assertEqual(pg.evaluate(cls), ['b2'])
        self.key(pg, 'ArrowRight')                     # step change: back to the slide's own state
        self.assertEqual(self.state(pg), (1, 1))
        self.assertEqual(pg.evaluate(cls), ['dflt'])
        self.assertEqual(pg.get_attribute('.tgs', 'aria-pressed'), 'false')
        pg.mouse.click(180, 325)
        self.key(pg, 'ArrowLeft')                      # step back resets too
        self.assertEqual(self.state(pg), (1, 0))
        self.assertEqual(pg.evaluate(cls), ['dflt'])
        pg.mouse.click(180, 325)
        self.key(pg, 'ArrowRight', 3)                  # leave the slide
        self.assertEqual(self.state(pg), (2, 0))
        self.key(pg, 'ArrowLeft')
        self.assertEqual(self.state(pg), (1, 2))
        self.assertEqual(pg.evaluate(cls), ['dflt'])

    def test_toggle_is_keyboard_safe(self):
        pg = self.page(self.deck('k12_toggle.html'))
        has = "c => document.querySelector('.tg1').classList.contains(c)"
        pg.focus('.tgb')
        self.key(pg, ' ')                              # space advances, never toggles
        self.assertEqual(self.state(pg), (1, 1))
        self.assertFalse(pg.evaluate(has, 'alt'))
        pg.focus('.tgb')
        self.key(pg, 'Enter')                          # Enter on a focused toggle toggles
        self.assertEqual(self.state(pg), (1, 1))
        self.assertTrue(pg.evaluate(has, 'alt'))
        self.assertEqual(pg.get_attribute('.tgs', 'tabindex'), '0')
        self.assertEqual(pg.get_attribute('.tgs', 'role'), 'button')
        pg.focus('.tgs')
        self.key(pg, 'Enter')
        self.assertTrue(pg.evaluate(has, 'b2'))
        self.assertEqual(pg.get_attribute('.tgs', 'aria-pressed'), 'true')
        self.key(pg, 'ArrowRight')                     # arrows still navigate from a focused toggle
        self.assertEqual(self.state(pg), (1, 2))
        self.assertFalse(pg.evaluate(has, 'b2'))

    # ------------------------------------------------------------------ 5. data-hide-at
    def test_hide_at_key_and_swap(self):
        pg = self.page(self.deck('k12_hideat.html'))
        vis = """() => ['a','b','c','e'].map(c=>{ const e=document.querySelector('.ha1 .'+c), s=getComputedStyle(e);
          return s.visibility==='visible'&&parseFloat(s.opacity)>0.99; })"""
        want = {0: [True, False, False, False], 1: [True, False, True, False],
                2: [False, True, True, False], 3: [False, True, False, True]}
        for p in (0, 1, 2, 3, 2, 1, 0):
            if self.state(pg)[1] < p:
                self.key(pg, 'ArrowRight', wait=700)
            elif self.state(pg)[1] > p:
                self.key(pg, 'ArrowLeft', wait=700)
            with self.subTest(p=p):
                self.assertEqual(self.state(pg), (1, p))
                self.assertEqual(pg.evaluate(vis), want[p])
        ra = pg.evaluate("() => ['a','b'].map(c=>{ const e=document.querySelector('.ha1 .'+c); return [e.offsetLeft,e.offsetTop]; })")
        self.assertEqual(ra[0], ra[1])                 # .swap stacks A and B in one place
        self.assertEqual(pg.errors, [])

    def test_hide_at_count_and_arrival_backwards(self):
        pg = self.page(self.deck('k12_hideat.html'))
        hid = "() => document.querySelector('.ha2 .g').classList.contains('kit-hid')"
        self.key(pg, 'ArrowRight', 4)                  # slide 1 to its end, then slide 2
        self.assertEqual(self.state(pg), (2, 0))
        got = [pg.evaluate(hid)]
        for _ in range(3):
            self.key(pg, 'ArrowRight')
            got.append(pg.evaluate(hid))
        self.assertEqual(got, [False, False, True, True])
        self.key(pg, 'ArrowRight')                     # last slide: nothing happens
        pg.evaluate('() => go(0, true)')               # arrival with all steps shown
        pg.wait_for_timeout(60)
        self.assertEqual(pg.evaluate("() => ['a','c'].map(c=>document.querySelector('.ha1 .'+c).classList.contains('kit-hid'))"),
                         [True, True])
        self.assertEqual(pg.evaluate("() => getComputedStyle(document.querySelector('.ha1 .a')).visibility"), 'hidden')

    def test_hide_at_bad_value_is_one_console_error(self):
        pg = self.page(self.deck('k12_hideat_bad.html'))
        self.key(pg, 'ArrowRight')
        self.key(pg, 'ArrowLeft')
        errs = [e for e in pg.errors if 'data-hide-at' in e]
        self.assertEqual(len(errs), 1)
        self.assertIn('"soon"', errs[0])
        self.assertFalse(pg.evaluate("() => document.querySelector('.hb1 .z').classList.contains('kit-hid')"))

    # ------------------------------------------------------------------ 6. topic overview
    OV = """() => [...document.querySelectorAll('#ovgrid .ovsec')].map(s=>[s.querySelector('.ovsec-h').textContent,
        [...s.querySelectorAll('.ovitem')].map(b=>[b.querySelector('.tt').textContent, b.querySelector('.ovn').textContent])])"""

    def test_topic_overview_groups_by_section(self):
        pg = self.page(self.deck('k12_topics.html', '--body-class', 'ov-topics'))
        self.assertEqual(pg.evaluate(self.OV), [
            ['Title', [['Title', '1 slide']]],
            ['1 · Intro', [['Motivation', '2 slides'], ['Data', '1 slide']]],
            ['2 · Method', [['Method overview', '2 slides']]]])
        pg.keyboard.press('o')
        pg.wait_for_timeout(100)
        pg.click('#ovgrid .ovitem:has-text("Data")')
        pg.wait_for_timeout(150)
        self.assertEqual(self.state(pg), (4, 0))
        self.assertFalse(pg.evaluate("() => document.getElementById('overview').classList.contains('show')"))

    def test_topic_overview_off_by_default(self):
        pg = self.page(self.deck('k12_topics.html'))
        self.assertEqual(pg.evaluate(self.OV), [])
        tiles = pg.evaluate("() => [...document.querySelectorAll('#ovgrid > .ovitem .tt')].map(e=>e.textContent)")
        self.assertEqual(tiles, ['Title', 'Why', 'More why', 'Dataset', 'Method overview', 'Method detail'])

    # ------------------------------------------------------------------ 7 + 9. .pbox, .illus
    def test_pbox_accent_and_header(self):
        pg = self.page(self.deck('k12_pbox_illus.html'))
        got = pg.evaluate("""() => ['.p1','.p2','.p3'].map(c=>getComputedStyle(document.querySelector(c)).borderLeftColor)
          .concat([getComputedStyle(document.querySelector('.pbox-h')).fontSize,
                   getComputedStyle(document.querySelector('.p1')).borderLeftWidth])""")
        self.assertEqual(got, ['rgb(27, 42, 74)', 'rgb(232, 131, 58)', 'rgb(18, 52, 86)', '16px', '5px'])

    def test_illus_hidden_only_with_no_illus(self):
        js = "() => [...document.querySelectorAll('.pi1 .illus, .pi1 .plain')].map(e=>getComputedStyle(e).display)"
        pg = self.page(self.deck('k12_pbox_illus.html'))
        self.assertNotIn('none', pg.evaluate(js))
        pg2 = self.page(self.deck('k12_pbox_illus.html', '--body-class', 'no-illus'))
        got = pg2.evaluate(js)                       # span.illus, span.plain, text.illus (DOM order)
        self.assertEqual((got[0], got[2]), ('none', 'none'))
        self.assertNotEqual(got[1], 'none')

    # ------------------------------------------------------------------ 8. below-title lane
    def test_below_title_lane_both_sizes(self):
        js = """() => { const s=document.querySelector('#stage .slide.active'), c=s.querySelector('.spot-cap.on');
          const l=s.querySelector('.spot-g.on .spot-lead'), t=s.querySelector('h2.title');
          let tb=null; if(t){ const sr=s.getBoundingClientRect(), rg=document.createRange(); rg.selectNodeContents(t);
            const r=rg.getBoundingClientRect(); tb=(r.bottom-sr.top)*720/sr.height; }
          return [c.offsetLeft,c.offsetTop,c.offsetWidth,c.offsetHeight,tb,
                  (l.getAttribute('d').match(/-?[\\d.]+/g)||[]).map(Number)]; }"""
        deck = self.deck('k12_lane.html')
        for w, h in ((1280, 720), (1024, 768)):
            pg = self.page(deck, w, h)
            for slide in (1, 2):
                self.key(pg, 'ArrowRight', slide, wait=500)      # slide 1 step 1; slide 2 entry + step 1
                x, y, cw, ch, tb, d = pg.evaluate(js)
                with self.subTest(size=(w, h), slide=slide):
                    self.assertAlmostEqual(x + cw / 2, 600, delta=1)
                    if slide == 1:
                        self.assertAlmostEqual(y, tb + 12, delta=0.5)
                        self.assertGreater(tb, 52)                 # a real title box (padding-top 52)
                    else:
                        self.assertIsNone(tb)
                        self.assertAlmostEqual(y, 16, delta=0.5)
                    self.assertEqual(len(d), 4)
                    self.assertAlmostEqual(d[1], y + ch, delta=1)  # leader from the caption's bottom
                    self.assertAlmostEqual(d[3], 289, delta=0.5)   # to the ring's top
            self.assertEqual([e for e in pg.errors if 'caption-lane' in e], [])

    # ------------------------------------------------------------------ BUILD_GUIDE §9.1 / §9.3 seams
    # the canvas minus the kit chrome that legitimately changes at a cut (top bar y 0-3, side dots x > 1240)
    CLIP = {'x': 0, 'y': 4, 'width': 1230, 'height': 640}
    BOX = "s => { const r=document.querySelector(s).getBoundingClientRect(); return [r.left,r.top,r.width,r.height]; }"

    # Frame comparison with a tolerance (exact PNG bytes differ across machines: antialiasing, font
    # rasterising, composited layers). Both PNGs are decoded in a blank page's <canvas> (no Pillow).
    # mad  = mean |a-b| over all RGB values (0-255);
    # pale = the largest rise in mean brightness of any 32x32 block from `ref` to `img`.
    # A pale frame (cross-fade over white) brightens the dark blocks by tens of levels; rasterising
    # noise moves single edge pixels, which a 32x32 block mean dilutes to well under 1 level.
    DIFF_JS = """async ([a, b]) => {
      const load = u => new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = no; i.src = u; });
      const px = async u => { const i = await load(u), c = document.createElement('canvas'); c.width = i.width; c.height = i.height;
        const x = c.getContext('2d'); x.drawImage(i, 0, 0); return [x.getImageData(0, 0, i.width, i.height).data, i.width, i.height]; };
      const [A, w, h] = await px(a), [B] = await px(b);
      let sum = 0, pale = 0;
      for (let k = 0; k < A.length; k += 4) sum += Math.abs(A[k]-B[k]) + Math.abs(A[k+1]-B[k+1]) + Math.abs(A[k+2]-B[k+2]);
      for (let by = 0; by + 32 <= h; by += 32) for (let bx = 0; bx + 32 <= w; bx += 32) {
        let d = 0;
        for (let y = by; y < by + 32; y++) for (let x = bx; x < bx + 32; x++) { const k = (y*w + x)*4;
          d += (B[k]+B[k+1]+B[k+2]) - (A[k]+A[k+1]+A[k+2]); }
        pale = Math.max(pale, d / (32*32*3)); }
      return [sum / (w*h*3), pale]; }"""
    MAD_MAX, PALE_MAX = 1.5, 6.0

    def diff(self, ref, img):
        import base64
        if not hasattr(self, '_dp'):
            self._dp = self.browser.new_page()
            self.pages.append(self._dp)
        u = lambda b: 'data:image/png;base64,' + base64.b64encode(b).decode()
        return self._dp.evaluate(self.DIFF_JS, [u(ref), u(img)])

    def assertSameFrame(self, ref, img, what):
        mad, pale = self.diff(ref, img)
        self.assertLess(mad, self.MAD_MAX, '%s: mean abs diff %.2f' % (what, mad))
        self.assertLess(pale, self.PALE_MAX, '%s: a 32x32 block is %.1f levels paler' % (what, pale))

    @staticmethod
    def settle(pg):
        # no finite animation or transition still running, then two frames
        pg.wait_for_function("""() => document.getAnimations().every(a => a.playState !== 'running' ||
            !isFinite(a.effect.getComputedTiming().endTime))""", timeout=5000)
        pg.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")

    def seam(self, frag, a_steps, shared_a, shared_b, pale_css):
        pg = self.page(self.deck(frag))
        self.key(pg, 'ArrowRight', a_steps, wait=900)           # A at its final frame
        self.assertEqual(self.state(pg), (1, a_steps))
        self.settle(pg)
        end, box_a = pg.screenshot(clip=self.CLIP), pg.evaluate(self.BOX, shared_a)
        pg.keyboard.press('ArrowRight')
        cut = pg.screenshot(clip=self.CLIP)                      # the frame just after the cut
        self.assertEqual(self.state(pg), (2, 0))
        self.assertSameFrame(end, cut, "frame after the cut vs A's final frame")
        box_b = pg.evaluate(self.BOX, shared_b)
        for u, v in zip(box_a, box_b):
            self.assertAlmostEqual(u, v, delta=2)
        self.settle(pg)
        self.assertSameFrame(end, pg.screenshot(clip=self.CLIP), "B's settled entry vs A's final frame")
        pg.keyboard.press('ArrowLeft')
        back = pg.screenshot(clip=self.CLIP)                     # replay guard: A's end state at once
        self.assertEqual(self.state(pg), (1, a_steps))
        self.assertSameFrame(end, back, "<- from B vs A's final frame")
        # control: with the kit's cross-fade left on, the same sample must fail the same check
        ctl = self.page(self.deck(frag))
        ctl.add_style_tag(content=pale_css)
        self.key(ctl, 'ArrowRight', a_steps, wait=900)
        self.settle(ctl)
        end2 = ctl.screenshot(clip=self.CLIP)
        ctl.keyboard.press('ArrowRight')
        mad, pale = self.diff(end2, ctl.screenshot(clip=self.CLIP))
        self.assertGreaterEqual(pale, self.PALE_MAX, 'control: cross-fade not detected (pale %.1f, mad %.2f)' % (pale, mad))
        self.seam_stats = (self.diff(end, cut), (mad, pale))
        return pg

    def test_zoom_pair_seam(self):
        pg = self.seam('k12_zoom.html', 1, '.zA .b2', '.zB .b2',
                       '.slide.zA,.slide.zB{transition:opacity .5s ease!important}')
        self.key(pg, 'ArrowRight', 2, wait=900)                  # back on B, then its zoom step
        self.assertEqual(self.state(pg), (2, 1))
        w = pg.evaluate(self.BOX, '.zB .b2')[2]
        self.assertAlmostEqual(w, 360, delta=1)                  # block 2 at scale 2

    def test_fold_morph_seam(self):
        pg = self.seam('k12_fold.html', 2, '.fA .k3', '.fB .k3',
                       '.slide.fA,.slide.fB{transition:opacity .5s ease!important}')
        box = pg.evaluate(self.BOX, '.fA .k3')                   # folded: (100-36+380*.25, 300-160) 40x22.5
        for u, v in zip(box, [159, 140, 40, 22.5]):
            self.assertAlmostEqual(u, v, delta=1)
        self.assertEqual(pg.evaluate("() => getComputedStyle(document.querySelector('.fA .fn')).visibility"), 'hidden')
        self.key(pg, 'ArrowLeft', 1, wait=900)                   # one more <- unfolds it
        self.assertEqual(self.state(pg), (1, 1))
        for u, v in zip(pg.evaluate(self.BOX, '.fA .k3'), [480, 300, 160, 90]):
            self.assertAlmostEqual(u, v, delta=1)
        self.assertEqual(pg.evaluate("() => getComputedStyle(document.querySelector('.fA .fn')).visibility"), 'visible')

    # ------------------------------------------------------------------ backwards compatibility
    SNAP = """() => { const sl=[...document.querySelectorAll('#stage .slide')], i=sl.findIndex(s=>s.classList.contains('active'));
      const vis=e=>getComputedStyle(e).display;
      return {i, p:sl[i]._p||0, shown:[...sl[i].querySelectorAll('.step')].map(e=>e.classList.contains('shown')),
        num:[vis(document.getElementById('kit-num')), document.getElementById('kit-num').textContent],
        bar:document.getElementById('kit-bar').firstElementChild.style.width, prog:document.getElementById('prog').style.width,
        dots:[...document.querySelectorAll('#dots button')].map(b=>vis(b)+(b.classList.contains('active')?'*':'')),
        ov:document.getElementById('ovgrid').innerHTML, back:document.getElementById('back').className,
        cls:sl.map(s=>s.className),
        op:[...sl[i].querySelectorAll('.step')].map(e=>Math.round(parseFloat(getComputedStyle(e).opacity)*100)),
        spot:[...sl[i].querySelectorAll('.spot-g')].map(g=>g.getAttribute('class')+'|'+[...g.querySelectorAll('path')].map(p=>p.getAttribute('d')).join(';'))}; }"""

    def walk(self, deck, body):
        pg = self.page(deck)
        snaps = [pg.evaluate(self.SNAP)]
        for k in body:
            if k.startswith('click:'):
                pg.click(k[6:])
            else:
                pg.keyboard.press(k)
            pg.wait_for_timeout(900)
            snaps.append(pg.evaluate(self.SNAP))
        return snaps

    def test_deck_without_new_attributes_matches_v110(self):
        old = FIX / 'k12_kit_v110.html'
        cases = [
            (ROOT / 'examples' / 'demo_fragment.html', (),
             ['ArrowRight'] * 9 + ['click:[data-goto]', 'ArrowRight', 'ArrowRight', 'Backspace',
                                   'ArrowRight', 'ArrowRight', 'ArrowRight', 'ArrowLeft', 'ArrowLeft']),
            (FIX / 'numbers.html', ('--body-class', 'slide-numbers progress'),
             ['ArrowRight'] * 6 + ['ArrowLeft'] * 3),
            (FIX / 'spot_drill.html', (), ['ArrowRight'] * 4 + ['ArrowLeft'] * 2),
        ]
        for frag, extra, keys in cases:
            with self.subTest(fragment=frag.name):
                # DOM state, not pixels: the demo's own animations make screenshots differ run to run
                a = self.walk(self.deck(frag, *extra, kit=old), keys)
                b = self.walk(self.deck(frag, *extra), keys)
                self.assertEqual(len(a), len(keys) + 1)
                self.assertEqual(a, b)


if __name__ == '__main__':
    unittest.main()
