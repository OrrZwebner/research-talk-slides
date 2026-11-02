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
    assemble.py -o OUT.html --master 00-master_fragment.html --order ORDER.txt \\
                --title "Talk title" [--allow-missing] [--asset-base ../..]
Options:
    --title TEXT      the page <title> (the kit's is "Slide Kit")
    --body-class CLS  classes added to <body>: the kit options "slide-numbers" (running
                      slide number) and "progress" (step-aware bottom bar), space-separated
    --master FILE     a fragment spliced first (shared CSS/JS of the talk); not repeated
                      when it is also listed
    --order FILE      fragments in talk order, one path per line (relative to FILE's folder);
                      blank lines and # comments are skipped; listed fragments come before
                      any given on the command line
    --allow-missing   a fragment that does not exist is skipped with a warning (stderr and
                      "warnings") instead of exit 2, so a deck stitches mid-build
    --asset-base DIR  rewrite relative assets/ URLs in the fragments (src, href, poster,
                      data-src, srcset, CSS url()) to DIR/assets/..., e.g. a preview written
                      to build/NN/ with --asset-base ../.. still finds the talk's assets/
    --check-assets    warn on every relative URL in the deck (src, href, poster, data-src,
                      srcset, CSS url(); after the --asset-base rewrite) whose file does not
                      exist relative to OUT's folder, the way a browser resolves it; JSON
                      "assets": {"relative": N, "missing": [...]}. Use before publishing
                      (P6): a deck with relative assets is not self-contained

Prints JSON: {"out", "kit", "fragments", "slides", "chars", "warnings"}, plus "skipped"
with --allow-missing, "asset_rewrites" with --asset-base and "assets" with --check-assets.

Refused calls (exit 2) write nothing. Without -o the call must be exactly FRAGMENT
OUT.html, and OUT must not be an existing fragment (a file with a slide <section> but
no SLIDES:START marker): "assemble.py a_fragment.html b_fragment.html" would overwrite
b. When a call is refused and its output path holds an earlier assembled deck (it has
the SLIDES:START marker), that deck is renamed to OUT.stale, so nothing downstream
(shot.py, a publish) picks it up as if this call had refreshed it; the error JSON names
it in "stale_moved_to". Without -o, the output path of a refused call is its last
argument.
Warnings (non-fatal) flag: duplicate element ids across the deck, data-goto
targets with no matching data-id, vw/vh/dvh/svh units inside fragments (data: URIs
are skipped), spotlight markers (data-spot) missing class="spot step", malformed
data-spot-rect values, a data-ring other than "none" (or "none" together with a
data-caption), a data-caption-lane other than top | bottom | below-title, U+FFFD replacement
characters (a broken encoding; a host may refuse the deck), duplicate
data-title, a data-section that recurs after another section (not contiguous),
mixed data-section naming styles ("3" vs "4 · Name" vs "Name"; the first slide is
exempt), and fragment CSS rules that restyle a kit class (.chip, .panel, ...) on
every slide because they are not scoped under the fragment's own class; size: a
fragment over 500 KB (512,000 bytes) or with more than 2,000 <rect> elements (put
shared attributes on a <g> or a class, round coordinates, or switch a big heatmap to
an image). The markup lints skip <script> bodies (JS text such as 'data-goto="..."'
is not markup); the viewport-unit lint still reads them, since a script that sets
style.width = '50vw' does use one. Slides marked data-offpath (backup slides, opened
only by a link) are left out of the section-contiguity lint.
Exit codes: 0 ok, 2 bad input (missing file or kit markers).
"""
import argparse
import html
import json
import pathlib
import re
import sys

START = '<!-- ============================ SLIDES:START ============================ -->'
END = '<!-- ============================ SLIDES:END ============================== -->'
DEFAULT_KIT = pathlib.Path(__file__).resolve().parent.parent / 'assets' / 'kit.html'
# classes the kit styles; a fragment rule led by one of them restyles every slide of the deck
KIT_CLASSES = {'arena', 'lang', 'panel', 'meta', 'name', 'counter', 'stage-cell', 'chips', 'chip',
               'btn', 'note', 'cards', 'card', 'ci', 'stitle', 'title', 'kicker', 'sub', 'step',
               'brand', 'logo-slot', 'copybtn', 'halo', 'spot', 'spot-cap', 'spot-ring',
               'spot-veil', 'spot-lead'}
# kit modifiers and the slide wrapper: they never scope a rule to one fragment
KIT_GENERIC = {'slide', 'active', 'shown', 'pop', 'ghost', 'en', 'sa', 'bo', 'gr', 'has-spot'}


MAX_FRAGMENT_BYTES = 512000
MAX_RECTS = 2000
SCRIPT = re.compile(r'<!--.*?-->|(<script\b[^>]*>).*?(</script\s*>)', re.S | re.I)
STALE = {'out': None}          # the output path of this call, once known (see fail)


def fail(msg):
    """Refuse: exit 2, write nothing; an earlier deck at the output path is moved to OUT.stale."""
    res = {'error': msg}
    out = STALE['out']
    try:
        if out is not None and out.is_file() and START in out.read_text(encoding='utf-8', errors='replace'):
            stale = out.with_name(out.name + '.stale')
            out.replace(stale)
            res['stale_moved_to'] = str(stale)
            print('assemble.py: refused; the earlier deck %s was moved to %s so it is not mistaken for '
                  'this call\'s output' % (out, stale), file=sys.stderr)
    except OSError:
        pass
    print(json.dumps(res))
    sys.exit(2)


def strip_scripts(text):
    """<script> bodies emptied (the tags stay): JS text is not markup. Comments are kept
    as they are, and a "<script>" inside a comment opens nothing."""
    return SCRIPT.sub(lambda m: m.group(0) if m.group(1) is None else m.group(1) + m.group(2), text)


def lint(frags_text):
    """Cheap static checks on the joined fragment text."""
    warnings = []
    # comments out; markup lints read code_ns (no <script> bodies), the vw lint reads code
    code = re.sub(r'<!--.*?-->', '', frags_text, flags=re.S)
    code_ns = strip_scripts(code)
    ids = re.findall(r'\sid="([^"]+)"', code_ns)
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        warnings.append('duplicate element ids (prefix them per slide): ' + ', '.join(dup))
    targets = set(re.findall(r'data-goto="([^"]+)"', code_ns))
    have = set(re.findall(r'data-id="([^"]+)"', code_ns))
    missing = sorted(targets - have)
    if missing:
        warnings.append('data-goto targets without a slide data-id: ' + ', '.join(missing))
    # strip comments, then look for viewport units used as CSS lengths; data: URIs are cut
    # first, since base64 can spell "5vw"
    nodata = re.sub(r'data:[^"\')\s]*', 'data:', code)
    vp = sorted(set(re.findall(r'[\d.]+(?:vw|vh|dvh|svh|lvh)\b', nodata)))
    if vp:
        warnings.append('viewport units inside slides (use px or cqw/cqh): ' + ', '.join(vp))
    # spotlight markers: <i class="spot step" data-spot="SEL" ...> (selectors may contain '>')
    unlit, bad_rect, bad_ring, bad_lane = [], [], [], []
    for attrs in re.findall(r'<[a-zA-Z][\w-]*((?:\s+[\w:-]+(?:\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s>]+))?)*)\s*/?>', code_ns):
        spot = re.search(r'\sdata-spot="([^"]*)"', attrs)
        if not spot:
            continue
        cls = re.search(r'\sclass="([^"]*)"', attrs)
        if not cls or not {'spot', 'step'} <= set(cls.group(1).split()):
            unlit.append(spot.group(1))
        rect = re.search(r'\sdata-spot-rect="([^"]*)"', attrs)
        if rect and not re.fullmatch(r'\s*(?:[\d.]+\s*,\s*){3}[\d.]+\s*', rect.group(1)):
            bad_rect.append(rect.group(1))
        ring = re.search(r'\sdata-ring="([^"]*)"', attrs)
        if ring and ring.group(1) != 'none':
            bad_ring.append('%s (data-ring="%s")' % (spot.group(1), ring.group(1)))
        elif ring and re.search(r'\sdata-caption="', attrs):
            bad_ring.append('%s (data-caption with data-ring="none")' % spot.group(1))
        lane = re.search(r'\sdata-caption-lane="([^"]*)"', attrs)
        if lane and lane.group(1) not in ('top', 'bottom', 'below-title'):
            bad_lane.append('%s (data-caption-lane="%s")' % (spot.group(1), lane.group(1)))
    if unlit:
        warnings.append('spotlight markers without class="spot step" (they never light): ' + ', '.join(unlit))
    if bad_rect:
        warnings.append('data-spot-rect must be four numbers "x,y,w,h" (fractions of the target): '
                        + ', '.join(bad_rect))
    if bad_ring:
        warnings.append('data-ring takes only "none", which draws no ring, leader or caption: '
                        + ', '.join(bad_ring))
    if bad_lane:
        warnings.append('data-caption-lane takes only "top", "bottom" or "below-title": ' + ', '.join(bad_lane))
    # slide-level attributes, in slide order
    heads = re.findall(r'<section\b([^>]*\bclass="[^"]*\bslide\b[^>]*)>', code_ns)
    titles = [m.group(1) for m in (re.search(r'\sdata-title="([^"]*)"', h) for h in heads) if m]
    dup_t = sorted({x for x in titles if titles.count(x) > 1})
    if dup_t:
        warnings.append('duplicate data-title (the section map and the dots cannot tell them apart): '
                        + ', '.join(dup_t))
    secs = [m.group(1) if m else None for m in (re.search(r'\sdata-section="([^"]*)"', h) for h in heads)]
    offpath = [bool(re.search(r'\sdata-offpath(?:[\s=]|$)', h)) for h in heads]
    order = [s for s, off in zip(secs, offpath) if s is not None and not off]   # backup slides sit anywhere
    broken = []
    for k, s in enumerate(order):
        if k and s != order[k - 1] and s in order[:k] and s not in broken:
            broken.append(s)
    if broken:
        warnings.append('data-section not contiguous (a section recurs after another one): '
                        + ', '.join(broken))
    styles = {}
    for s in [s for s in secs[1:] if s is not None]:       # the first (title) slide is exempt
        v = s.strip()
        st = ('number' if re.fullmatch(r'\d+[a-z]?(?:\.\d+[a-z]?)*', v) else       # 3, 03a, 4.2
              'number · name' if re.match(r'\d+[a-z]?(?:\.\d+[a-z]?)*\s*·\s*\S', v) else 'name')
        styles.setdefault(st, s)
    if len(styles) > 1:
        warnings.append('mixed data-section naming styles (use one, e.g. "N · Name"): '
                        + ', '.join('%s "%s"' % kv for kv in sorted(styles.items())))
    return warnings


def css_rules(style_text):
    """Selectors of the style rules in a stylesheet; @media/@supports blocks are opened,
    other at-rules (@keyframes, @font-face) skipped."""
    s = re.sub(r'/\*.*?\*/', '', style_text, flags=re.S)
    out, i = [], 0
    while True:
        b = s.find('{', i)
        if b == -1:
            return out
        sel = s[i:b].strip().split(';')[-1].strip()      # drop a stray "@import ...;" before it
        depth, j = 1, b + 1
        while j < len(s) and depth:
            depth += {'{': 1, '}': -1}.get(s[j], 0)
            j += 1
        if sel.startswith(('@media', '@supports')):
            out += css_rules(s[b + 1:j - 1])
        elif not sel.startswith('@'):
            out.append(sel)
        i = j


def unscoped_kit_selector(sel):
    """True when the selector's first compound that is not html/body/#stage/.slide is made of
    kit classes only, e.g. ".chip", ".slide .panel .name", ".chip.sa" (but not ".myslide .chip")."""
    for comp in re.split(r'\s*[\s>+~]\s*', re.sub(r'::?[\w-]+(\([^)]*\))?', '', sel.strip())):
        if not comp or comp in ('html', 'body', '#stage', '*'):
            continue
        classes = re.findall(r'\.([\w-]+)', comp)
        if '#' in comp or not classes:
            return False                                 # scoped by an id, a tag or an attribute
        if set(classes) <= KIT_GENERIC:
            continue                                     # .slide, .slide.active: look further
        return set(classes) <= KIT_CLASSES | KIT_GENERIC
    return False


def lint_file(name, text):
    """Per-fragment checks that name the file: U+FFFD and unscoped kit-class CSS."""
    warnings = []
    n_bad = text.count('�')
    if n_bad:
        warnings.append('%s: %d U+FFFD replacement character(s) (a broken encoding; re-save the '
                        'source as UTF-8)' % (name, n_bad))
    size = len(text.encode('utf-8'))
    if size > MAX_FRAGMENT_BYTES:
        warnings.append('%s: %.0f KB, over the %d KB fragment budget (shared SVG attributes on a <g> '
                        'or a class, coordinates to 1 decimal, an image for a big heatmap)'
                        % (name, size / 1000, MAX_FRAGMENT_BYTES // 1000))
    hits = []
    code = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    n_rect = len(re.findall(r'<rect\b', strip_scripts(code), flags=re.I))
    if n_rect > MAX_RECTS:
        warnings.append('%s: %d <rect> elements (over %d; above about 500 cells draw a heatmap as an '
                        'image or canvas)' % (name, n_rect, MAX_RECTS))
    for style in re.findall(r'<style\b[^>]*>(.*?)</style>', code, flags=re.S):
        for sel in css_rules(style):
            hits += [p.strip() for p in sel.split(',') if unscoped_kit_selector(p)]
    if hits:
        warnings.append('%s: unscoped CSS restyles kit classes on every slide (prefix your slide '
                        'class): %s' % (name, ', '.join(dict.fromkeys(hits))))
    return warnings


ASSET_ATTR = re.compile(r'''(\b(?:src|href|poster|data-src)\s*=\s*["']|url\(\s*["']?)(?:\./)?assets/''')
SRCSET = re.compile(r'''(\bsrcset\s*=\s*)(["'])(.*?)\2''', re.S)


def rebase_assets(text, base):
    """assets/... -> BASE/assets/... in URL attributes, srcset and CSS url(); returns (text, n)."""
    base = base.rstrip('/') + '/assets/'
    text, n = ASSET_ATTR.subn(lambda m: m.group(1) + base, text)
    count = [n]

    def srcset(m):
        def one(e):
            e2 = re.sub(r'^(\s*)(?:\./)?assets/', lambda q: q.group(1) + base, e)
            count[0] += e2 != e
            return e2
        return m.group(1) + m.group(2) + ','.join(one(e) for e in m.group(3).split(',')) + m.group(2)
    text = SRCSET.sub(srcset, text)
    return text, count[0]


ASSET_REF = re.compile(r'''\b(?:src|href|poster|data-src)\s*=\s*(["'])(.*?)\1|url\(\s*(["']?)([^"')]*)\3\s*\)''', re.S)


def relative_urls(text):
    """Relative URLs in markup and CSS (no <script> bodies): src, href, poster, data-src, srcset, url()."""
    import urllib.parse
    code = strip_scripts(re.sub(r'<!--.*?-->', '', text, flags=re.S))
    found = [(m.start(), m.group(2) if m.group(2) is not None else m.group(4)) for m in ASSET_REF.finditer(code)]
    for m in SRCSET.finditer(code):
        found += [(m.start() + k / 100, e.strip().split()[0]) for k, e in enumerate(m.group(3).split(',')) if e.strip()]
    out = []
    for _, u in sorted(found):                    # document order
        u = html.unescape(u.strip())
        if (not u or u.startswith(('#', '/', '\\')) or re.match(r'[a-zA-Z][\w+.-]*:', u)
                or '${' in u or '{{' in u):
            continue                          # anchor, absolute path, scheme (http:, data:, mailto:), template
        out.append(urllib.parse.unquote(u.split('#', 1)[0].split('?', 1)[0]))
    return list(dict.fromkeys(x for x in out if x))


def read_order(path):
    p = pathlib.Path(path)
    if not p.is_file():
        fail('order file not found: %s' % p)
    out = []
    for line in p.read_text(encoding='utf-8').splitlines():
        line = line.split('#', 1)[0].strip()
        if line:
            q = pathlib.Path(line)
            out.append(str(q if q.is_absolute() else p.parent / q))
    return out


def main():
    ap = argparse.ArgumentParser(
        description='Splice slide fragment(s) into the kit. Forms: "FRAGMENT OUT.html" or "-o OUT.html FRAG...".',
        epilog='See the module docstring (head of this file) for the lint list and the JSON output.')
    ap.add_argument('paths', nargs='*', help='FRAGMENT OUT.html, or (with -o) one or more fragments')
    ap.add_argument('-o', '--out', help='output HTML (enables multi-fragment deck stitch)')
    ap.add_argument('--kit', default=str(DEFAULT_KIT), help='kit HTML (default: assets/kit.html of this skill)')
    ap.add_argument('--title', help='page <title> (replaces the kit\'s "Slide Kit")')
    ap.add_argument('--body-class', metavar='CLASSES',
                    help='classes added to <body>, e.g. "slide-numbers progress"')
    ap.add_argument('--master', metavar='FILE', help='fragment spliced first (the talk\'s shared CSS/JS)')
    ap.add_argument('--order', metavar='FILE',
                    help='fragments in talk order, one path per line relative to FILE; # comments')
    ap.add_argument('--allow-missing', action='store_true',
                    help='skip a missing fragment with a warning instead of exit 2')
    ap.add_argument('--asset-base', metavar='DIR',
                    help='rewrite relative assets/ URLs in fragments to DIR/assets/')
    ap.add_argument('--check-assets', action='store_true',
                    help='warn on relative asset URLs that do not exist relative to OUT (before publishing)')
    a = ap.parse_args()

    if a.out:
        frag_paths, out = list(a.paths), pathlib.Path(a.out)
        STALE['out'] = out
    else:
        if a.paths and (len(a.paths) > 2 or a.order):
            STALE['out'] = pathlib.Path(a.paths[-1])  # the likely output of a mistyped deck stitch
        if a.order or len(a.paths) != 2:
            fail('without -o give exactly FRAGMENT OUT.html; for several fragments (or --order) '
                 'use -o OUT.html FRAG1 FRAG2 ...')
        frag_paths, out = [a.paths[0]], pathlib.Path(a.paths[1])
        STALE['out'] = out
        if out.is_file():
            head = out.read_text(encoding='utf-8', errors='replace')
            if START not in head and re.search(r'<section\b[^>]*\bclass="[^"]*\bslide\b', head):
                STALE['out'] = None                    # a fragment: never move or overwrite it
                fail('%s is a slide fragment, not a deck: without -o the second path is the output '
                     'and would be overwritten; to stitch several fragments use -o OUT.html FRAG1 FRAG2 ...'
                     % out)
    if a.order:
        frag_paths = read_order(a.order) + frag_paths
    if a.master:
        if not pathlib.Path(a.master).is_file():
            fail('master fragment not found: %s' % a.master)
        mres = pathlib.Path(a.master).resolve()
        frag_paths = [a.master] + [f for f in frag_paths if pathlib.Path(f).resolve() != mres]
    if not frag_paths:
        fail('no fragments given')

    kit_path = pathlib.Path(a.kit)
    if not kit_path.is_file():
        fail('kit not found: %s' % kit_path)
    kit = kit_path.read_text(encoding='utf-8')
    i, j = kit.find(START), kit.find(END)
    if i == -1 or j == -1 or j < i:
        fail('SLIDES:START / SLIDES:END markers not found in kit %s' % kit_path)

    parts, used, skipped, file_warnings, rewrites = [], [], [], [], 0
    for fp in frag_paths:
        p = pathlib.Path(fp)
        if not p.is_file():
            if not a.allow_missing:
                fail('fragment not found: %s' % p)
            skipped.append(str(p))
            print('assemble.py: WARNING: fragment not found, skipped: %s' % p, file=sys.stderr)
            continue
        text = p.read_text(encoding='utf-8', errors='replace').strip()
        file_warnings += lint_file(str(p), text)
        if a.asset_base:
            text, n = rebase_assets(text, a.asset_base)
            rewrites += n
        parts.append(text)
        used.append(str(p))
    joined = '\n\n'.join(parts)

    head = kit[:i]
    if a.title is not None:
        head, n = re.subn(r'<title>.*?</title>', '<title>%s</title>' % html.escape(a.title, quote=False),
                          head, count=1, flags=re.S)
        if not n:
            fail('no <title> in kit %s' % kit_path)
    if a.body_class:
        cls = ' '.join(a.body_class.split())

        def add(m):
            attrs = m.group(1)
            c = re.search(r'\sclass="([^"]*)"', attrs)
            if c:
                return '<body%s>' % attrs.replace(c.group(0), ' class="%s %s"' % (c.group(1), cls), 1)
            return '<body%s class="%s">' % (attrs, cls)
        h = head.find('</head>') + 1                   # the real tag, not "<body>" in a comment
        rest, n = re.subn(r'<body\b([^>]*)>', add, head[h:], count=1)
        head = head[:h] + rest
        if not h or not n:
            fail('no <body> in kit %s' % kit_path)
    merged = head + kit[i:i + len(START)] + '\n' + joined + '\n' + kit[j:]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(merged, encoding='utf-8')
    warnings = lint(joined) + file_warnings + ['fragment not found, skipped: ' + s for s in skipped]
    if a.check_assets:
        rel = relative_urls(merged)
        missing = [u for u in rel if not (out.parent / u).exists()]
        if missing:
            warnings.append('relative assets not found next to %s (the published deck would miss them): %s'
                            % (out, ', '.join(missing)))
    res = {
        'out': str(out),
        'kit': str(kit_path),
        'fragments': used,
        'slides': len(re.findall(r'<section[^>]*class="[^"]*\bslide\b', strip_scripts(joined))),
        'chars': len(merged),
        'warnings': warnings,
    }
    if a.allow_missing:
        res['skipped'] = skipped
    if a.asset_base:
        res['asset_rewrites'] = rewrites
    if a.check_assets:
        res['assets'] = {'relative': len(rel), 'missing': missing}
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
