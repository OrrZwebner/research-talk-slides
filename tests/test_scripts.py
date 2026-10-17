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

    def test_demo_deck_is_up_to_date(self):
        # consistency check (not an independent expectation): the committed demo deck
        # must be what assemble.py produces from the committed fragment and kit
        out = self.tmp / 'demo.html'
        code, j = assemble(ROOT / 'examples' / 'demo_fragment.html', out)
        self.assertEqual(code, 0)
        self.assertEqual(j['warnings'], [])
        self.assertEqual(out.read_bytes(), (ROOT / 'examples' / 'demo_deck.html').read_bytes())


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

    def test_help_without_browser(self):
        # shot.py --help must work without launching a browser
        code, out, err = run('shot.py', '--help')
        self.assertEqual(code, 0)
        self.assertIn('--check', out)


if __name__ == '__main__':
    unittest.main()
