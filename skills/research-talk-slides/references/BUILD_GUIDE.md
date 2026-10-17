# Build guide — kit architecture, conventions, do-not-regress table

Load this before authoring the first slide of a session, and whenever a slide fails
verification. SKILL.md has the procedures; this file has the reasons and the details.

## 0. Non-negotiables in one breath

One shared kit defines palette, fonts, canvas, reveal engine, chrome and logo slots; every
slide is built against it. Slides live on a fixed 1280×720 canvas scaled to fit. Inside a
slide: px or cqw/cqh, never vw/vh. White master, top-left title, no kicker. Minimal text, never
invented. One build per click. Screenshot every step before delivering.

## 1. Layout of the skill and of a talk

```
<skill>/assets/kit.html            the kit (do not copy-edit per slide)
<skill>/scripts/assemble.py        fragment(s) -> standalone deck
<skill>/scripts/shot.py            screenshots per reveal step (+ --check)
<talk>/<name>_fragment.html        EDITABLE source: <section>(s) + own <style>/<script>
<talk>/<name>.html                 assembled deck (open by double-click)
<talk>/shots/<name>_NN.png         verification screenshots
```

Why fragments: the kit is the single source of the master and engine; a fragment holds only
what is specific to its slide, so slide work stays small and every slide shares one shell.
`assemble.py` replaces the region between `SLIDES:START` / `SLIDES:END` in the kit.

## 2. The kit

### 2.1 Master
- Background white (`--paper:#fff`).
- Title: `<h2 class="title">`, top-left, Open Sans 700, 48px, one per slide. No `.kicker`
  on content slides. A title slide may use `<h1 class="title">` larger and vertically centred.
- Logo slots bottom-left (192px wide) and bottom-right (132px wide), 16px from the bottom,
  **hidden until set** (`--logo-left` / `--logo-right` CSS variables, or replace the slot
  `<div>` with an `<img class="brand brand-left">`). Embed at ≥ 2× display width.
- Slide padding `52px 64px 100px`: content must end above canvas y = 620.

### 2.2 Palette and fonts (`:root`)
```
--ink:#1a1a1a  --paper/--panel:#fff  --line:#e2e0d8  --muted:#5e6470  --tint:#eef2fb
--en:#1b2a4a navy (primary)  --sa:#3b7dd8 blue  --bo:#e8833a orange  --gr:#5a8f69 green
--title:'Open Sans'  --display:'Space Grotesk'  --serif:'Spectral'  --mono:'JetBrains Mono'
```
One semantic color per concept, reused everywhere it appears. Only these tokens exist; a
reference to an undefined variable (e.g. `var(--c1)`) silently drops the property. For
non-Latin scripts add a Noto family to the Google Fonts link in the kit.

### 2.3 Fixed-canvas scaling
`#stage` is 1280×720, `container-type:size`, scaled by
`s = min(W_vp/1280, H_vp/720)` and translated by `((W_vp − 1280s)/2, (H_vp − 720s)/2)`
(letterbox/pillarbox). Content never re-layouts; it only scales. Because the stage is a size
container, `1cqw = 12.8px` and `1cqh = 7.2px` are constants. `vw/vh/dvh/svh` read the real
viewport and double-scale, so content shifts or disappears on another screen.
Background: reveal.js "Presentation Size" (https://revealjs.com/presentation-size/);
MDN container query length units (https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_containment/Container_queries).

### 2.4 Step-reveal engine
- A slide: `<section class="slide" data-section="NN" data-title="...">`.
- Non-`.step` content shows on entry. `.step` elements reveal one **bucket** per advance.
  Elements sharing `data-step="k"` form one bucket; bucket order = smallest DOM index among
  its members; a `.step` without `data-step` is its own bucket. So the number of advances on a
  slide equals its number of buckets.
- Keys: `→`/click/space next, `←` back, `O` section map, `N` notes, `F` fullscreen, dots jump.
- On reveal `kit:step` fires on `document` with `detail:{slide,index,els}`; `kit:unstep` on
  reverse. The kit's default reveal is fade + 14px rise; slides with arrows override it to
  opacity only.
- Unrevealed steps have `pointer-events:none`, so a hidden drill-down component cannot be
  clicked by accident.
- Speaker notes: `<aside class="notes-src">…</aside>` inside the slide.
- A single-slide file hides the nav dots. There are no prev/next buttons (they looked like
  arrows next to the logo).
- Drill-down: `data-goto="<id>"` on a component jumps to the slide with `data-id="<id>"` and
  shows `‹ back` (and Backspace), which returns to the overview fully revealed. The back-stack
  clears on a normal map/dot jump. The target must be in the same file.

### 2.5 Component vocabulary
`.panel` (rounded card, colored left accent via `.en/.sa/.bo/.gr`), `.chip` (mono token box,
`.sa`/`.bo` tints, `.pop` animation), `.counter` (large mono number), `.card` (titled card),
`.sub` (serif subtitle), `.btn`, `.note`. Slide-specific visuals (matrices, nets, heat grids,
charts) are built in the fragment.

### 2.6 Fragment hygiene (needed once fragments share one deck)
- Give each section its own class and scope **every** rule under it
  (`.pipe .box{…}`, never bare `.box{…}` or `h2.title{…}`).
- Prefix ids and `@keyframes` (`pipe-ah`, `pipe-pop`); use classes inside scripts.
- Fragment `<script>` runs before the kit engine. Wrap it in an IIFE, find its slide with
  `document.currentScript.closest('.slide')`, and react to `kit:step`/`kit:unstep` or to the
  slide's `active` class (MutationObserver). Do not call kit functions at load.
- `assemble.py` warns about duplicate ids, dangling `data-goto` and viewport units.

## 3. Content rules
- Show, don't tell: the slide carries the picture; explanations are spoken.
- Minimal text. Never add captions, sub-labels, role text or UI hints that the author did not
  give. Ask; lean toward more relevant questions.
- Real, sourced data. Illustrative values are labelled on the slide; ask before presenting
  fabricated specifics.
- One idea per slide; parallel structure; consistent semantic colors.
- Reveal in placement/flow order; group sensibly.
- Internal padding on every component; if content is tight, shrink the font, never clip.
- Paper figures are embedded as images, never redrawn.

## 4. Arrows and connectors
1. Compute once, never move: one SVG overlay with `viewBox="0 0 1280 720"`; coordinates from
   element geometry after fonts/layout settle (double `requestAnimationFrame` + ~400 ms
   timeout) and again on resize or slide activation, never on a reveal step.
2. Reveal = opacity only: `.<slidecls> .step{transform:none}`; a step only toggles its arrow
   group's opacity (`applyShown()`).
3. Full, aligned arrows: stroke `#9aa3b2`, width 3, filled `<marker>` head.
4. Within a row: right edge of box k → left edge of box k+1, gap `PAD ≈ 10px`.
5. Between rows: entry arrow only (≈ 34px) into the left edge of the next row's first box. No
   stub off the previous row's right edge (it dead-ends and clips at the canvas edge).
6. Labels 11px, static, ~10–12px above the arrow, clamped to x ∈ [70, 1210].
7. `rectOf(el)`: `x_c = (x_screen − slide.left) · 1280 / slide.width`, same for y with 720, so
   arrows land on box edges at any zoom.

## 5. Build and verify, per slide
1. Get content; ask for anything missing.
2. Storyboard: entry + N steps; confirm labels.
3. Author the fragment (px/cqw/cqh, kit classes, scoped CSS).
4. `python3 <skill>/scripts/assemble.py frag.html out.html`; clear all warnings.
5. `python3 <skill>/scripts/shot.py out.html shots/name N --check`; read every PNG.
   - entry correct; each PNG adds exactly one bucket;
   - arrows identical across steps (`check.arrows_moved` empty) and not clipped;
   - nothing below canvas y = 620 (`check.below_safe_area` empty);
   - `real_errors` empty. Failed web-font requests offline are filtered out; fallback fonts in
     screenshots are acceptable.
6. `--size 1024x768`: same picture, letterboxed.
7. Drill-down: add `--click '[data-goto=ID]'` and `--click '#back'` and read those PNGs.
8. Iterate until everything passes.

`shot.py` actions after the N advances (`--click`, `--then`) run in the given order:
`right`, `left`, `right*K`, `left*K`, `click:SEL`, `key:KEY`, `slide:K`. Quote `right*K` in
zsh. Rapid `right*K` presses can catch a staggered animation mid-way; use single steps when
judging an animated step.

## 6. Do-not-regress table

| # | Symptom | Rule |
|---|---|---|
| 1 | Cream or colored background | White master, `--paper:#fff` |
| 2 | Title centered or low | Title first, top-left, 48px |
| 3 | Kicker/eyebrow above the title | Never on content slides |
| 4 | Logos missing or slide looks off-master | Always build against `assets/kit.html` |
| 5 | Invented labels or captions | Ask; name + icon only meanwhile |
| 6 | Components too small | Enlarge; wrap to 2–3 rows rather than shrink |
| 7 | Conceptual step too fast | Stagger chips ~0.3 s inside one step |
| 8 | Matrices look fake | Float grids with `…`/`⋮`, highlighted rows |
| 9 | Neural block with a lone input/output node | Hidden layers only, several nodes per column |
| 10 | Item counts change across a transform | Keep counts unless the transform changes them |
| 11 | Probability readout cluttered | Token-aligned rows, `0.58`, `P` header, no bars |
| 12 | Blurry logos | Embed at ≥ 2× display width |
| 13 | Content shifts or disappears on another screen | Fixed canvas + transform; no vw/vh |
| 14 | Arrows move between clicks | Compute once; opacity-only reveal; `.step{transform:none}` |
| 15 | Dead-end arrow off a row's right edge | Entry arrow only between rows |
| 16 | Arrow labels touch boxes or clip | 11px, static, gap, clamped |
| 17 | Text touches a box border | Padding on every box; shrink font first |
| 18 | Prev/next buttons look like arrows | Not shipped |
| 19 | One-hot or id vectors cramped | Wide vectors, ids as columns with `…`, `⋮` centered |
| 20 | "Click to open" text on screen | Never; say it or put it in notes |
| 21 | Sub-labels / role text added unasked | Name + icon only unless given |
| 22 | Fragment CSS leaks into other slides | Scope every rule under the slide class |
| 23 | Two arrow slides break each other | Prefix ids, markers, keyframes per slide |
| 24 | Accent border missing | Use kit tokens only (`--en --sa --bo --gr`) |
| 25 | Hidden component clicked by accident | Kit sets `.step:not(.shown){pointer-events:none}` |
| 26 | Fragment script fails at load | IIFE + `currentScript.closest('.slide')`; no kit calls at load |
