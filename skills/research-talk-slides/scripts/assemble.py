#!/usr/bin/env python3
"""Splice slide fragment(s) into the slide kit and write a standalone deck HTML.

A fragment is one or more <section class="slide" ...> elements, each optionally
carrying its own <style> and <script>. The kit (assets/kit.html next to this
scripts/ folder, unless --kit is given) holds everything else: canvas, master,
step-reveal engine, drill-down, chrome. The fragments replace the region
between the SLIDES:START / SLIDES:END markers, in the order given.

Usage:
    assemble.py FRAGMENT OUT.html                  # one fragment
    assemble.py -o OUT.html FRAG1 [FRAG2 ...]      # deck stitch, talk order
    assemble.py --kit my_kit.html FRAGMENT OUT.html

Prints JSON: {"out", "kit", "fragments", "slides", "chars", "warnings"}.
Warnings (non-fatal) flag: duplicate element ids across the deck, data-goto
targets with no matching data-id, and vw/vh/dvh/svh units inside fragments.
Exit codes: 0 ok, 2 bad input (missing file or kit markers).
"""
import argparse
import json
import pathlib
import re
import sys

START = '<!-- ============================ SLIDES:START ============================ -->'
END = '<!-- ============================ SLIDES:END ============================== -->'
DEFAULT_KIT = pathlib.Path(__file__).resolve().parent.parent / 'assets' / 'kit.html'


def fail(msg):
    print(json.dumps({'error': msg}))
    sys.exit(2)


def lint(frags_text):
    """Cheap static checks on the joined fragment text."""
    warnings = []
    ids = re.findall(r'\sid="([^"]+)"', frags_text)
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        warnings.append('duplicate element ids (prefix them per slide): ' + ', '.join(dup))
    targets = set(re.findall(r'data-goto="([^"]+)"', frags_text))
    have = set(re.findall(r'data-id="([^"]+)"', frags_text))
    missing = sorted(targets - have)
    if missing:
        warnings.append('data-goto targets without a slide data-id: ' + ', '.join(missing))
    # strip comments, then look for viewport units used as CSS lengths
    code = re.sub(r'<!--.*?-->', '', frags_text, flags=re.S)
    vp = sorted(set(re.findall(r'[\d.]+(?:vw|vh|dvh|svh|lvh)\b', code)))
    if vp:
        warnings.append('viewport units inside slides (use px or cqw/cqh): ' + ', '.join(vp))
    return warnings


def main():
    ap = argparse.ArgumentParser(
        description='Splice slide fragment(s) into the kit. Forms: "FRAGMENT OUT.html" or "-o OUT.html FRAG...".')
    ap.add_argument('paths', nargs='+', help='FRAGMENT OUT.html, or (with -o) one or more fragments')
    ap.add_argument('-o', '--out', help='output HTML (enables multi-fragment deck stitch)')
    ap.add_argument('--kit', default=str(DEFAULT_KIT), help='kit HTML (default: assets/kit.html of this skill)')
    a = ap.parse_args()

    if a.out:
        frag_paths, out = a.paths, pathlib.Path(a.out)
    else:
        if len(a.paths) != 2:
            fail('without -o give exactly FRAGMENT OUT.html; for several fragments use -o OUT.html FRAG1 FRAG2 ...')
        frag_paths, out = [a.paths[0]], pathlib.Path(a.paths[1])

    kit_path = pathlib.Path(a.kit)
    if not kit_path.is_file():
        fail('kit not found: %s' % kit_path)
    kit = kit_path.read_text(encoding='utf-8')
    i, j = kit.find(START), kit.find(END)
    if i == -1 or j == -1 or j < i:
        fail('SLIDES:START / SLIDES:END markers not found in kit %s' % kit_path)

    parts = []
    for fp in frag_paths:
        p = pathlib.Path(fp)
        if not p.is_file():
            fail('fragment not found: %s' % p)
        parts.append(p.read_text(encoding='utf-8').strip())
    joined = '\n\n'.join(parts)

    merged = kit[:i + len(START)] + '\n' + joined + '\n' + kit[j:]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(merged, encoding='utf-8')
    print(json.dumps({
        'out': str(out),
        'kit': str(kit_path),
        'fragments': [str(f) for f in frag_paths],
        'slides': len(re.findall(r'<section[^>]*class="[^"]*\bslide\b', joined)),
        'chars': len(merged),
        'warnings': lint(joined),
    }, indent=1))


if __name__ == '__main__':
    main()
