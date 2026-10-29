#!/usr/bin/env python3
"""Tests for scripts/assemble.py and scripts/shot.py (stdlib unittest).

Every expected value is fixed by how the synthetic fixture in tests/fixtures/ was
constructed (see the comment at the top of each fixture), never by recording what
the script printed. Do not update an expectation to match new output: if a value
moves, the code is wrong until proven otherwise.

Run:  python3 -m unittest discover -s tests -v
The shot.py tests are skipped when Playwright (with Chromium) is not installed,
unless REQUIRE_PLAYWRIGHT=1 is set (as in CI), in which case they run and fail.
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
START = '<!-- ============================ SLIDES:START ============================ -->'
END = '<!-- ============================ SLIDES:END ============================== -->'


def run(script, *args):
    r = subprocess.run([sys.executable, str(SCRIPTS / script)] + [str(a) for a in args],
                       capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def assemble(*args):
    code, out, err = run('assemble.py', *args)
    return code, json.loads(out)


def have_playwright():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch().close()
        return True
    except Exception:
        return False


class TestAssemble(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self.td.name)

    def tearDown(self):
        self.td.cleanup()

    def test_clean_fragment_no_warnings(self):
        code, j = assemble(FIX / 'clean.html', self.tmp / 'o.html')
        self.assertEqual(code, 0)
        self.assertEqual(j['warnings'], [])
        self.assertEqual(j['slides'], 2)

    def test_duplicate_id_warns(self):
        code, j = assemble(FIX / 'dup_id.html', self.tmp / 'o.html')
        self.assertEqual(code, 0)
        self.assertEqual(len(j['warnings']), 1)
        self.assertIn('duplicate element ids', j['warnings'][0])
        self.assertTrue(j['warnings'][0].endswith(': box'))      # only-once is not listed

    def test_viewport_unit_warns_comment_ignored(self):
        code, j = assemble(FIX / 'vw_unit.html', self.tmp / 'o.html')
        self.assertEqual(code, 0)
        self.assertEqual(len(j['warnings']), 1)
        self.assertTrue(j['warnings'][0].endswith(': 50vw'))     # 10vh lives in a comment

    def test_dangling_goto_warns(self):
        code, j = assemble(FIX / 'dangling_goto.html', self.tmp / 'o.html')
        self.assertEqual(code, 0)
        self.assertEqual(len(j['warnings']), 1)
        self.assertIn('data-goto', j['warnings'][0])
        self.assertTrue(j['warnings'][0].endswith(': nowhere'))  # 'present' resolves

    def test_splice_is_exact(self):
        out = self.tmp / 'o.html'
        code, j = assemble('--kit', FIX / 'kit_tiny.html', FIX / 'one_slide.html', out)
        self.assertEqual(code, 0)
        expected = ('HEAD\n' + START + '\n<section class="slide x">X</section>\n'
                    + END + '\nTAIL\n')
        self.assertEqual(out.read_text(encoding='utf-8'), expected)
        self.assertEqual(j['slides'], 1)
        self.assertEqual(j['chars'], len(expected))

    def test_multi_fragment_order_and_count(self):
        out = self.tmp / 'o.html'
        code, j = assemble('--kit', FIX / 'kit_tiny.html', '-o', out,
                           FIX / 'one_slide.html', FIX / 'clean.html')
        self.assertEqual(code, 0)
        self.assertEqual(j['slides'], 1 + 2)
        text = out.read_text(encoding='utf-8')
        self.assertLess(text.index('class="slide x"'), text.index('class="slide fxa"'))

    def test_missing_markers_exit_2(self):
        code, j = assemble('--kit', FIX / 'kit_nomarkers.html', FIX / 'one_slide.html',
                           self.tmp / 'o.html')
        self.assertEqual(code, 2)
        self.assertIn('markers', j['error'])

    def test_missing_fragment_exit_2(self):
        code, j = assemble(FIX / 'does_not_exist.html', self.tmp / 'o.html')
        self.assertEqual(code, 2)
        self.assertIn('fragment not found', j['error'])

    def test_bad_arity_exit_2(self):
        code, j = assemble(FIX / 'one_slide.html')
        self.assertEqual(code, 2)

    def test_default_kit_has_markers_once(self):
        kit = (SCRIPTS.parent / 'assets' / 'kit.html').read_text(encoding='utf-8')
        self.assertEqual(kit.count(START), 1)
        self.assertEqual(kit.count(END), 1)
        self.assertLess(kit.index(START), kit.index(END))

    def test_spot_lint_warns(self):
        code, j = assemble(FIX / 'spot_lint.html', self.tmp / 'o.html')
        self.assertEqual(code, 0)
        self.assertEqual(len(j['warnings']), 2)                   # the commented marker is ignored
        self.assertIn('class="spot step"', j['warnings'][0])
        self.assertTrue(j['warnings'][0].endswith(': .p, .q'))    # '.row > .r' has both classes
        self.assertTrue(j['warnings'][1].endswith(': 0.5,0.5'))

    def test_spot_ring_lint_warns(self):
        code, j = assemble(FIX / 'spot_badring.html', self.tmp / 'o.html')
        self.assertEqual(code, 0)
        self.assertEqual(len(j['warnings']), 1)
        self.assertIn('data-ring takes only "none"', j['warnings'][0])
        self.assertIn('.sbr .t (data-ring="no")', j['warnings'][0])
        self.assertIn('.sbr .u (data-caption with data-ring="none")', j['warnings'][0])

    def test_spotlight_example_assembles_clean_and_keeps_engine(self):
        out = self.tmp / 'spot.html'
        code, j = assemble(SCRIPTS.parent / 'references' / 'example_spotlight_fragment.html', out)
        self.assertEqual(code, 0)
        self.assertEqual(j['warnings'], [])
        self.assertEqual(j['slides'], 1)
        text = out.read_text(encoding='utf-8')
        for needle in ('--spot-dim:', '.spot[data-spot]{display:none!important}',
                       'function spotSync(', 'function spotLayout(', 'slides.forEach(spotInit);'):
            self.assertEqual(text.count(needle), 1, needle)

    def test_demo_deck_is_up_to_date(self):
        # consistency check (not an independent expectation): the committed demo deck
        # must be what assemble.py produces from the committed fragment and kit
        out = self.tmp / 'demo.html'
        code, j = assemble(ROOT / 'examples' / 'demo_fragment.html', out)
        self.assertEqual(code, 0)
        self.assertEqual(j['warnings'], [])
        self.assertEqual(out.read_bytes(), (ROOT / 'examples' / 'demo_deck.html').read_bytes())

    # ---- v1.1 lints: expectations follow from each fixture's header comment ----
    def test_fffd_warns_with_file_and_count(self):
        code, j = assemble(FIX / 'fffd.html', self.tmp / 'o.html')
        self.assertEqual(code, 0)
        self.assertEqual(len(j['warnings']), 1)
        self.assertIn('fffd.html: 2 U+FFFD', j['warnings'][0])

    def test_viewport_lint_skips_data_uris(self):
        code, j = assemble(FIX / 'vw_datauri.html', self.tmp / 'o.html')
        self.assertEqual(code, 0)
        self.assertEqual(len(j['warnings']), 1)
        self.assertTrue(j['warnings'][0].endswith(': 20vh'), j['warnings'])

    def test_duplicate_data_title_warns(self):
        code, j = assemble(FIX / 'dup_title.html', self.tmp / 'o.html')
        self.assertEqual(code, 0)
        self.assertEqual(len(j['warnings']), 1)
        self.assertIn('duplicate data-title', j['warnings'][0])
        self.assertTrue(j['warnings'][0].endswith(': Results'))

    def test_noncontiguous_sections_warn(self):
        code, j = assemble(FIX / 'sections_noncontig.html', self.tmp / 'o.html')
        self.assertEqual(code, 0)
        self.assertEqual(len(j['warnings']), 1)
        self.assertIn('not contiguous', j['warnings'][0])
        self.assertTrue(j['warnings'][0].endswith(': 1, 2'))

    def test_mixed_section_styles_warn_title_exempt(self):
        code, j = assemble(FIX / 'sections_mixed.html', self.tmp / 'o.html')
        self.assertEqual(code, 0)
        self.assertEqual(len(j['warnings']), 1)
        self.assertTrue(j['warnings'][0].endswith(
            ': name "Results", number "1", number · name "2 · Method"'), j['warnings'])

    def test_consistent_sections_no_warning(self):
        code, j = assemble(FIX / 'sections_ok.html', self.tmp / 'o.html')
        self.assertEqual((code, j['warnings']), (0, []))

    def test_unscoped_kit_css_warns(self):
        code, j = assemble(FIX / 'kit_css.html', self.tmp / 'o.html')
        self.assertEqual(code, 0)
        self.assertEqual(len(j['warnings']), 1)
        self.assertIn('kit_css.html: unscoped CSS restyles kit classes', j['warnings'][0])
        self.assertTrue(j['warnings'][0].endswith(
            ': .chip, .slide .panel .name, .chip.sa:hover, .card, .step.shown'), j['warnings'])

    def test_bad_caption_lane_warns(self):
        code, j = assemble(FIX / 'spot_badlane.html', self.tmp / 'o.html')
        self.assertEqual(code, 0)
        self.assertEqual(j['warnings'], ['data-caption-lane takes only "top" or "bottom": '
                                         '.sbl .t (data-caption-lane="middle")'])

    def test_good_caption_lane_no_warning(self):
        code, j = assemble(FIX / 'spot_lane.html', self.tmp / 'o.html')
        self.assertEqual((code, j['warnings']), (0, []))

    # ---- v1.1 options ----
    def test_title_option_escapes_and_replaces_once(self):
        out = self.tmp / 'o.html'
        code, j = assemble(FIX / 'one_slide.html', out, '--title', 'A <b> & c')
        self.assertEqual(code, 0)
        text = out.read_text(encoding='utf-8')
        self.assertIn('<title>A &lt;b&gt; &amp; c</title>', text)
        self.assertNotIn('Slide Kit</title>', text)

    def test_title_absent_keeps_kit_title(self):
        out = self.tmp / 'o.html'
        assemble(FIX / 'one_slide.html', out)
        self.assertIn('<title>Slide Kit</title>', out.read_text(encoding='utf-8'))

    def test_body_class_option(self):
        out = self.tmp / 'o.html'
        code, _ = assemble(FIX / 'one_slide.html', out, '--body-class', 'slide-numbers  progress')
        self.assertEqual(code, 0)
        self.assertIn('<body class="slide-numbers progress">', out.read_text(encoding='utf-8'))

    def test_order_file_relative_comments_blank(self):
        out = self.tmp / 'o.html'
        code, j = assemble('--kit', FIX / 'kit_tiny.html', '-o', out, '--order', FIX / 'order.txt')
        self.assertEqual(code, 0)
        self.assertEqual([pathlib.Path(f).name for f in j['fragments']], ['one_slide.html', 'clean.html'])
        self.assertEqual(j['slides'], 1 + 2)

    def test_order_then_positional_fragments(self):
        code, j = assemble('--kit', FIX / 'kit_tiny.html', '-o', self.tmp / 'o.html',
                           '--order', FIX / 'order.txt', FIX / 'dup_id.html')
        self.assertEqual(code, 0)
        self.assertEqual([pathlib.Path(f).name for f in j['fragments']],
                         ['one_slide.html', 'clean.html', 'dup_id.html'])

    def test_order_missing_fragment_exit_2(self):
        code, j = assemble('-o', self.tmp / 'o.html', '--order', FIX / 'order_missing.txt')
        self.assertEqual(code, 2)
        self.assertIn('not_built_yet.html', j['error'])

    def test_order_allow_missing_warns_and_skips(self):
        code, out, err = run('assemble.py', '--kit', FIX / 'kit_tiny.html', '-o', self.tmp / 'o.html',
                             '--order', FIX / 'order_missing.txt', '--allow-missing')
        j = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual([pathlib.Path(f).name for f in j['fragments']], ['one_slide.html', 'clean.html'])
        self.assertEqual([pathlib.Path(f).name for f in j['skipped']], ['not_built_yet.html'])
        self.assertEqual(len(j['warnings']), 1)
        self.assertIn('not_built_yet.html', j['warnings'][0])
        self.assertIn('WARNING', err)
        self.assertIn('not_built_yet.html', err)

    def test_order_without_out_exit_2(self):
        code, j = assemble('--order', FIX / 'order.txt', self.tmp / 'o.html')
        self.assertEqual(code, 2)

    def test_missing_order_file_exit_2(self):
        code, j = assemble('-o', self.tmp / 'o.html', '--order', FIX / 'no_such_order.txt')
        self.assertEqual(code, 2)
        self.assertIn('order file not found', j['error'])

    def test_master_first_and_not_repeated(self):
        out = self.tmp / 'o.html'
        code, j = assemble('--kit', FIX / 'kit_tiny.html', '-o', out, '--master', FIX / 'clean.html',
                           '--order', FIX / 'order.txt')
        self.assertEqual(code, 0)
        self.assertEqual([pathlib.Path(f).name for f in j['fragments']], ['clean.html', 'one_slide.html'])
        text = out.read_text(encoding='utf-8')
        self.assertEqual(text.count('class="slide fxa"'), 1)
        self.assertLess(text.index('class="slide fxa"'), text.index('class="slide x"'))

    def test_missing_master_exit_2(self):
        code, j = assemble('-o', self.tmp / 'o.html', '--master', FIX / 'nope.html', FIX / 'clean.html')
        self.assertEqual(code, 2)
        self.assertIn('master fragment not found', j['error'])

    def test_asset_base_rewrites(self):
        out = self.tmp / 'o.html'
        code, j = assemble(FIX / 'assets.html', out, '--asset-base', '../..')
        self.assertEqual(code, 0)
        self.assertEqual(j['asset_rewrites'], 5)
        text = out.read_text(encoding='utf-8')
        for needle in ('src="../../assets/a.png"', "href='../../assets/b.css'",
                       'url(../../assets/c.png)', 'srcset="../../assets/d.png 1x, ../../assets/e.png 2x"',
                       'src="http://example.org/assets/f.png"', 'data-x="assets/g.png"',
                       'see assets/ folder'):
            self.assertIn(needle, text)

    def test_no_new_keys_without_new_options(self):
        # backwards compatible JSON: the v1.0 keys only
        code, j = assemble(FIX / 'clean.html', self.tmp / 'o.html')
        self.assertEqual(set(j), {'out', 'kit', 'fragments', 'slides', 'chars', 'warnings'})

    def test_tex2svg_help_without_browser(self):
        code, out, err = run('tex2svg.py', '--help')
        self.assertEqual(code, 0)
        self.assertIn('--display', out)
        self.assertIn('--json', out)


# CI sets REQUIRE_PLAYWRIGHT=1 so a broken browser install fails instead of skipping.
@unittest.skipUnless(os.environ.get('REQUIRE_PLAYWRIGHT') == '1' or have_playwright(),
                     'Playwright + Chromium not installed')
class TestShot(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self.td.name)

    def tearDown(self):
        self.td.cleanup()

    def deck(self, frag):
        out = self.tmp / (frag + '.deck.html')
        code, _ = assemble(FIX / frag, out)
        self.assertEqual(code, 0)
        return out

    def shot(self, deck, *extra):
        code, out, err = run('shot.py', deck, self.tmp / 's' / 'f', *extra)
        return code, json.loads(out)

    def test_safe_area_ok(self):
        code, j = self.shot(self.deck('safe_area_ok.html'), '0', '--check')
        self.assertEqual(code, 0)
        self.assertTrue(j['check']['pass'])
        self.assertEqual(j['real_errors'], [])

    def test_safe_area_low_fails(self):
        code, j = self.shot(self.deck('safe_area_low.html'), '0', '--check')
        self.assertEqual(code, 1)
        self.assertFalse(j['check']['pass'])
        bottoms = [h['bottom'] for h in j['shots'][0]['below_safe_area']]
        self.assertTrue(any(abs(b - 680) <= 2 for b in bottoms), bottoms)  # 600 + 80, ±2 px

    def test_moving_arrow_detected(self):
        code, j = self.shot(self.deck('moving_arrow.html'), '2', '--check')
        self.assertEqual(code, 1)
        self.assertTrue(j['check']['arrows_moved'])

    def test_demo_deck_both_sizes(self):
        seq = ['9', '--check', '--click', '[data-goto=attn]', '--then', 'right', '--then', 'right',
               '--click', '#back', '--then', 'slide:5', '--then', 'right', '--then', 'right']
        for size in ('1280x720', '1024x768'):
            with self.subTest(size=size):
                code, j = self.shot(ROOT / 'examples' / 'demo_deck.html', *seq, '--size', size)
                self.assertEqual(code, 0, j.get('check'))
                self.assertTrue(j['check']['pass'])
                self.assertEqual(j['real_errors'], [])
                # 1 entry + 9 advances + 7 actions = 17 shots by construction of the sequence
                self.assertEqual(len(j['shots']), 17)
                # '#back' returns to the hub (slide 3) fully revealed (3 steps)
                back = j['shots'][13]
                self.assertEqual((back['slide'], back['step']), (3, 3))
                self.assertTrue(all('spot' not in s for s in j['shots']))  # no markers, no key

    # ---- spotlight: expected "spot" lists follow from each fixture's bucket order ----
    def test_spot_example_steps_and_back_both_sizes(self):
        frag = SCRIPTS.parent / 'references' / 'example_spotlight_fragment.html'
        deck = self.tmp / 'spx.html'
        self.assertEqual(assemble(frag, deck)[0], 0)
        b2, fig, b4 = (['.spx-box.b2'], ['.spx-fig img @0.6667,0.25,0.1667,0.25'],
                       ['.spx-b4', '.spx-past [no ring]'])   # step 4: ringed bar + ring-less hole
        want = [[], [], b2, fig, b4, [], b4, fig, b2]       # 5 advances, then 3 x left
        for size in ('1280x720', '1024x768'):
            with self.subTest(size=size):
                code, j = self.shot(deck, '5', '--check', '--then', 'left', '--then', 'left',
                                    '--then', 'left', '--size', size)
                self.assertEqual(code, 0, j.get('check'))
                self.assertEqual(j['real_errors'], [])
                self.assertEqual([s['spot'] for s in j['shots']], want)

    def test_spot_cross_slide_navigation(self):
        code, j = self.shot(self.deck('spot_nav.html'), '1', '--check', '--then', 'right',
                            '--then', 'left', '--then', 'left')
        self.assertEqual(code, 0, j.get('check'))
        got = [(s['slide'], s['step'], s.get('spot')) for s in j['shots']]
        self.assertEqual(got, [(1, 0, []), (1, 1, ['.n']), (2, 0, None), (1, 1, ['.n']), (1, 0, [])])

    def test_spot_drilldown_no_stale_spot(self):
        # the click on A happens while A's spotlight veil is up: it must reach A
        code, j = self.shot(self.deck('spot_drill.html'), '2', '--check',
                            '--click', '[data-goto=sdd]', '--then', 'right', '--click', '#back',
                            '--then', 'left', '--then', 'left')
        self.assertEqual(code, 0, j.get('check'))
        got = [(s['slide'], s['step'], s['spot']) for s in j['shots']]
        self.assertEqual(got, [(1, 0, []), (1, 1, []), (1, 2, ['.sd1 .ca']), (2, 0, []),
                               (2, 1, ['.sd2 .box']), (1, 3, []), (1, 2, ['.sd1 .ca']), (1, 1, [])])

    def test_spot_low_target_passes_check(self):
        code, j = self.shot(self.deck('spot_low.html'), '1', '--check')
        self.assertEqual(code, 0, j.get('check'))
        self.assertTrue(j['check']['pass'])
        self.assertEqual(j['shots'][1]['spot'], ['.slw .t'])

    def test_spot_missing_target_is_real_error(self):
        code, j = self.shot(self.deck('spot_missing.html'), '1')
        self.assertEqual(code, 1)
        self.assertEqual(len(j['real_errors']), 1)
        self.assertIn('data-spot=".nope"', j['real_errors'][0])

    def test_spot_bad_ring_is_real_error(self):
        code, j = self.shot(self.deck('spot_badring.html'), '1')
        self.assertEqual(code, 1)
        self.assertEqual(len(j['real_errors']), 2)
        self.assertIn('data-ring must be none', j['real_errors'][0])
        self.assertIn('data-caption is ignored', j['real_errors'][1])

    def test_spot_ring_none_steps(self):
        code, j = self.shot(self.deck('spot_noring.html'), '2', '--check', '--then', 'left')
        self.assertEqual(code, 0, j.get('check'))
        lit = ['.snr .dot', '.snr .cols [no ring]']
        self.assertEqual([s['spot'] for s in j['shots']], [[], lit, [], lit])

    def test_spot_ring_none_geometry_and_hole_both_sizes(self):
        # by construction of tests/fixtures/spot_noring.html (see its comment)
        js = """() => { const s=document.querySelector('#stage .slide.active');
          const veil=s.querySelector('.spot-g.on .spot-veil');
          const mask=veil&&document.getElementById(veil.getAttribute('mask').slice(5,-1));
          const box=e=>{const b=e.getBBox(); return [b.x,b.y,b.width,b.height];};
          return {rings:[...s.querySelectorAll('.spot-ring')].map(r=>[r.getAttribute('data-for'),box(r)]),
                  colsRing:s.querySelectorAll('.spot-ring[data-for=".snr .cols"]').length,
                  leads:s.querySelectorAll('.spot-lead').length, caps:s.querySelectorAll('.spot-cap').length,
                  holes:mask?[...mask.querySelectorAll('path[data-for]')].map(h=>[h.getAttribute('data-for'),
                         h.getAttribute('data-ring'),box(h)]):[]}; }"""
        from playwright.sync_api import sync_playwright
        deck = self.deck('spot_noring.html')
        with sync_playwright() as p:
            b = p.chromium.launch(args=['--no-sandbox', '--disable-gpu'])
            for w, h in ((1280, 720), (1024, 768)):
                pg = b.new_page(viewport={'width': w, 'height': h})
                pg.goto(deck.as_uri())
                pg.wait_for_timeout(700)
                s = min(w / 1280, h / 720)
                ox, oy = (w - 1280 * s) / 2, (h - 720 * s) / 2

                def clip(x, y, cw, ch):   # canvas rect -> screenshot bytes of that screen region
                    return pg.screenshot(clip={'x': ox + x * s, 'y': oy + y * s,
                                               'width': cw * s, 'height': ch * s})
                cols0, other0 = clip(110, 210, 580, 180), clip(910, 460, 180, 60)   # insets of 10
                pg.keyboard.press('ArrowRight')
                pg.wait_for_timeout(500)
                g = pg.evaluate(js)
                with self.subTest(size=(w, h)):
                    self.assertEqual([r[0] for r in g['rings']], ['.snr .dot'])  # the only ring
                    self.assertEqual(g['colsRing'], 0)
                    self.assertEqual((g['leads'], g['caps']), (0, 0))
                    self.assertEqual([(hh[0], hh[1]) for hh in g['holes']],
                                     [('.snr .dot', None), ('.snr .cols', 'none')])
                    for a, c in zip(g['rings'][0][1], (794, 254, 52, 52)):
                        self.assertAlmostEqual(a, c, delta=0.5)
                    for a, c in zip(g['holes'][1][2], (100, 200, 600, 200)):
                        self.assertAlmostEqual(a, c, delta=0.5)
                    # the hole is cut: inside .cols the pixels equal the unveiled entry frame,
                    # while .other (outside every hole) is whitened
                    self.assertEqual(clip(110, 210, 580, 180), cols0)
                    self.assertNotEqual(clip(910, 460, 180, 60), other0)
                pg.close()
            b.close()

    def test_spot_title_stays_bright_unless_opted_out_both_sizes(self):
        from playwright.sync_api import sync_playwright
        deck = self.deck('spot_title.html')
        js = """() => { const s=document.querySelector('#stage .slide.active'), v=s.querySelector('.spot-g.on .spot-veil');
          return v?document.getElementById(v.getAttribute('mask').slice(5,-1)).querySelectorAll('.spot-title-hole').length:-1; }"""
        with sync_playwright() as p:
            b = p.chromium.launch(args=['--no-sandbox', '--disable-gpu'])
            for w, h in ((1280, 720), (1024, 768)):
                pg = b.new_page(viewport={'width': w, 'height': h})
                pg.goto(deck.as_uri())
                pg.wait_for_timeout(700)
                s = min(w / 1280, h / 720)
                ox, oy = (w - 1280 * s) / 2, (h - 720 * s) / 2
                # a region inside the title's glyphs ("Title stays", 48px, starting at canvas x 64)
                region = {'x': ox + 66 * s, 'y': oy + 60 * s, 'width': 150 * s, 'height': 36 * s}
                entry = pg.screenshot(clip=region)
                with self.subTest(size=(w, h)):
                    pg.keyboard.press('ArrowRight')
                    pg.wait_for_timeout(500)
                    self.assertEqual(pg.evaluate(js), 1)
                    self.assertEqual(pg.screenshot(clip=region), entry)     # not whitened
                    pg.keyboard.press('ArrowRight')
                    pg.wait_for_timeout(500)
                    self.assertEqual(pg.evaluate(js), 0)                    # data-veil-title
                    self.assertNotEqual(pg.screenshot(clip=region), entry)  # whitened
                pg.close()
            b.close()

    def test_hint_fades_after_first_navigation_and_toggles_back(self):
        from playwright.sync_api import sync_playwright
        deck = self.deck('clean.html')
        op = "() => parseFloat(getComputedStyle(document.getElementById('hint')).opacity)"
        with sync_playwright() as p:
            b = p.chromium.launch(args=['--no-sandbox', '--disable-gpu'])
            pg = b.new_page(viewport={'width': 1280, 'height': 720})
            pg.goto(deck.as_uri())
            pg.wait_for_timeout(700)
            self.assertAlmostEqual(pg.evaluate(op), 0.7, delta=0.01)    # visible on load
            pg.keyboard.press('o')                                     # map is not navigation
            pg.keyboard.press('Escape')
            pg.wait_for_timeout(800)
            self.assertAlmostEqual(pg.evaluate(op), 0.7, delta=0.01)
            pg.keyboard.press('ArrowRight')
            pg.wait_for_timeout(800)
            self.assertEqual(pg.evaluate(op), 0)                       # gone after the first key
            pg.keyboard.press('ArrowRight')
            pg.wait_for_timeout(800)
            self.assertEqual(pg.evaluate(op), 0)                       # and stays gone
            pg.keyboard.press('?')
            pg.wait_for_timeout(800)
            self.assertAlmostEqual(pg.evaluate(op), 0.7, delta=0.01)    # ? brings it back
            pg.keyboard.press('h')
            pg.wait_for_timeout(800)
            self.assertEqual(pg.evaluate(op), 0)                       # H toggles it away
            pg2 = b.new_page(viewport={'width': 1280, 'height': 720})
            pg2.goto(deck.as_uri())
            pg2.wait_for_timeout(700)
            pg2.mouse.click(640, 400)
            pg2.wait_for_timeout(800)
            self.assertEqual(pg2.evaluate(op), 0)                      # a click hides it too
            b.close()

    def test_spot_geometry_both_sizes(self):
        # canvas rects by construction of tests/fixtures/spot_geom.html (see its comment)
        expect = {1: [], 2: [(90, 190, 320, 140)], 3: [(850, 235, 112.5, 150)],
                  4: [(100, 200, 300, 120), (100, 400, 300, 100)], 5: []}
        js = """() => { const s=document.querySelector('#stage .slide.active');
          const rings=[...s.querySelectorAll('.spot-g.on .spot-ring')];
          const veil=s.querySelector('.spot-g.on .spot-veil');
          return {canvas:rings.map(r=>{const b=r.getBBox(); return [b.x,b.y,b.width,b.height];}),
                  screen:rings.map(r=>{const b=r.getBoundingClientRect(); return [b.left,b.top,b.width,b.height];}),
                  lit:s.querySelectorAll('.spot-g.on').length,
                  holes:veil?document.querySelector(veil.getAttribute('mask').slice(4,-1)).querySelectorAll('path[data-for]').length:0,
                  thole:veil?document.querySelector(veil.getAttribute('mask').slice(4,-1)).querySelectorAll('.spot-title-hole').length:0,
                  caps:[...s.querySelectorAll('.spot-cap.on')].map(c=>[c.offsetLeft,c.offsetTop,c.offsetWidth,c.offsetHeight])}; }"""
        from playwright.sync_api import sync_playwright
        deck = self.deck('spot_geom.html')
        with sync_playwright() as p:
            b = p.chromium.launch(args=['--no-sandbox', '--disable-gpu'])
            for w, h in ((1280, 720), (1024, 768)):
                pg = b.new_page(viewport={'width': w, 'height': h})
                pg.goto(deck.as_uri())
                pg.wait_for_timeout(700)
                s = min(w / 1280, h / 720)
                ox, oy = (w - 1280 * s) / 2, (h - 720 * s) / 2
                for step in range(1, 6):
                    pg.keyboard.press('ArrowRight')
                    pg.wait_for_timeout(450)
                    g = pg.evaluate(js)
                    with self.subTest(size=(w, h), step=step):
                        self.assertEqual(len(g['canvas']), len(expect[step]))
                        self.assertEqual(g['lit'], 1 if expect[step] else 0)   # one shared veil
                        self.assertEqual(g['holes'], len(expect[step]))
                        self.assertEqual(g['thole'], 1 if expect[step] else 0)  # title kept bright
                        for got, scr, e in zip(g['canvas'], g['screen'], expect[step]):
                            for a, c in zip(got, e):
                                self.assertAlmostEqual(a, c, delta=0.5)
                            # the ring lands on the target on screen (letterboxed at 1024x768)
                            for a, c in zip(scr, (ox + e[0] * s, oy + e[1] * s, e[2] * s, e[3] * s)):
                                self.assertAlmostEqual(a, c, delta=1)
                        if step == 3:   # caption above the ring, centred on it, GAP 30
                            (cx, cy, cw, ch), = g['caps']
                            self.assertAlmostEqual(cy + ch, 235 - 30, delta=1)
                            self.assertAlmostEqual(cx + cw / 2, 850 + 112.5 / 2, delta=1)
                        else:
                            self.assertEqual(g['caps'], [])
                pg.close()
            b.close()

    # ---- v1.1: kit click guard, slide numbers, progress bar, halo, caption lanes ----
    STATE = "() => { const sl=[...document.querySelectorAll('#stage .slide')]; " \
            "const i=sl.findIndex(s=>s.classList.contains('active')); return [i+1, sl[i]._p||0]; }"

    def page(self, p, deck, w=1280, h=720):
        b = p.chromium.launch(args=['--no-sandbox', '--disable-gpu'])
        pg = b.new_page(viewport={'width': w, 'height': h})
        pg.goto(deck.as_uri())
        pg.wait_for_timeout(700)
        return b, pg

    def test_click_guard(self):
        # canvas = screen at 1280x720; blank area at (640, 520), the word "Selectable" at (160, 230)
        from playwright.sync_api import sync_playwright
        deck = self.deck('click_guard.html')
        sel = "() => String(getSelection()).trim()"
        with sync_playwright() as p:
            b, pg = self.page(p, deck)
            at = lambda: tuple(pg.evaluate(self.STATE))
            pg.mouse.click(640, 520)
            pg.wait_for_timeout(300)
            self.assertEqual(at(), (1, 1))                       # a plain click advances
            pg.mouse.move(300, 520)
            pg.mouse.down()
            pg.mouse.move(500, 520, steps=5)
            pg.mouse.up()
            pg.wait_for_timeout(300)
            self.assertEqual(at(), (1, 1))                       # a drag does not
            pg.mouse.dblclick(160, 230)
            pg.wait_for_timeout(300)
            self.assertEqual(pg.evaluate(sel), 'Selectable')
            self.assertEqual(at(), (1, 1))                       # a double-click on a word: net zero
            pg.keyboard.down('Shift')
            pg.mouse.click(560, 230)
            pg.keyboard.up('Shift')
            pg.wait_for_timeout(300)
            self.assertTrue(pg.evaluate(sel).startswith('Selectable words'))
            self.assertEqual(at(), (1, 1))                       # a click with text selected: none
            pg.mouse.click(640, 520)                             # collapses the selection, advances
            pg.wait_for_timeout(300)
            self.assertEqual(at(), (1, 2))
            b.close()

    def test_slide_numbers_and_progress_bar(self):
        # by construction of tests/fixtures/numbers.html (see its comment)
        from playwright.sync_api import sync_playwright
        deck = self.tmp / 'nb.html'
        code, _ = assemble(FIX / 'numbers.html', deck, '--body-class', 'slide-numbers progress')
        self.assertEqual(code, 0)
        js = """() => { const n=document.getElementById('kit-num'), d=document.getElementById('kit-bar');
          return [getComputedStyle(n).display==='none'?null:n.textContent,
                  parseFloat(d.firstElementChild.style.width), d.classList.contains('off'),
                  getComputedStyle(document.getElementById('prog')).display,
                  getComputedStyle(document.getElementById('dots')).display]; }"""
        want = [(None, 0, True), ('2', 100 / 6, False), ('2', 200 / 6, False), ('2', 300 / 6, False),
                (None, 400 / 6, False), ('4', 500 / 6, False), ('4', 100, False)]
        with sync_playwright() as p:
            for w, h in ((1280, 720), (1024, 768)):
                b, pg = self.page(p, deck, w, h)
                for k, (num, width, off) in enumerate(want):
                    if k:
                        pg.keyboard.press('ArrowRight')
                        pg.wait_for_timeout(150)
                    got = pg.evaluate(js)
                    with self.subTest(size=(w, h), k=k):
                        self.assertEqual(got[0], num)
                        self.assertAlmostEqual(got[1], width, delta=0.01)
                        self.assertEqual(got[2], off)
                        self.assertEqual(got[3:], ['none', 'none'])   # the bar replaces top bar + dots
                pg.keyboard.press('ArrowLeft')                        # back from the end: 5/6 again
                pg.wait_for_timeout(150)
                self.assertAlmostEqual(pg.evaluate(js)[1], 500 / 6, delta=0.01)
                b.close()

    def test_options_off_by_default(self):
        from playwright.sync_api import sync_playwright
        js = """() => ['kit-num','kit-bar','prog','dots'].map(i=>getComputedStyle(document.getElementById(i)).display)"""
        with sync_playwright() as p:
            b, pg = self.page(p, self.deck('numbers.html'))
            pg.keyboard.press('ArrowRight')
            pg.wait_for_timeout(150)
            self.assertEqual(pg.evaluate(js), ['none', 'none', 'block', 'flex'])
            b.close()

    def test_halo_class(self):
        from playwright.sync_api import sync_playwright
        js = """() => [...document.querySelectorAll('.hl .halo, .hl .plain')].map(e=>{ const c=getComputedStyle(e);
          return [e.tagName.toLowerCase(), e.getAttribute('class'), c.paintOrder, c.stroke, c.textShadow==='none']; })"""
        with sync_playwright() as p:
            b, pg = self.page(p, self.deck('halo.html'))
            got = pg.evaluate(js)
            b.close()
        self.assertEqual([g[:2] for g in got], [['text', 'halo'], ['text', 'plain'], ['span', 'halo'],
                                               ['span', 'plain']])
        self.assertTrue(got[0][2].startswith('stroke'))               # outline painted under the fill
        self.assertEqual(got[0][3], 'rgb(255, 255, 255)')
        self.assertEqual(got[1][3], 'none')                           # plain SVG text: no stroke
        self.assertTrue(got[0][4])                                    # no text-shadow on SVG text
        self.assertFalse(got[2][4])                                   # HTML halo: text-shadow
        self.assertTrue(got[3][4])

    def test_spot_caption_lanes_both_sizes(self):
        # by construction of tests/fixtures/spot_lane.html (see its comment)
        from playwright.sync_api import sync_playwright
        js = """() => { const s=document.querySelector('#stage .slide.active'), c=s.querySelector('.spot-cap.on');
          const l=s.querySelector('.spot-g.on .spot-lead');
          return [c.offsetLeft,c.offsetTop,c.offsetWidth,c.offsetHeight,
                  (l.getAttribute('d').match(/-?[\\d.]+/g)||[]).map(Number)]; }"""
        deck = self.deck('spot_lane.html')
        with sync_playwright() as p:
            for w, h in ((1280, 720), (1024, 768)):
                b, pg = self.page(p, deck, w, h)
                for step in (1, 2):
                    pg.keyboard.press('ArrowRight')
                    pg.wait_for_timeout(500)
                    x, y, cw, ch, d = pg.evaluate(js)
                    with self.subTest(size=(w, h), step=step):
                        self.assertAlmostEqual(x + cw / 2, 600, delta=1)
                        self.assertEqual(len(d), 4)
                        if step == 1:
                            self.assertAlmostEqual(y, 16, delta=0.5)
                            self.assertAlmostEqual(d[1], 16 + ch, delta=1)
                            self.assertAlmostEqual(d[3], 289, delta=0.5)
                        else:
                            self.assertAlmostEqual(y + ch, 612, delta=0.5)
                            self.assertAlmostEqual(d[1], y, delta=1)
                            self.assertAlmostEqual(d[3], 411, delta=0.5)
                b.close()

    def test_spot_bad_lane_is_real_error(self):
        code, j = self.shot(self.deck('spot_badlane.html'), '0', '--wait', '300')
        self.assertEqual(code, 1)
        self.assertEqual(len(j['real_errors']), 1)
        self.assertIn('data-caption-lane must be top | bottom', j['real_errors'][0])

    # ---- v1.1 shot.py options ----
    def test_all_advances_to_the_last_step(self):
        deck = self.deck('all_steps.html')
        code, j = self.shot(deck, '--all', '--wait', '300')
        self.assertEqual(code, 0)
        self.assertEqual([(s['slide'], s['step']) for s in j['shots']],
                         [(1, 0), (1, 1), (1, 2), (2, 0), (3, 0), (3, 1)])
        code, j = self.shot(deck, '--all', '--start', '3', '--wait', '300')
        self.assertEqual(code, 0, j)
        self.assertEqual([(s['slide'], s['step']) for s in j['shots']], [(3, 0), (3, 1)])

    def test_json_file_keeps_stdout_clean(self):
        jf = self.tmp / 'out' / 'r.json'
        code, out, err = run('shot.py', self.deck('clean.html'), self.tmp / 's' / 'f', '0',
                             '--wait', '300', '--json', jf)
        self.assertEqual(code, 0)
        self.assertEqual(out, '')
        self.assertEqual(len(json.loads(jf.read_text(encoding='utf-8'))['shots']), 1)
        self.assertIn('REAL ERRORS: NONE', err)
        self.assertIn('wrote', err)

    def test_box_fit_overflow_fails_at_both_sizes(self):
        code, j = self.shot(self.deck('boxfit.html'), '0', '--check', '--wait', '300')
        self.assertEqual(code, 1)
        self.assertFalse(j['check']['pass'])
        self.assertEqual([o['text'] for o in j['shots'][0]['overflow']], ['overflowing label that runs'])
        self.assertEqual(j['check']['overflow'], [j['shots'][0]['png']])
        extra = j['check']['sizes']['1906x1000']
        self.assertFalse(extra['pass'])
        self.assertEqual([o['text'] for o in extra['shots'][0]['overflow']], ['overflowing label that runs'])
        self.assertTrue(pathlib.Path(extra['shots'][0]['png']).is_file())   # PNG kept for a failure

    def test_extra_check_size_catches_viewport_only_overflow(self):
        deck = self.deck('boxfit_wide.html')
        code, j = self.shot(deck, '0', '--check', '--wait', '300')
        self.assertEqual(code, 1)
        self.assertEqual(j['check']['overflow'], [])                  # fine at 1280x720
        self.assertFalse(j['check']['sizes']['1906x1000']['pass'])
        code, j = self.shot(deck, '0', '--check', '--check-size', 'none', '--wait', '300')
        self.assertEqual(code, 0)
        self.assertEqual(j['check']['sizes'], {})

    def test_small_text_warns_without_failing(self):
        code, out, err = run('shot.py', self.deck('small_text.html'), self.tmp / 's' / 'f', '0',
                             '--check', '--wait', '300')
        j = json.loads(out)
        self.assertEqual(code, 0, j['check'])
        self.assertTrue(j['check']['pass'])
        self.assertEqual(sorted(s['px'] for s in j['shots'][0]['small_text']), [6, 7, 10])
        self.assertIn('WARNING: text below 12 px', err)

    def test_check_survives_svg_title_and_foreign_object(self):
        code, out, err = run('shot.py', self.deck('svg_mixed.html'), self.tmp / 's' / 'f', '0',
                             '--check', '--wait', '300')
        self.assertEqual(code, 0, err)
        j = json.loads(out)
        self.assertEqual(j['real_errors'], [])
        self.assertTrue(j['check']['pass'])
        self.assertEqual([(s['text'], s['px']) for s in j['shots'][0]['small_text']], [('eight', 8)])

    def test_default_wait_is_1200(self):
        code, out, err = run('shot.py', '--help')
        self.assertIn('default 1200', out.replace('\n', ' '))

    def test_hang_stops_with_partial_result(self):
        code, j = self.shot(self.deck('hang_loop.html'), '4', '--step-timeout', '5')
        self.assertEqual(code, 1)
        self.assertTrue(j['hang'])
        self.assertEqual(j['stuck_at'], 'advance 2 (ArrowRight)')
        self.assertEqual(len(j['shots']), 2)   # entry + advance 1

    def test_help_without_browser(self):
        # shot.py --help must work without launching a browser
        code, out, err = run('shot.py', '--help')
        self.assertEqual(code, 0)
        self.assertIn('--check', out)


if __name__ == '__main__':
    unittest.main()
