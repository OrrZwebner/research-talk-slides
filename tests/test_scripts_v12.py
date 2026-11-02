#!/usr/bin/env python3
"""Tests for the v1.2 script features: assemble.py (script-body lints, refused calls, size
lints, data-offpath contiguity, --check-assets), shot.py (--load-timeout, slot lock,
--frames, --click fallback, failed-asset warning, data-small-ok) and anim.py (transfer,
label_clear, text_box).

As in test_scripts.py, every expected value follows from how the synthetic fixture
(tests/fixtures/s12_*, or a fragment generated in the test) was built, never from
recorded output. Run:  python3 -m unittest discover -s tests -p 'test_scripts_v12.py' -v
The browser tests are skipped without Playwright + Chromium unless REQUIRE_PLAYWRIGHT=1.
"""
import doctest
import fcntl
import importlib
import io
import json
import math
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / 'skills' / 'research-talk-slides' / 'scripts'
FIX = ROOT / 'tests' / 'fixtures'
START = '<!-- ============================ SLIDES:START ============================ -->'
sys.path.insert(0, str(SCRIPTS))
import anim  # noqa: E402


def run(script, *args, env=None):
    r = subprocess.run([sys.executable, str(SCRIPTS / script)] + [str(a) for a in args],
                       capture_output=True, text=True, env=env)
    return r.returncode, r.stdout, r.stderr


def assemble(*args):
    code, out, err = run('assemble.py', *args)
    return code, json.loads(out), err


def have_playwright():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch().close()
        return True
    except Exception:
        return False


PLAYWRIGHT = os.environ.get('REQUIRE_PLAYWRIGHT') == '1' or have_playwright()


class Tmp(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self.td.name)

    def tearDown(self):
        self.td.cleanup()


# ----------------------------------------------------------------------------- assemble.py
class TestAssembleV12(Tmp):
    def test_script_bodies_skipped_by_markup_lints(self):
        code, j, _ = assemble(FIX / 's12_script_text.html', self.tmp / 'o.html')
        self.assertEqual(code, 0)
        self.assertEqual(len(j['warnings']), 1, j['warnings'])
        self.assertTrue(j['warnings'][0].startswith('viewport units'))
        self.assertTrue(j['warnings'][0].endswith(': 50vw'))
        self.assertEqual(j['slides'], 1)                   # the '<section class="slide' JS string is not one

    def test_offpath_slides_ignored_by_contiguity(self):
        code, j, _ = assemble(FIX / 's12_offpath.html', self.tmp / 'o.html')
        self.assertEqual(code, 0)
        self.assertEqual(j['warnings'], [])
        self.assertEqual(j['slides'], 6)

    def test_offpath_does_not_hide_a_real_recurrence(self):
        code, j, _ = assemble(FIX / 's12_offpath_noncontig.html', self.tmp / 'o.html')
        self.assertEqual(code, 0)
        self.assertEqual(len(j['warnings']), 1, j['warnings'])
        self.assertIn('not contiguous', j['warnings'][0])
        self.assertTrue(j['warnings'][0].endswith(': 1 · Intro'))

    def frag(self, name, body):
        p = self.tmp / name
        p.write_text('<section class="slide big" data-title="Big">' + body + '</section>', encoding='utf-8')
        return p

    def test_rect_count_lint(self):
        f = self.frag('r2001.html', '<svg>' + '<rect x="1" y="1" width="2" height="2"/>' * 2001 + '</svg>')
        code, j, _ = assemble(f, self.tmp / 'o.html')
        self.assertEqual(code, 0)
        self.assertEqual(len(j['warnings']), 1, j['warnings'])
        self.assertIn('2001 <rect> elements (over 2000', j['warnings'][0])
        ok = self.frag('r2000.html', '<svg>' + '<rect/>' * 2000 + '<!-- <rect/> --></svg>'
                       '<script>const r = "<rect/>";</script>')
        code, j, _ = assemble(ok, self.tmp / 'o2.html')
        self.assertEqual(j['warnings'], [])                # exactly 2000; comments and JS do not count

    def test_fragment_size_lint(self):
        filler = '<p>' + 'x' * 1000 + '</p>'
        prefix = len('<section class="slide big" data-title="Big"></section>')
        big = self.frag('big.html', filler * 500 + 'y' * (512000 - 500 * len(filler) - prefix + 1))
        self.assertEqual(big.stat().st_size, 512001)
        code, j, _ = assemble(big, self.tmp / 'o.html')
        self.assertEqual(code, 0)
        self.assertEqual(len(j['warnings']), 1, j['warnings'])
        self.assertIn('over the 512 KB fragment budget', j['warnings'][0])
        edge = self.frag('edge.html', filler * 500 + 'y' * (512000 - 500 * len(filler) - prefix))
        self.assertEqual(edge.stat().st_size, 512000)
        code, j, _ = assemble(edge, self.tmp / 'o2.html')
        self.assertEqual(j['warnings'], [])

    def test_check_assets(self):
        out = self.tmp / 'deck' / 'o.html'
        (out.parent / 'assets').mkdir(parents=True)
        (out.parent / 'assets' / 'logo.svg').write_text('<svg/>')
        (out.parent / 'assets' / 'a b.png').write_bytes(b'')
        (out.parent / 'img').mkdir()
        (out.parent / 'img' / 'one.png').write_bytes(b'')
        code, j, _ = assemble('--check-assets', FIX / 's12_assets.html', out)
        self.assertEqual(code, 0)
        self.assertEqual(j['assets'], {'relative': 6, 'missing': ['assets/missing.woff2', 'img/two.png',
                                                                  'paper.pdf']})
        self.assertEqual(len(j['warnings']), 1, j['warnings'])
        self.assertTrue(j['warnings'][0].endswith(': assets/missing.woff2, img/two.png, paper.pdf'))

    def test_check_assets_after_asset_base(self):
        # a preview in build/NN/ with --asset-base ../.. resolves assets/ of the talk root
        root = self.tmp / 'talk'
        (root / 'assets').mkdir(parents=True)
        (root / 'assets' / 'logo.svg').write_text('<svg/>')
        out = root / 'build' / '07' / 'o.html'
        code, j, _ = assemble('--check-assets', '--asset-base', '../..', FIX / 's12_assets.html', out)
        self.assertEqual(code, 0)
        self.assertNotIn('../../assets/logo.svg', j['assets']['missing'])
        self.assertIn('../../assets/missing.woff2', j['assets']['missing'])

    def test_below_title_caption_lane_accepted(self):
        code, j, _ = assemble(FIX / 's12_lane_below.html', self.tmp / 'o.html')
        self.assertEqual(code, 0)
        self.assertEqual(j['warnings'], [])
        code, j, _ = assemble(FIX / 'spot_badlane.html', self.tmp / 'o2.html')
        self.assertTrue(any('"top", "bottom" or "below-title"' in w for w in j['warnings']), j['warnings'])

    def test_no_new_keys_without_new_options(self):
        code, j, _ = assemble(FIX / 's12_offpath.html', self.tmp / 'o.html')
        self.assertEqual(set(j), {'out', 'kit', 'fragments', 'slides', 'chars', 'warnings'})

    # refused calls ------------------------------------------------------------------
    def deck_at(self, path):
        code, _, _ = assemble(FIX / 'clean.html', path)
        self.assertEqual(code, 0)
        return path.read_text(encoding='utf-8')

    def test_two_fragments_without_o_refused_and_second_untouched(self):
        a, b = self.tmp / 'a_fragment.html', self.tmp / 'b_fragment.html'
        a.write_text((FIX / 'one_slide.html').read_text())
        b.write_text((FIX / 'clean.html').read_text())
        before = b.read_bytes()
        code, j, _ = assemble(a, b)
        self.assertEqual(code, 2)
        self.assertIn('is a slide fragment', j['error'])
        self.assertEqual(b.read_bytes(), before)
        self.assertNotIn('stale_moved_to', j)

    def test_several_fragments_without_o_moves_the_stale_deck(self):
        deck = self.tmp / 'deck.html'
        old = self.deck_at(deck)
        code, j, err = assemble(FIX / 'one_slide.html', FIX / 'clean.html', deck)
        self.assertEqual(code, 2)
        self.assertIn('without -o', j['error'])
        self.assertFalse(deck.exists())
        stale = pathlib.Path(j['stale_moved_to'])
        self.assertEqual(stale, self.tmp / 'deck.html.stale')
        self.assertEqual(stale.read_text(encoding='utf-8'), old)
        self.assertIn('moved to', err)

    def test_refused_with_o_moves_the_stale_deck(self):
        deck = self.tmp / 'deck.html'
        self.deck_at(deck)
        code, j, _ = assemble('-o', deck, FIX / 'clean.html', FIX / 'does_not_exist.html')
        self.assertEqual(code, 2)
        self.assertIn('fragment not found', j['error'])
        self.assertFalse(deck.exists())
        self.assertTrue((self.tmp / 'deck.html.stale').exists())

    def test_refused_writes_nothing(self):
        out = self.tmp / 'new' / 'deck.html'
        code, j, _ = assemble('-o', out, FIX / 'does_not_exist.html')
        self.assertEqual(code, 2)
        self.assertFalse(out.parent.exists())
        self.assertNotIn('stale_moved_to', j)

    def test_refusal_never_moves_a_non_deck(self):
        other = self.tmp / 'notes.html'
        other.write_text('<p>my notes</p>')
        code, j, _ = assemble(FIX / 'one_slide.html', FIX / 'clean.html', other)
        self.assertEqual(code, 2)
        self.assertEqual(other.read_text(), '<p>my notes</p>')
        self.assertNotIn('stale_moved_to', j)

    def test_reassembling_over_an_existing_deck_still_works(self):
        deck = self.tmp / 'deck.html'
        self.deck_at(deck)
        code, j, _ = assemble(FIX / 'one_slide.html', deck)
        self.assertEqual(code, 0)
        self.assertIn('class="slide x"', deck.read_text(encoding='utf-8'))
        self.assertFalse((self.tmp / 'deck.html.stale').exists())

    def test_help_mentions_new_option(self):
        code, out, _ = run('assemble.py', '--help')
        self.assertEqual(code, 0)
        self.assertIn('--check-assets', out)


# ----------------------------------------------------------------------------- anim.py
class TestAnim(unittest.TestCase):
    def test_docstring_examples(self):
        r = doctest.testmod(anim)
        self.assertGreaterEqual(r.attempted, 15)
        self.assertEqual(r.failed, 0)

    def test_module_runs_its_examples(self):
        code, out, _ = run('anim.py')
        self.assertEqual(code, 0)
        self.assertIn('0 failed', out)

    def test_transfer_timings(self):
        tr = anim.transfer((0, 0), (100, 0), '<circle r="4"/>', t0=1.0, dur=2.0)
        self.assertAlmostEqual(tr.t_cut, 1.9)              # t0 + 0.9 s snip
        self.assertAlmostEqual(tr.t_fly, 2.0)              # + 0.1 s
        self.assertAlmostEqual(tr.t_land, 2.0 + 2.0 * 0.8)
        self.assertAlmostEqual(tr.t_end, max(tr.t_land + 0.6, 2.0 + 2.0 * 0.9))
        fast = anim.transfer((0, 0), (100, 0), '<circle r="4"/>', t0=1.0, dur=2.0, speed=2)
        for k in ('t_cut', 't_fly', 't_land', 't_end'):
            self.assertAlmostEqual(getattr(fast, k), getattr(tr, k) / 2)
        self.assertIn('animation:xfer-fly 1s', fast.css)

    def test_transfer_without_cut_or_recolour(self):
        tr = anim.transfer((0, 0), (100, 0), '<circle r="4"/>', t0=0.5, cut=False, uid='q')
        self.assertAlmostEqual(tr.t_fly, 0.5)
        for part in ('q-ring', 'q-cutr', 'q-bla', 'q-done', 'q-lring'):
            self.assertNotIn(part, tr.svg)
        self.assertNotIn('@keyframes q-snipa', tr.css)

    def test_transfer_names_are_uid_scoped(self):
        import re
        tr = anim.transfer((10, 10), (300, 80), '<rect class="pl" x="-5" y="-5" width="10" height="10"/>',
                           recolour='red', recolour_target='.cell-b', uid='mv', scope='.s7')
        own = set(re.findall(r'class="([^"]+)"', tr.svg)) - {'pl'}
        self.assertTrue(all(c == 'mv' or c.startswith('mv-') for c in own), own)
        self.assertTrue(all(k.startswith('mv-') for k in re.findall(r'@keyframes ([\w-]+)', tr.css)))
        rules = [r for r in tr.css.split('\n') if r and not r.startswith('@')]
        self.assertTrue(all(r.startswith('.s7') for r in rules), rules)
        self.assertIn('.s7:has(.step.shown .mv-fly) .cell-b{fill:red;', tr.css)

    def test_transfer_trigger_for_autoplay(self):
        tr = anim.transfer((0, 0), (100, 0), '<circle r="4"/>', uid='ap', trigger='.slide.playing')
        self.assertIn('.slide.playing .ap-fly{animation:', tr.css)
        self.assertNotIn('.step.shown', tr.css)

    def test_transfer_slide_trigger_joins_the_scope(self):
        tr = anim.transfer((0, 0), (100, 0), '<circle r="4"/>', uid='u', scope='.x', trigger='.slide.playing',
                           recolour='red', recolour_target='.cell')
        self.assertIn('.x.slide.playing .u-fly{animation:', tr.css)
        self.assertNotIn('.x .slide.playing', tr.css)
        self.assertIn('.x.slide.playing .cell{fill:red;', tr.css)
        st = anim.transfer((0, 0), (100, 0), '<circle r="4"/>', uid='u', scope='.x')
        self.assertIn('.x .step.shown .u-fly{animation:', st.css)       # a descendant trigger is unchanged
        sl = anim.transfer((0, 0), (100, 0), '<circle r="4"/>', uid='u', scope='.x', trigger='.slides-wrap .on')
        self.assertIn('.x .slides-wrap .on .u-fly', sl.css)               # ".slides-wrap" is not ".slide"

    def test_transfer_points_follow_given_controls(self):
        tr = anim.transfer((0, 0), (90, 0), '<circle r="4"/>', c1=(30, 60), c2=(60, 60))
        self.assertEqual(len(tr.points), 201)
        self.assertEqual(tr.points[0], (0.0, 0.0))
        self.assertEqual(tr.points[-1], (90.0, 0.0))
        mid = tr.points[100]                               # B(1/2) = (A + 3 c1 + 3 c2 + B) / 8
        self.assertAlmostEqual(mid[0], 45.0)
        self.assertAlmostEqual(mid[1], 45.0)

    def test_transfer_bad_args(self):
        with self.assertRaises(ValueError):
            anim.transfer((0, 0), (1, 1), '', recolour_target='.x')
        with self.assertRaises(ValueError):
            anim.transfer((0, 0), (1, 1), '', speed=0)

    def test_label_clear_exact_segment_distance(self):
        # a horizontal segment y=100 from x=0 to 200; a label box 10 px above it
        seg = [(0, 100), (200, 100)]
        box = (90, 80, 110, 90)
        self.assertAlmostEqual(anim.label_clear([box], [seg], 10), 10.0)
        with self.assertRaises(anim.ClearanceError) as cm:
            anim.label_clear([box], [seg], 10.5)
        self.assertEqual(len(cm.exception.violations), 1)

    def test_label_clear_segment_crossing_box_is_zero(self):
        # the segment's sample points (its two ends) are far, but it passes through the box
        with self.assertRaises(anim.ClearanceError) as cm:
            anim.label_clear([{'text': 'v', 'box': (95, 95, 105, 105)}], [{'name': 'arc', 'points': [(0, 0), (200, 200)]}], 1)
        self.assertEqual(cm.exception.violations[0][:2], ('v', 'arc'))
        self.assertEqual(cm.exception.violations[0][2], 0.0)

    def test_label_clear_between_labels(self):
        a, b = (0, 0, 10, 10), (13, 0, 23, 10)             # 3 px apart
        with self.assertRaises(anim.ClearanceError):
            anim.label_clear([a, b], [], 4)
        self.assertEqual(anim.label_clear([a, b], [(100, 100)], 4, between_labels=False),
                         math.hypot(100 - 23, 90))          # b's corner (23, 10) is nearer

    def test_label_clear_on_transfer_path(self):
        tr = anim.transfer((100, 300), (500, 300), '<circle r="4"/>')
        peak = min(tr.points, key=lambda q: q[1])
        on_arc = anim.text_box(peak[0], peak[1], '0.5')
        with self.assertRaises(anim.ClearanceError):
            anim.label_clear([on_arc], [tr.points], 4)
        above = anim.text_box(peak[0], peak[1] - 20, '0.5')
        self.assertGreaterEqual(anim.label_clear([above], [tr.points], 4), 4)

    def test_label_clear_rejects_bad_shapes(self):
        with self.assertRaises(ValueError):
            anim.label_clear([(1, 2)], [], 1)              # a point is not a label box
        with self.assertRaises(ValueError):
            anim.label_clear([(0, 0, 1, 1)], [{'name': 'x'}], 1)


# ----------------------------------------------------------------------------- shot.py
class TestSlotLock(Tmp):
    """acquire_slot() in-process: no browser needed."""

    def load(self):
        return importlib.import_module('shot')

    def test_unlimited_and_free_slot(self):
        shot = self.load()
        env = {'SLIDES_SHOT_SLOTS': '0', 'SLIDES_SHOT_LOCK_DIR': str(self.tmp)}
        with unittest.mock.patch.dict(os.environ, env):
            self.assertEqual(shot.acquire_slot(io.StringIO()), (None, 0.0))
        env['SLIDES_SHOT_SLOTS'] = '2'
        with unittest.mock.patch.dict(os.environ, env):
            fd, waited = shot.acquire_slot(io.StringIO())
            self.assertIsNotNone(fd)
            self.assertLess(waited, 0.5)
            fd2, _ = shot.acquire_slot(io.StringIO())       # the second of two slots
            self.assertNotEqual(fd, fd2)
            os.close(fd)
            os.close(fd2)
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), ['slot-0', 'slot-1'])

    def test_waits_with_a_message_until_released(self):
        shot = self.load()
        env = {'SLIDES_SHOT_SLOTS': '1', 'SLIDES_SHOT_LOCK_DIR': str(self.tmp)}
        holder = os.open(str(self.tmp / 'slot-0'), os.O_RDONLY | os.O_CREAT, 0o666)
        fcntl.flock(holder, fcntl.LOCK_EX)
        threading.Timer(1.5, lambda: os.close(holder)).start()
        log = io.StringIO()
        with unittest.mock.patch.dict(os.environ, env):
            fd, waited = shot.acquire_slot(log)
        os.close(fd)
        self.assertGreaterEqual(waited, 1.3)
        self.assertIn('waiting for a Chromium slot', log.getvalue())


@unittest.skipUnless(PLAYWRIGHT, 'Playwright + Chromium not installed')
class TestShotV12(Tmp):
    def deck(self, frag):
        out = self.tmp / (frag + '.deck.html')
        code, _, _ = assemble(FIX / frag, out)
        self.assertEqual(code, 0)
        return out

    def shot(self, deck, *extra, env=None):
        code, out, err = run('shot.py', deck, self.tmp / 's' / 'f', *extra, env=env)
        return code, json.loads(out), err

    def test_help_documents_new_options(self):
        code, out, _ = run('shot.py', '--help')
        self.assertEqual(code, 0)
        flat = ' '.join(out.split())
        for needle in ('--load-timeout', 'larger of 30 and --step-timeout', '--frames',
                       'SLIDES_SHOT_SLOTS', 'default 2; 0 = no limit'):
            self.assertIn(needle, flat)

    def test_load_timeout_reports_a_load_hang(self):
        code, j, err = self.shot(self.deck('s12_autoplay.html'), '0', '--load-timeout', '0.001')
        self.assertEqual(code, 1)
        self.assertTrue(j['hang'])
        self.assertEqual(j['stuck_at'], 'load')
        self.assertEqual(j['shots'], [])
        self.assertIn('--load-timeout', err)

    def test_frames_after_waiting_for_a_slot(self):
        # one Chromium run checks both: the slot lock (held by this test for 2 s) and --frames
        env = dict(os.environ, SLIDES_SHOT_SLOTS='1', SLIDES_SHOT_LOCK_DIR=str(self.tmp / 'locks'))
        (self.tmp / 'locks').mkdir()
        holder = os.open(str(self.tmp / 'locks' / 'slot-0'), os.O_RDONLY | os.O_CREAT, 0o666)
        fcntl.flock(holder, fcntl.LOCK_EX)
        threading.Timer(2.0, lambda: os.close(holder)).start()
        code, j, err = self.shot(self.deck('s12_autoplay.html'), '0', '--frames', '3000,0', '--wait', '300',
                                 env=env)
        self.assertEqual(code, 0, err)
        self.assertIn('waiting for a Chromium slot', err)
        self.assertGreaterEqual(j['slot_wait_s'], 1.5)
        fr = [s for s in j['shots'] if s['action'] == 'frame']
        self.assertEqual([s['t_ms'] for s in fr], [0, 3000])           # sorted
        self.assertEqual([pathlib.Path(s['png']).name for s in fr], ['f_00_t00000.png', 'f_00_t03000.png'])
        for s in fr:
            self.assertGreaterEqual(s['t_actual_ms'], s['t_ms'])
            self.assertLess(s['t_actual_ms'], s['t_ms'] + 1500)
            self.assertEqual((s['slide'], s['step']), (1, 0))
        self.assertEqual(j['shots'][-1]['action'], 'entry')
        a, b = (pathlib.Path(s['png']).read_bytes() for s in fr)
        self.assertNotEqual(a, b)                                      # the square moved

    def test_start_by_id_title_and_position(self):
        deck = self.deck('s12_start.html')
        for args, want in ((('--start-id', 'tgt'), 3), (('--start-title', 'Target'), 3),
                           (('--start', '3'), 3), (('--start-id', 'bk'), 2)):
            code, j, err = self.shot(deck, '0', '--wait', '300', *args)
            self.assertEqual(code, 0, (args, err))
            self.assertEqual(j['shots'][0]['slide'], want, args)

    def test_start_by_name_errors(self):
        deck = self.deck('s12_start.html')
        for args, msg in ((('--start-id', 'nope'), 'no slide with data-id="nope"'),
                          (('--start-title', 'Twin'), '2 slides with data-title="Twin"'),
                          (('--start-id', 'bk', '--start-title', 'Target'), 'name different slides')):
            code, j, err = self.shot(deck, '0', '--wait', '300', *args)
            self.assertEqual(code, 1, args)
            self.assertIn(msg, j['error'])
            self.assertEqual(j['shots'], [])
        code, out, err = run('shot.py', deck, self.tmp / 'f', '--start', '2', '--start-id', 'bk')
        self.assertNotEqual(code, 0)
        self.assertIn('does not combine', json.loads(err)['error'])

    def test_help_explains_start_and_json(self):
        code, out, _ = run('shot.py', '--help')
        flat = ' '.join(out.split())
        for needle in ('K-th slide in document order', '--start-id', '--start-title',
                       'FILE (a path, required)'):
            self.assertIn(needle, flat)

    def test_transfer_autoplay_trigger_in_the_browser(self):
        """trigger='.slide.playing' + scope on a data-autoplay slide: the flight runs on entry and
        ends with the landing mark and the recoloured target (S1: the descendant form never fired)."""
        from playwright.sync_api import sync_playwright
        tr = anim.transfer((200, 400), (900, 400), '<rect class="pl" x="-30" y="-8" width="60" height="16"/>',
                           t0=0.1, dur=1.2, cut=False, recolour='rgb(123, 79, 208)', recolour_target='.cellb',
                           uid='ap', scope='.tap', trigger='.slide.playing')
        frag = self.tmp / 'tap.html'
        frag.write_text('<section class="slide t0" data-title="Before"><h2 class="title">Before</h2></section>'
                        '<section class="slide tap" data-title="Auto" data-autoplay><h2 class="title">Auto</h2>'
                        '<style>.tap svg{position:absolute;left:0;top:0;width:1280px;height:720px}' + tr.css +
                        '</style><svg viewBox="0 0 1280 720"><rect class="cellb" x="880" y="380" width="40" '
                        'height="40" fill="rgb(200, 200, 200)"/>' + tr.svg + '</svg></section>', encoding='utf-8')
        deck = self.tmp / 'tap.deck.html'
        code, j, _ = assemble(frag, deck)
        self.assertEqual((code, j['warnings']), (0, []))
        names = "() => document.getAnimations().map(a => a.animationName).filter(Boolean)"
        st = "() => [getComputedStyle(document.querySelector('.tap .ap-done')).opacity, " \
             "getComputedStyle(document.querySelector('.tap .cellb')).fill]"
        with sync_playwright() as p:
            b = p.chromium.launch(args=['--no-sandbox', '--disable-gpu'])
            pg = b.new_page(viewport={'width': 1280, 'height': 720})
            pg.goto(deck.resolve().as_uri())
            pg.wait_for_timeout(500)
            self.assertNotIn('ap-fly', pg.evaluate(names))              # not playing before entry
            pg.keyboard.press('ArrowRight')
            pg.wait_for_timeout(int((tr.t_fly + 0.3) * 1000))
            self.assertIn('ap-fly', pg.evaluate(names))
            pg.wait_for_timeout(int((tr.t_end + 0.6) * 1000))
            got = pg.evaluate(st)
            b.close()
        self.assertEqual(got, ['1', 'rgb(123, 79, 208)'])

    def test_bad_frames_value(self):
        code, out, err = run('shot.py', self.deck('s12_autoplay.html'), self.tmp / 'f', '--frames', 'soon')
        self.assertNotEqual(code, 0)
        self.assertIn('--frames', json.loads(err)['error'])          # like a bad --then: before any browser

    def test_click_falls_back_to_js_dispatch(self):
        code, j, err = self.shot(self.deck('s12_svg_goto.html'), '0', '--click', '#hitg', '--click', '#back',
                                 '--click', '#emptyg', '--click', '#back', '--click', '#plain', '--wait', '500')
        self.assertEqual(code, 0, err)
        self.assertEqual([s['slide'] for s in j['shots'][1:]], [2, 1, 2, 1, 2])
        notes = [s.get('click') for s in j['shots'][1:]]
        self.assertEqual(notes, ['js-dispatch (point click lands on an ancestor)', None,
                                 'js-dispatch (element not visible)', None, None])
        self.assertEqual(err.count('NOTE: --click'), 2)

    def test_failed_assets_warn(self):
        code, j, err = self.shot(self.deck('s12_failed_assets.html'), '0', '--wait', '300')
        self.assertEqual(code, 0, err)
        self.assertEqual(j['real_errors'], [])
        fa = sorted((x['type'], pathlib.Path(x['url']).name) for x in j['failed_assets'])
        self.assertEqual(fa, [('font', 'missing.woff2'), ('image', 'missing.png')])
        self.assertIn('WARNING: 2 asset(s) failed to load', err)

    def test_small_ok_opt_out(self):
        code, j, err = self.shot(self.deck('s12_small_ok.html'), '0', '--check', '--check-size', 'none',
                                 '--wait', '300')
        self.assertEqual(code, 0, err)
        s = j['shots'][0]
        self.assertEqual([x['text'] for x in s['small_text']], ['plain'])
        self.assertEqual(sorted((x['text'], x['reason']) for x in s['small_ok']),
                         [('tick', 'tick labels'), ('unit', 'axis units')])
        self.assertEqual(sorted(x['reason'] for x in j['check']['small_ok']), ['axis units', 'tick labels'])
        self.assertTrue(j['check']['pass'])

    def test_no_new_keys_on_a_plain_run(self):
        code, j, _ = self.shot(self.deck('s12_autoplay.html'), '0', '--wait', '300')
        self.assertEqual(code, 0)
        self.assertEqual(set(j), {'shots', 'real_errors', 'size'})
        self.assertEqual(set(j['shots'][0]), {'png', 'slide', 'step', 'action'})

    def test_transfer_geometry_in_the_browser(self):
        """anim.transfer in a real deck: the payload sits at B(1/2) mid-flight and at dst on
        landing; after t_end the landing mark shows, the payload is gone and the target recoloured."""
        from playwright.sync_api import sync_playwright
        src, dst, c1, c2 = (200, 400), (900, 400), (350, 150), (750, 150)
        tr = anim.transfer(src, dst, '<rect class="pl" x="-30" y="-8" width="60" height="16" fill="#335"/>',
                           t0=0.2, dur=1.6, recolour='rgb(123, 79, 208)', recolour_target='.cellb',
                           c1=c1, c2=c2, uid='mv', scope='.tg')
        frag = self.tmp / 'tg.html'
        frag.write_text('<section class="slide tg" data-title="Transfer"><h2 class="title">Transfer</h2>'
                        '<style>.tg svg{position:absolute;left:0;top:0;width:1280px;height:720px}' + tr.css +
                        '</style><svg viewBox="0 0 1280 720"><rect class="cellb" x="880" y="380" width="40" '
                        'height="40" fill="rgb(200, 200, 200)"/><g class="step">' + tr.svg + '</g></svg></section>',
                        encoding='utf-8')
        deck = self.tmp / 'tg.deck.html'
        code, j, _ = assemble(frag, deck)
        self.assertEqual((code, j['warnings']), (0, []))
        centre = """() => { const svg=document.querySelector('.tg svg'), r=document.querySelector('.tg .pl')
                     .getBoundingClientRect(), m=svg.getScreenCTM().inverse(), p=svg.createSVGPoint();
                     p.x=r.left+r.width/2; p.y=r.top+r.height/2; const q=p.matrixTransform(m); return [q.x,q.y]; }"""
        seek = """t => { document.getAnimations().filter(a => a.animationName==='mv-fly')
                    .forEach(a => { a.pause(); a.currentTime = t; }); }"""
        mid = anim.bezier_points(src, c1, c2, dst, n=2)[1]
        with sync_playwright() as p:
            b = p.chromium.launch(args=['--no-sandbox', '--disable-gpu'])
            pg = b.new_page(viewport={'width': 1280, 'height': 720})
            pg.goto(deck.resolve().as_uri())
            pg.wait_for_timeout(500)
            pg.keyboard.press('ArrowRight')
            pg.wait_for_timeout(1000)                          # the kit's step reveal moves the step for 0.5 s
            for at, want in ((tr.t_fly + 0.5 * 1.6, mid), (tr.t_fly + 0.8 * 1.6, dst)):
                pg.evaluate(seek, at * 1000)                       # currentTime includes the delay
                got = pg.evaluate(centre)
                self.assertLess(math.dist(got, want), 1.5, (at, got, want))
            pg.evaluate("() => document.getAnimations().forEach(a => a.play())")
            pg.wait_for_timeout(int((tr.t_end + 0.6) * 1000))
            st = pg.evaluate("""() => [getComputedStyle(document.querySelector('.tg .mv-done')).opacity,
                                      getComputedStyle(document.querySelector('.tg .mv-fly')).opacity,
                                      getComputedStyle(document.querySelector('.tg .cellb')).fill]""")
            b.close()
        self.assertEqual(st, ['1', '0', 'rgb(123, 79, 208)'])


if __name__ == '__main__':
    unittest.main()
