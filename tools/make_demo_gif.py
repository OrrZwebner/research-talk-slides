#!/usr/bin/env python3
"""Build docs/demo.gif from examples/demo_deck.html (repo build helper, not part of the skill).

Runs the skill's shot.py through every reveal step of the demo deck, including a
drill-down click into the Attention detail and '‹ back', then stitches the PNGs
with Pillow (width 960, ~1.2 s per frame, loops).

GIF-only polish (the kit and examples/demo_deck.html are untouched):
  * the kit's bottom help hint (#hint) is hidden in a temporary copy of the deck
    that is shot instead of the real one;
  * an entry frame (step 0) whose content area below the title is blank is
    dropped when the next frame shows the same slide, i.e. it is merged into
    that slide's first reveal step.

Usage: python3 tools/make_demo_gif.py [--out docs/demo.gif] [--frame-ms 1200] [--width 960]
Requires: playwright (+ chromium) and Pillow. Prints JSON {"gif","frames","bytes"}.
"""
import argparse
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILL = ROOT / 'skills' / 'research-talk-slides'

# title -> pipeline (4 steps) -> overview (3 steps) = 9 advances,
# then drill into Attention, its 2 steps, back, jump to the chart, its 2 steps.
HIDE_HINT = '<style id="gif-only">#hint{display:none!important}</style>'
# content area below the title, in 1280x720 canvas px (left, top, right, bottom)
CONTENT_BOX = (40, 115, 1230, 680)


def is_blank_content(im, box=CONTENT_BOX, ink=235, frac=0.002):
    """True if almost no pixel in the content box is darker than `ink` (title-only slide)."""
    k = im.width / 1280.0
    g = im.convert('L').crop(tuple(round(v * k) for v in box))
    hist = g.histogram()
    dark = sum(hist[:ink])
    return dark < frac * g.width * g.height


SEQUENCE = ['--click', '[data-goto=attn]', '--then', 'right', '--then', 'right',
            '--click', '#back', '--then', 'slide:5', '--then', 'right', '--then', 'right']


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', default=str(ROOT / 'docs' / 'demo.gif'))
    ap.add_argument('--frame-ms', type=int, default=1200)
    ap.add_argument('--width', type=int, default=960)
    a = ap.parse_args()
    from PIL import Image

    deck = ROOT / 'examples' / 'demo_deck.html'
    subprocess.run([sys.executable, str(SKILL / 'scripts' / 'assemble.py'),
                    str(ROOT / 'examples' / 'demo_fragment.html'), str(deck)],
                   check=True, stdout=subprocess.DEVNULL)
    with tempfile.TemporaryDirectory() as td:
        gif_deck = pathlib.Path(td) / 'deck_gif.html'
        gif_deck.write_text(deck.read_text(encoding='utf-8').replace('</head>', HIDE_HINT + '</head>', 1),
                            encoding='utf-8')
        r = subprocess.run([sys.executable, str(SKILL / 'scripts' / 'shot.py'), str(gif_deck),
                            str(pathlib.Path(td) / 'f'), '9', '--wait', '1500', '--check', '--check-size', 'none'] + SEQUENCE,
                           capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(r.stdout + r.stderr)
        shots = json.loads(r.stdout)['shots']
        frames, dropped = [], []
        for n, s in enumerate(shots):
            im = Image.open(s['png']).convert('RGB')
            nxt = shots[n + 1] if n + 1 < len(shots) else None
            if (s['step'] == 0 and nxt and nxt['slide'] == s['slide'] and nxt['step'] > 0
                    and is_blank_content(im)):
                dropped.append(pathlib.Path(s['png']).name)
                continue
            h = round(im.height * a.width / im.width)
            frames.append(im.resize((a.width, h), Image.LANCZOS)
                          .quantize(colors=128, method=Image.MEDIANCUT, dither=Image.NONE))
        durations = [a.frame_ms] * len(frames)
        durations[0] = durations[-1] = a.frame_ms * 2      # linger on title and final frame
        out = pathlib.Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        frames[0].save(out, save_all=True, append_images=frames[1:], duration=durations,
                       loop=0, optimize=True, disposal=1)
    print(json.dumps({'gif': str(out), 'frames': len(frames), 'dropped_blank_entry': dropped, 'bytes': out.stat().st_size}))


if __name__ == '__main__':
    main()
