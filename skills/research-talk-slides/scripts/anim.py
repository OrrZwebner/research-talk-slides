#!/usr/bin/env python3
"""SVG + CSS helpers for slide generators on the research-talk-slides kit (stdlib only).

A generator is a Python script that writes a slide fragment. These helpers return
strings to paste into it; they never touch files.

    transfer(src, dst, payload_svg, ...)  a value moving from point A to point B along a
                                          curve, with an optional cut mark at A and a
                                          recolour on landing. Returns the markup, the CSS,
                                          the timings and the path points.
    label_clear(labels, obstacles, min_px)
                                          checks that value labels keep min_px from every
                                          mark (boxes, points, polylines such as the path
                                          points of a transfer) and from each other; raises
                                          ClearanceError on a violation.
    text_box(x, y, text, size)            a generous bounding box for an SVG <text>, for
                                          label_clear.
    fmt(v)                                a number for SVG/CSS: 1 decimal, no trailing zeros.

Import it from a generator next to a copy of this file, or by path:
    sys.path.insert(0, '<skill>/scripts'); import anim

All coordinates are canvas px (the kit's 1280x720 canvas, or the SVG's own viewBox units),
all times seconds after the trigger (by default the moment the enclosing kit .step is
shown). Run "python anim.py" to check the examples in the docstrings.
"""
import math
import re
from collections import namedtuple

__all__ = ['fmt', 'transfer', 'Transfer', 'label_clear', 'ClearanceError', 'text_box',
           'bezier_points']


def fmt(v):
    """A number as SVG/CSS text: 1 decimal, no trailing zeros (keeps generated SVG small).

    >>> fmt(3.0), fmt(2.25), fmt(-0.04), fmt(1280)
    ('3', '2.2', '0', '1280')
    """
    s = ('%.1f' % v).rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def _bez(p, t):
    u = 1 - t
    return tuple(u ** 3 * a + 3 * u * u * t * b + 3 * u * t * t * c + t ** 3 * d for a, b, c, d in zip(*p))


def bezier_points(src, c1, c2, dst, n=200):
    """n+1 points along the cubic Bezier src -> dst with control points c1, c2.

    >>> pts = bezier_points((0, 0), (0, -10), (10, -10), (10, 0), n=2)
    >>> [tuple(fmt(v) for v in q) for q in pts]
    [('0', '0'), ('5', '-7.5'), ('10', '0')]
    """
    p = (src, c1, c2, dst)
    return [_bez(p, k / n) for k in range(n + 1)]


def _sub(p, t0, t1):
    """The piece t0..t1 of the cubic p, as its own four control points (de Casteljau)."""
    def levels(q, t):
        a = [q]
        while len(a[-1]) > 1:
            a.append([tuple((1 - t) * x + t * y for x, y in zip(r, s)) for r, s in zip(a[-1], a[-1][1:])])
        return a
    a = levels(list(p), t0)
    right = [a[3][0], a[2][1], a[1][2], a[0][3]]
    b = levels(right, (t1 - t0) / (1 - t0) if t0 < 1 else 0)
    return [b[0][0], b[1][0], b[2][0], b[3][0]]


def default_controls(src, dst, bend=0.35):
    """Control points of an arc from src to dst that bulges to the left of the travel
    direction (upwards for a left-to-right move) by bend x the distance.

    >>> [tuple(fmt(v) for v in c) for c in default_controls((0, 100), (100, 100))]
    [('25', '65'), ('75', '65')]
    """
    (x0, y0), (x1, y1) = src, dst
    dx, dy = x1 - x0, y1 - y0
    nx, ny = dy, -dx                                    # left normal (y grows downwards)
    return ((x0 + dx / 4 + nx * bend, y0 + dy / 4 + ny * bend),
            (x0 + 3 * dx / 4 + nx * bend, y0 + 3 * dy / 4 + ny * bend))


Transfer = namedtuple('Transfer', 'svg css t_cut t_fly t_land t_end points')
Transfer.__doc__ = """Result of transfer().
svg     markup to place inside a kit .step (or another trigger element) of an inline <svg>
css     the scoped rules and @keyframes, for the fragment's <style>
t_cut   when the cut mark completes (s; equals t_fly - 0.1 with a cut, else t0)
t_fly   when the payload starts to move
t_land  when the payload reaches dst (the flash and the recolour start here)
t_end   when the last beat ends: wait at least this long (plus the kit fade) before a shot
points  201 points of the full flight curve, src -> dst, for label_clear()"""

# beats, in % of the flight duration: grow at A, leave, land at B, gone
_GROW, _LEAVE, _LAND, _GONE = 12, 20, 80, 90
_SNIP, _FLASH = 0.9, 0.6


def transfer(src, dst, payload_svg, t0=0.0, dur=2.8, cut=True, recolour=None, uid='xfer',
             scope='', trigger='.step.shown', c1=None, c2=None, bend=0.35, ring=14, land_ring=None,
             recolour_target=None, speed=1.0, path_colour='#9aa3b2', mark_colour='var(--ink, #1a1a1a)'):
    """Animate a payload moving from point src to point dst along a curve.

    Beats, in seconds after the trigger (the enclosing kit .step being shown):
      t0 .. t_cut   with cut=True: a ring marks src and a pair of scissors snips twice;
                    the ring turns into a dashed cut line (the value is taken out of A)
      t_fly         the curve (with an arrow head) appears; the payload grows at src,
                    flies along the curve and shrinks into dst (dur s in all)
      t_land        a flash at dst; with recolour, a ring + dot in that colour stay at
                    dst, and the elements matched by recolour_target change their fill
      t_end         the last beat is over

    src, dst      (x, y) in the coordinates of the <svg> the markup goes into
    payload_svg   SVG markup drawn around (0, 0), e.g. a small labelled rect; it is
                  moved by a CSS transform, so keep its own coordinates centred on 0
    dur           flight duration in s (the move itself is 60 % of it)
    cut           draw the cut mark at src (False: the payload just leaves)
    recolour      a CSS colour for the landing mark (None: no mark, only the flash)
    recolour_target  a CSS selector (inside the slide) whose fill turns `recolour` at
                  t_land, e.g. the target cell; needs recolour. The rule reads
                  ".SCOPE:has(TRIGGER .UID-fly) SELECTOR" (uses :has()), or with a
                  slide trigger ".SCOPE.slide.playing SELECTOR"
    uid           prefix of every class and @keyframes name: unique per transfer on a slide
    scope         a selector every rule is prefixed with, normally the slide's own class
                  (".myslide"); empty for no prefix
    trigger       the state that starts the beats: ".step.shown" (default; put the markup
                  inside a <g class="step">), ".slide.playing" for an autoplay slide
                  (<section class="slide myslide" data-autoplay>), or ".playing" for an
                  element with data-autoplay inside the slide. A trigger that starts with
                  ".slide" names the slide itself, so it is joined to the scope on that one
                  element: scope ".s7" + ".slide.playing" gives ".s7.slide.playing .UID-fly";
                  any other trigger is a descendant of the scope (".s7 .step.shown .UID-fly")
    c1, c2        Bezier control points; default: an arc bulging by bend x the distance
    ring          radius of the source ring; land_ring that of the landing ring (default ring)
    speed         > 1 plays faster, < 1 slower: every time (and the returned timings) is
                  divided by it. This is the only speed control: the times are written into
                  the CSS, so the kit's --anim-speed variable does not reach transfer()

    Example (synthetic): a value moves from a cell at (100, 200) to one at (500, 200).

    >>> tr = transfer((100, 200), (500, 200), '<rect x="-30" y="-8" width="60" height="16"/>',
    ...               t0=0.5, recolour='#7b4fd0', uid='mv1', scope='.demo')
    >>> (round(tr.t_cut, 2), round(tr.t_fly, 2), round(tr.t_land, 2), round(tr.t_end, 2))
    (1.4, 1.5, 3.74, 4.34)
    >>> tr.points[0], tr.points[-1]
    ((100.0, 200.0), (500.0, 200.0))
    >>> min(y for x, y in tr.points) < 200       # the default arc bulges upwards
    True
    >>> '@keyframes mv1-fly' in tr.css and '.demo .step.shown .mv1-fly' in tr.css
    True
    >>> tr.svg.count('class="mv1-fly"')
    1

    On an autoplay slide (<section class="slide demo" data-autoplay>):

    >>> ap = transfer((100, 200), (500, 200), '<circle r="6"/>', uid='mv2', scope='.demo',
    ...               trigger='.slide.playing')
    >>> '.demo.slide.playing .mv2-fly{animation:' in ap.css
    True

    Use in a generator:
        tr = anim.transfer(A, B, '<rect .../>', recolour='var(--sa)', uid='mv1', scope='.s07')
        svg = '<g class="step">' + tr.svg + '</g>'; style = tr.css
        anim.label_clear([anim.text_box(x, y, '0.42')], [tr.points], 6)
    """
    if speed <= 0:
        raise ValueError('speed must be > 0')
    if recolour_target and not recolour:
        raise ValueError('recolour_target needs recolour (the colour to turn it)')
    k = 1.0 / speed
    t0, dur = t0 * k, dur * k
    snip, flash = _SNIP * k, _FLASH * k
    land_ring = land_ring or ring
    if c1 is None or c2 is None:
        d1, d2 = default_controls(src, dst, bend)
        c1, c2 = c1 or d1, c2 or d2
    curve = (tuple(src), tuple(c1), tuple(c2), tuple(dst))
    t_cut = t0 + snip if cut else t0
    t_fly = t_cut + 0.1 * k if cut else t0
    t_land = t_fly + dur * _LAND / 100
    t_end = max(t_land + flash, t_fly + dur * _GONE / 100)
    points = [_bez(curve, j / 200) for j in range(201)]

    n, S = uid, (scope.strip() + ' ') if scope.strip() else ''
    T = trigger.strip()
    on_slide = re.match(r'\.slide(?![\w-])', T) is not None      # the trigger is the slide itself
    TS = (scope.strip() + T) if (on_slide and scope.strip()) else S + T
    (sx, sy), (tx, ty) = src, dst
    # the visible curve stops short of the source ring and the landing mark
    gap_a = (ring + 2) if cut else 2
    gap_b = (land_ring + 3) if recolour else 4
    dists = [math.dist(q, src) for q in points]
    ta = next((j / 200 for j, d in enumerate(dists) if d >= gap_a), 0.0)
    tb = next((j / 200 for j in range(200, -1, -1) if math.dist(points[j], dst) >= gap_b), 1.0)
    a, b, c, d = _sub(curve, ta, tb) if tb > ta else curve

    o = ['<g class="%s">' % n,
         '<defs><marker id="%s-ah" markerWidth="12" markerHeight="12" refX="6" refY="4" orient="auto" '
         'markerUnits="userSpaceOnUse"><path d="M0,0 L9,4 L0,8 Z" fill="%s"/></marker></defs>' % (n, path_colour)]
    if cut:
        o.append('<circle class="%s-ring" cx="%s" cy="%s" r="%s"/>' % (n, fmt(sx), fmt(sy), fmt(ring)))
        o.append('<circle class="%s-cutr" cx="%s" cy="%s" r="%s"/>' % (n, fmt(sx), fmt(sy), fmt(ring)))
        o.append(_scissors(n, sx, sy, ring))
    o.append('<path class="%s-arc" d="M%s,%s C%s,%s %s,%s %s,%s" marker-end="url(#%s-ah)"/>'
             % ((n,) + tuple(fmt(v) for pt in (a, b, c, d) for v in pt) + (n,)))
    o.append('<circle class="%s-flash" cx="%s" cy="%s" r="8"/>' % (n, fmt(tx), fmt(ty)))
    if recolour:
        o.append('<g class="%s-done"><circle class="%s-lring" cx="%s" cy="%s" r="%s"/>'
                 '<circle class="%s-ldot" cx="%s" cy="%s" r="6"/></g>'
                 % (n, n, fmt(tx), fmt(ty), fmt(land_ring), n, fmt(tx), fmt(ty)))
    o.append('<g transform="translate(%s,%s)"><g class="%s-fly">%s</g></g>' % (fmt(sx), fmt(sy), n, payload_svg))
    o.append('</g>')

    s = lambda v: '%gs' % round(v, 3)
    rules = [
        '%(S)s.%(n)s-arc{fill:none;stroke:%(pc)s;stroke-width:3;opacity:0}',
        '%(TS)s .%(n)s-arc{opacity:1;transition:opacity .4s ease %(fly)s}',
        '%(S)s.%(n)s-flash{fill:%(fc)s;opacity:0;transform-box:fill-box;transform-origin:center}',
        '%(TS)s .%(n)s-flash{animation:%(n)s-flash %(flash)s ease-out %(land)s forwards}',
        '%(S)s.%(n)s-fly{opacity:0;transform-box:view-box;transform-origin:0 0}',
        '%(TS)s .%(n)s-fly{animation:%(n)s-fly %(dur)s cubic-bezier(.4,0,.3,1) %(fly)s both}',
    ]
    if cut:
        rules += [
            '%(S)s.%(n)s-ring{fill:none;stroke:%(mc)s;stroke-width:3}',
            '%(S)s.%(n)s-cutr{fill:none;stroke:%(mc)s;stroke-width:3;stroke-dasharray:5 4;opacity:0}',
            '%(TS)s .%(n)s-ring{opacity:0;transition:opacity .15s linear %(cut)s}',
            '%(TS)s .%(n)s-cutr{opacity:1;transition:opacity .15s linear %(cut)s}',
            '%(S)s.%(n)s-scl{fill:var(--paper, #fff);stroke:var(--ink, #1a1a1a);stroke-width:1.8}',
            '%(S)s.%(n)s-scb{fill:var(--ink, #1a1a1a);stroke:var(--ink, #1a1a1a);stroke-width:1.2;stroke-linejoin:round}',
            '%(S)s.%(n)s-scp{fill:var(--paper, #fff)}',
            '%(S)s.%(n)s-bla,%(S)s.%(n)s-blb{transform-box:view-box;transform-origin:0 0}',
            '%(TS)s .%(n)s-bla{animation:%(n)s-snipa %(snip)s ease-in-out %(t0)s both}',
            '%(TS)s .%(n)s-blb{animation:%(n)s-snipb %(snip)s ease-in-out %(t0)s both}',
        ]
    if recolour:
        rules += [
            '%(S)s.%(n)s-lring{fill:none;stroke:%(rc)s;stroke-width:3}',
            '%(S)s.%(n)s-ldot{fill:%(rc)s;stroke:var(--paper, #fff);stroke-width:2}',
            '%(S)s.%(n)s-done{opacity:0}',
            '%(TS)s .%(n)s-done{opacity:1;transition:opacity .2s ease %(land)s}',
        ]
    if recolour_target:
        if on_slide:
            sel = '%s %s' % (TS, recolour_target)
        else:
            sel = '%s:has(%s .%s-fly) %s' % (scope.strip() or '.slide', T, n, recolour_target)
        rules.append('%s{fill:%s;transition:fill .2s ease %s}' % (sel, recolour, s(t_land)))
    v = dict(S=S, T=T, TS=TS, n=n, pc=path_colour, mc=mark_colour, rc=recolour or '', fc=recolour or path_colour,
             fly=s(t_fly), land=s(t_land), flash=s(flash), dur=s(dur), cut=s(t_cut), snip=s(snip), t0=s(t0))
    css = '\n'.join(r % v if '%(' in r else r for r in rules)
    css += '\n' + _keyframes(n, curve, cut)
    css += ('\n@media (prefers-reduced-motion:reduce){%s.%s *{animation:none!important;transition:none!important}}\n'
            % (S, n))
    return Transfer(''.join(o), css, t_cut, t_fly, t_land, t_end, points)


def _scissors(n, sx, sy, ring):
    """A small pair of scissors up-left of the source ring, pointing at it (two blades)."""
    k = 1.3
    d = ring + 4 + 13 * k
    x, y = sx - d / math.sqrt(2), sy - d / math.sqrt(2)
    o = ['<g transform="translate(%s,%s) rotate(45) scale(%s)">' % (fmt(x), fmt(y), fmt(k))]
    for cls, sg in (('bla', -1), ('blb', 1)):
        o.append('<g class="%s-%s"><circle class="%s-scl" cx="-11" cy="%s" r="4.5"/>'
                 '<path class="%s-scb" d="M-7,%s L13,%s L13,%s L-6,%s Z"/></g>'
                 % (n, cls, n, fmt(6 * sg), n, fmt(4.5 * sg), fmt(-1.5 * sg), fmt(-0.2 * sg), fmt(2 * sg)))
    o.append('<circle class="%s-scp" cx="0" cy="0" r="1.6"/></g>' % n)
    return ''.join(o)


def _keyframes(n, curve, cut):
    src, dst = curve[0], curve[3]
    fr = ['0%{transform:translate(0px,0px) scale(.2);opacity:0}',
          '%d%%{transform:translate(0px,0px) scale(1);opacity:1}' % _GROW]
    m = 16
    for i in range(m + 1):
        pc = _LEAVE + (_LAND - _LEAVE) * i / m
        x, y = _bez(curve, i / m)
        fr.append('%s%%{transform:translate(%spx,%spx) scale(1);opacity:1}' % (fmt(pc), fmt(x - src[0]), fmt(y - src[1])))
    dx, dy = dst[0] - src[0], dst[1] - src[1]
    fr.append('%d%%{transform:translate(%spx,%spx) scale(.2);opacity:1}' % (_GONE - 3, fmt(dx), fmt(dy)))
    fr.append('%d%%,100%%{transform:translate(%spx,%spx) scale(.2);opacity:0}' % (_GONE, fmt(dx), fmt(dy)))
    out = ['@keyframes %s-fly{%s}' % (n, ''.join(fr)),
           '@keyframes %s-flash{0%%{transform:scale(1);opacity:.85}100%%{transform:scale(3.2);opacity:0}}' % n]
    if cut:
        snip = ''.join('%s%%{transform:rotate(%sdeg)}' % (fmt(100 * i / 3), '0' if i % 2 else 'V') for i in range(4))
        out += ['@keyframes %s-snipa{%s}' % (n, snip.replace('V', '22')),
                '@keyframes %s-snipb{%s}' % (n, snip.replace('V', '-22'))]
    return '\n'.join(out)


# ---------------------------------------------------------------- label clearance

class ClearanceError(AssertionError):
    """A label is closer than min_px to a mark or to another label. .violations lists
    (label, obstacle, gap_px) for every offending pair."""

    def __init__(self, violations, min_px):
        self.violations = violations
        self.min_px = min_px
        lines = ['%s is %s px from %s (need >= %s)' % (a, fmt(g), b, fmt(min_px)) for a, b, g in violations]
        super().__init__('%d label clearance violation(s):\n  ' % len(violations) + '\n  '.join(lines))


def text_box(x, y, text, size=15, anchor='middle', em=0.6, baseline='central'):
    """A generous box (x0, y0, x1, y1) around an SVG <text> at (x, y): em x size px per
    character (0.6 is wide enough for digits in most sans fonts), size x 1.1 px tall.
    anchor = text-anchor (start | middle | end); baseline = 'central' (y is the middle,
    dominant-baseline:central) or 'alphabetic' (y is the baseline, the SVG default).

    >>> text_box(100, 50, '0.42', size=15)
    (82.0, 41.75, 118.0, 58.25)
    >>> text_box(100, 50, '0.42', size=10, anchor='end', baseline='alphabetic')
    (76.0, 42.0, 100.0, 52.5)
    """
    w, h = em * size * len(text), 1.1 * size
    x0 = {'start': x, 'middle': x - w / 2, 'end': x - w}[anchor]
    if baseline == 'central':
        y0, y1 = y - h / 2, y + h / 2
    elif baseline == 'alphabetic':
        y0, y1 = y - 0.8 * size, y + 0.25 * size
    else:
        raise ValueError('baseline must be central or alphabetic')
    return (round(x0, 3), round(y0, 3), round(x0 + w, 3), round(y1, 3))


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _shape(item, kind, i):
    """(name, kind, data): kind is 'box' (x0,y0,x1,y1), 'pt' (x,y) or 'line' [pts]."""
    name = None
    if isinstance(item, dict):
        name = item.get('name') or item.get('text')
        for key, kd in (('box', 'box'), ('point', 'pt'), ('points', 'line')):
            if key in item:
                item = item[key]
                break
        else:
            raise ValueError('%s %d: a dict needs "box", "point" or "points"' % (kind, i))
    item = list(item)
    if len(item) == 4 and all(_is_num(v) for v in item):
        x0, y0, x1, y1 = item
        return (name or '%s %d' % (kind, i), 'box', (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))
    if len(item) == 2 and all(_is_num(v) for v in item):
        return (name or '%s %d' % (kind, i), 'pt', tuple(item))
    if item and all(len(q) == 2 for q in item):
        return (name or '%s %d' % (kind, i), 'line', [tuple(q) for q in item])
    raise ValueError('%s %d: not a box (x0,y0,x1,y1), a point (x,y) or a list of points' % (kind, i))


def _pt_box(p, b):
    x, y = p
    return math.hypot(max(b[0] - x, 0, x - b[2]), max(b[1] - y, 0, y - b[3]))


def _pt_seg(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def _seg_hits_box(a, b, box):
    """True when the segment a-b crosses the box (Liang-Barsky clip)."""
    x0, y0, x1, y1 = box
    (ax, ay), (bx, by) = a, b
    t0, t1, dx, dy = 0.0, 1.0, bx - ax, by - ay
    for p, q in ((-dx, ax - x0), (dx, x1 - ax), (-dy, ay - y0), (dy, y1 - ay)):
        if p == 0:
            if q < 0:
                return False
        else:
            r = q / p
            if p < 0:
                t0 = max(t0, r)
            else:
                t1 = min(t1, r)
            if t0 > t1:
                return False
    return True


def _seg_box(a, b, box):
    if _seg_hits_box(a, b, box):
        return 0.0
    x0, y0, x1, y1 = box
    corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    return min([_pt_box(a, box), _pt_box(b, box)] + [_pt_seg(c, a, b) for c in corners])


def _gap(box, kind, data):
    if kind == 'box':
        return math.hypot(max(box[0] - data[2], 0, data[0] - box[2]), max(box[1] - data[3], 0, data[1] - box[3]))
    if kind == 'pt':
        return _pt_box(data, box)
    if len(data) == 1:
        return _pt_box(data[0], box)
    return min(_seg_box(a, b, box) for a, b in zip(data, data[1:]))


def label_clear(labels, obstacles, min_px, between_labels=True):
    """Check that every label box keeps >= min_px from every obstacle (and, with
    between_labels, from every other label); return the smallest gap found (px).
    Raises ClearanceError listing every pair that is too close.

    labels     boxes (x0, y0, x1, y1), e.g. from text_box(), or dicts
               {"text" or "name": ..., "box": (x0, y0, x1, y1)}
    obstacles  marks the labels must not touch: a box (x0, y0, x1, y1), a point (x, y),
               a polyline [(x, y), ...] (e.g. transfer(...).points, or a bar's outline),
               or a dict {"name": ..., "box" | "point" | "points": ...}
    Distances are exact for boxes, points and polyline segments (not sampled).

    Example (synthetic): a bar chart's value labels against the bars and a trend line.

    >>> bars = [{'name': 'bar A', 'box': (100, 300, 140, 500)}, {'name': 'bar B', 'box': (160, 250, 200, 500)}]
    >>> line = {'name': 'trend', 'points': [(80, 200), (220, 200)]}
    >>> labels = [{'text': '0.62', 'box': text_box(120, 288, '0.62', size=14)},
    ...           {'text': '0.71', 'box': text_box(180, 238, '0.71', size=14)}]
    >>> fmt(label_clear(labels, bars + [line], min_px=4))
    '4.3'
    >>> try:
    ...     label_clear(labels, bars + [line], min_px=6)
    ... except ClearanceError as e:
    ...     print(e.violations[0][:2], fmt(e.violations[0][2]))
    ('0.62', 'bar A') 4.3
    """
    L = [_shape(x, 'label', i) for i, x in enumerate(labels)]
    for name, kind, _ in L:
        if kind != 'box':
            raise ValueError('%s: a label must be a box (x0, y0, x1, y1)' % name)
    O = [_shape(x, 'obstacle', i) for i, x in enumerate(obstacles)]
    bad, best = [], math.inf
    for i, (ln, _, lb) in enumerate(L):
        others = O + ([(n, k, d) for j, (n, k, d) in enumerate(L) if j > i] if between_labels else [])
        for on, ok, od in others:
            g = _gap(lb, ok, od)
            best = min(best, g)
            if g < min_px - 1e-9:
                bad.append((ln, on, g))
    if bad:
        raise ClearanceError(bad, min_px)
    return best


if __name__ == '__main__':
    import doctest
    import sys
    r = doctest.testmod()
    print('anim.py: %d examples, %d failed' % (r.attempted, r.failed))
    sys.exit(1 if r.failed else 0)
