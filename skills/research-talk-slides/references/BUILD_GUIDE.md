# Build guide — kit architecture, conventions, do-not-regress table

Load this before authoring the first slide of a session, and whenever a slide fails
verification. SKILL.md has the procedures and the rules in one line each; this file has the
reasons and the details. ML-specific drawing conventions (tokens × layers grid, matrices,
neural blocks, probability readouts) are in `ml-visuals.md`.

## 1. Layout of the skill and of a talk

```
<skill>/assets/kit.html            the kit (do not copy-edit per slide)
<skill>/scripts/assemble.py        fragment(s) -> standalone deck
<skill>/scripts/shot.py            screenshots per reveal step (+ --check)
<skill>/scripts/tex2svg.py         TeX -> static inline SVG, at build time
<talk>/PRD.md                      the author's words, verbatim (who asked, which session)
<talk>/SPEC.md                     storyboards + slide order; superseded ones -> SPEC-archive.md
<talk>/TBD.md                      open questions (they survive a restart)
<talk>/ORDER.txt                   fragment paths in talk order (for assemble.py --order)
<talk>/fragments/00-master_fragment.html   the talk's shared CSS/JS, logos, fonts
<talk>/fragments/NN-<slug>_fragment.html   EDITABLE source: <section>(s) + own <style>/<script>
<talk>/build/NN/                   generator of a generated fragment (§8)
<talk>/<talk>.html                 assembled deck (open by double-click)
<talk>/shots/<name>_NN.png         verification screenshots
```

A small talk may keep PRD, SPEC and TBD in one PLAN file and its fragments next to the deck.

Why fragments: the kit is the single source of the master and engine; a fragment holds only
what is specific to its slide, so slide work stays small and every slide shares one shell.
`assemble.py` replaces the region between `SLIDES:START` / `SLIDES:END` in the kit.

## 2. The kit

### 2.1 Master
- Background white (`--paper:#fff`).
- Title: `<h2 class="title">`, top-left, Open Sans 700, 48px, one per slide. No `.kicker`
  on content slides. The kit styles `h1.title` like `h2.title`; a title slide may enlarge and centre its
  `h1.title` in its own scoped CSS.
- Logo slots bottom-left (192px wide) and bottom-right (132px wide), 16px from the bottom,
  **hidden until set**. Set them once, in the master fragment's `<style>` or in the kit:
  `:root{--logo-left:url("data:image/png;base64,…"); --logo-right:url("right.png")}`, or
  replace a slot `<div>` with `<img class="brand brand-left" src="…">`. Embed at ≥ 2× display
  width. `<body class="show-logo-slots">` outlines the empty slots while laying out.
- Slide padding `52px 64px 100px`: content must end above canvas y = 620.

### 2.2 Palette and fonts (`:root`)
```
--ink:#1a1a1a  --paper/--panel:#fff  --line:#e2e0d8  --muted:#5e6470  --tint:#eef2fb
--en:#1b2a4a navy (primary)  --sa:#3b7dd8 blue  --bo:#e8833a orange  --gr:#5a8f69 green
--title:'Open Sans'  --display:'Space Grotesk'  --serif:'Spectral'  --mono:'JetBrains Mono'
```
One semantic colour per concept, reused everywhere it appears. Only these tokens exist; a
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

> **Reveal order follows the DOM, not the `data-step` number.** A bucket's place in the
> sequence is the smallest DOM index among its members. To move a step earlier, move its
> element earlier in the markup; renumbering `data-step` changes only which elements group.

- A slide: `<section class="slide" data-section="N · Name" data-title="...">` (§2.8).
- Non-`.step` content shows on entry. `.step` elements reveal one **bucket** per advance.
  Elements sharing `data-step="k"` form one bucket; a `.step` without `data-step` is its own
  bucket. So the number of advances on a slide equals its number of buckets.
- Keys: `→`/PageDown/click/space next, `←`/PageUp back, touch swipe (> 50 px), `O` section map, `N` notes, `F` fullscreen, dots jump.
  The key hint at the bottom shows on load (so a published copy still teaches the keys), fades
  after the first navigation key or click and stays hidden; `?` or `H` toggles it back.
- **Click guard.** A plain click advances. A drag (the mouse moves more than 4 px between down
  and up) does not, and neither does a click while text is selected (e.g. a shift-click that
  extends a selection). A double-click is net zero wherever the browser selects a word (almost
  everywhere on a slide): the second click undoes the first, including the drill-down back
  stack. A triple-click adds nothing. Buttons, links, inputs, `[data-goto]`,
  `[data-noadvance]` and the kit chrome never advance.
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
`.panel` (rounded card, coloured left accent via `.en/.sa/.bo/.gr`), `.chip` (mono token box,
`.sa`/`.bo` tints, `.pop` animation), `.counter` (large mono number), `.card` (titled card),
`.sub` (serif subtitle), `.btn`, `.note`, plus layout helpers (`.arena`, `.stage-cell`, `.chips`, `.meta`,
…; see the kit). Slide-specific visuals (matrices, nets, heat grids,
charts) are built in the fragment (conventions in `ml-visuals.md`).

`.halo` outlines text in white for a label that sits on a busy figure or a heat map:
`<text class="halo">` in SVG gets `paint-order: stroke fill; stroke: var(--halo);
stroke-width: 4px; stroke-linejoin: round` (the outline is painted under the glyph fill);
HTML text (`<span class="halo">`) gets a white `text-shadow` stack. `--halo` sets the colour
(default `#fff`). Leave it off for text on white.

### 2.6 Fragment hygiene (needed once fragments share one deck)
- Give each section its own class and scope **every** rule under it
  (`.pipe .box{…}`, never bare `.box{…}` or `h2.title{…}`).
- Prefix ids and `@keyframes` (`pipe-ah`, `pipe-pop`); use classes inside scripts.
- Fragment `<script>` runs before the kit engine. Wrap it in an IIFE, find its slide with
  `document.currentScript.closest('.slide')`, and react to `kit:step`/`kit:unstep` or to the
  slide's `active` class (MutationObserver). Do not call kit functions at load.
- `assemble.py` warns about duplicate ids, dangling `data-goto`, viewport units and the deck
  lints of §7.2.

### 2.7 Slide numbers and progress bar (off by default)
A fragment cannot edit the kit's `<body>`, so both are turned on at assembly:
`assemble.py … --body-class "slide-numbers progress"` (or one of the two). A master fragment
can also run `<script>document.body.classList.add('slide-numbers')</script>`.

- **`slide-numbers`**: a running number in the logo band (`#kit-num`, 15 px mono, muted). It
  follows DOM order, 1-based, so it matches `shot.py --start K`; drill-down detail slides
  count (§2.8). The first (title) slide counts as 1 and shows no number; `data-nonum` on a
  slide hides its number but it still counts. Position: `right: var(--num-right)` (default
  170px, just left of the right logo slot), `bottom: var(--num-bottom)` (default 36px); move
  it with e.g. `:root{--num-right:134px; --num-bottom:39px}`.
- **`progress`**: a 6 px bar along the bottom edge (`#kit-bar`) that moves on every slide and
  on every reveal step; hidden on the title slide. It replaces the 3 px top bar (`#prog`) and
  the side dots (`#dots`). Position =
  (steps of all earlier slides + earlier slides + steps shown here) / (all steps + all slides − 1).
  Example: slides with 0, 2, 0 and 1 steps give a denominator of 3 + 4 − 1 = 6, and the bar
  reads 0 on slide 1; 1/6, 2/6, 3/6 on slide 2; 4/6 on slide 3; 5/6 then 6/6 on slide 4.
- The chrome ids are `kit-num` and `kit-bar` so that a master that builds its own bar (e.g. a
  `#deckbar`) is not hidden by a kit rule.

### 2.8 Sections, numbering and notes
- **Section labels read "N · Name"** (`data-section="4 · Patching"`), the same style on every
  slide except the title slide. `assemble.py` warns when styles are mixed (`3` next to
  `4 · Patching`).
- **A section's slides are contiguous.** A section that recurs after another one (1, 2, 1)
  splits in the section map; `assemble.py` warns.
- **`data-title` is unique** in the deck; two equal titles cannot be told apart in the map.
- **Drill-down detail slides are numbered linearly**: they sit right after their overview in
  the DOM and take the next numbers, like any slide. There is no "7a / 7b" scheme.
- **Speaker notes cite slides by title, never by number** ("as on *Activation patching*"),
  because numbers move whenever a slide is added.

### 2.9 Maths: pre-render TeX at build time
No runtime MathJax in a deck: it needs the network in the room and reflows after load.
Render each formula once with `scripts/tex2svg.py` (MathJax 3 in headless Chromium) and paste
the inline SVG into the fragment or the generator:
`tex2svg.py '\alpha_i' --display`, or `tex2svg.py --json IN.json OUT.json` for a batch.
It **needs the network** at build time (it fetches MathJax from jsDelivr) and Playwright; its
output is self-contained, works offline and draws in `currentColor`.

## 3. Content rules

Each rule is one line in SKILL.md's non-negotiables; the detail is here.

- **Show, don't tell.** The slide carries the picture; explanations are spoken. Replace any
  explanatory sentence with a scheme, a symbol or a formula. A rich picture is fine; a paragraph
  is not. A cheap or thin visual is a defect too.
- **Titles are plain, direct, exact and technical.** Name what the slide shows ("Attention
  pattern of head 3.2"), never a catchy phrase ("Who talks to whom").
- **Minimal text, nothing invented.** No captions, sub-labels, role text, UI hints, "?",
  "provisional", claims or status markers the author did not give; no recoloured semantics;
  no sizes the storyboard did not ask for. Ask; lean toward more relevant questions.
- **Reveal granularity.** A process gets one step per stage, in placement/flow order: never
  all at once, and never padding steps. Not every word gets a step.
- **Symbol key on the slide.** Every symbol is glossed on the slide that uses it, in the step
  it first appears, as a muted key line of at least 16px. Never rely on an earlier notation
  slide. At most 4 key lines per slide; more means the slide carries too many symbols.
- **Every connector means something.** Every arrow, dashed line and legend entry is explained
  on screen. Prefer a label on the drawing to a legend.
- **Every number has a definition.** A metric on screen shows what it measures (a formula or a
  comparison), never a bare "restored 0.50".
- **One visual language.** Reuse the deck's components (readouts, forward-pass drawing, block
  illustration) through a shared generator module (§8) rather than redrawing them per slide.
  One semantic colour per concept; a concept colour must contrast with the body ink.
- **Faithful notation and maths.** Notation follows the source. Formulas are checked against
  the paper. Index, shape and matrix conventions hold across the deck (`ml-visuals.md`).
- **Real, sourced data.** Illustrative values are labelled on the slide; ask before presenting
  fabricated specifics.
- **Results figures.** Copy the project's figures exactly (axes, units, resolution); embed
  paper figures as images, never redrawn. Every plot names its dataset and n; every panel has a
  y-axis.
- **Small conventions.** An example input sits in a box with a header naming it; the running
  example is named on screen, never by a nickname; citations go in the notes, with at most an
  origin tag on the slide; one spotlight at a time, and only where it adds something.
- One idea per slide; parallel structure.
- Internal padding on every component; if content is tight, shrink the font, never clip.

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
6. Labels 12px, static, ~10–12px above the arrow, clamped to x ∈ [70, 1210].
7. `rectOf(el)`: `x_c = (x_screen − slide.left) · 1280 / slide.width`, same for y with 720, so
   arrows land on box edges at any zoom.

## 5. Spotlight

On one reveal step, whiten the slide except one region (and the title), ring that region, and
optionally put the author's caption beside it with a leader line. The next step clears it; `←` brings it
back. The kit draws everything from a marker element, so a fragment carries no spotlight CSS or
JS. Copyable pattern: `references/example_spotlight_fragment.html`.

```html
<i class="spot step" data-step="3" data-spot=".fig img"
   data-spot-rect="0.6667,0.25,0.1667,0.25" data-pad="4"
   data-caption="one cell of the figure" data-caption-pos="above" data-tone="sa"></i>
```

| Attribute | Value | Default |
|---|---|---|
| `class="spot step"` | required; a marker without `step` never lights (`assemble.py` warns) | — |
| `data-step` | joins a bucket, like any step (optional) | own bucket |
| `data-spot` | CSS selector, resolved inside the slide: a panel, an SVG `<g>`, an `<img>`, … | required |
| `data-spot-rect` | `x,y,w,h` as fractions 0–1 of the target: a sub-rectangle of a figure | whole target |
| `data-pad` | canvas px between the target and the ring | `8` |
| `data-caption` | the author's text, shown verbatim (`textContent`, never HTML) | no caption |
| `data-caption-pos` | preferred side: `above` \| `below` \| `right` \| `left` | first that fits, in that order |
| `data-caption-lane` | `top` \| `bottom`: fixed band (rule 11); overrides `data-caption-pos` | beside the ring |
| `data-tone` | ring and caption border colour: `en` \| `sa` \| `bo` \| `gr` | `--spot-ring` |
| `data-veil-title` | flag (no value): whiten the slide title too, for this marker's bucket | title stays bright |
| `data-ring` | `none` only: cut the hole (it stays bright) but draw no ring, leader or caption; corner radius min(8, pad), so pad 0 cuts the exact box. Use it beside a ringed marker in the same bucket to keep context bright | ring drawn |

Rules:
1. A spotlight is lit exactly while its bucket is the **last bucket revealed** on the active
   slide, whatever brought you there: `→` lights it, the next `→` clears it, `←` restores the
   previous state exactly, a dot or map jump starts with nothing lit, and leaving the slide
   clears it. Arriving fully revealed (`←` from the next slide, `‹ back`) lights a spotlight only
   when the slide's last bucket is one (the state you left); a spotlight from an earlier bucket is
   never left on.
2. Bucket order is DOM order, not the `data-step` number: place each marker where its step falls
   in the flow (after the previous bucket's elements, before the next). Markers take no space
   (`display:none`), so they can sit anywhere in the DOM.
3. The slide title (`h1.title`, `h2.title`, `.stitle`) stays bright: its text box (+6/+4 px) is a
   hole in every veil, because the title is context, not a competitor. `data-veil-title` on any
   marker of a bucket whitens it for that bucket.
4. Several markers in one bucket share one veil with several holes: nothing is dimmed twice.
   With `data-ring="none"` on some of them, only the others are ringed (e.g. one ringed dot plus
   a ring-less hole over the columns read so far). A marker may also share a bucket with
   ordinary steps (the spotlight lands as they appear).
5. Geometry is computed once, like the arrows: canvas coordinates via `rectOf`, on slide
   activation (double rAF + ~400 ms), resize, image load and font load, never on a step; a step
   only toggles opacity (`.spot-g.on`). A slide with a marker gets `.has-spot`, which makes its
   steps reveal by opacity only (`transform:none`), so a target inside a not-yet-revealed step is
   measured where it will land.
6. `data-spot-rect` on an `<img>` drawn with `object-fit: contain` or `scale-down` refers to the
   drawn picture, not its letterbox: read the fractions off the source figure.
7. The hole is the target plus `data-pad`, kept inside the canvas; the pad never pushes the ring
   below y = 616 unless the target itself is lower. Captions stay in x ∈ [16, 1264],
   y ∈ [16, 612]; the leader runs from the caption edge to the ring, and is dropped when a clamped
   caption leaves no room for it.
8. Layers: veil and ring at z-index 35, caption at 36, inside the slide: above slide content,
   below the logos (40), `‹ back`, notes and map. All have `pointer-events:none`, so clicks reach
   revealed elements, `data-goto` components and the nav through the veil.
9. Tokens in `:root`: `--spot-dim` (veil, `rgba(255,255,255,.72)`: it whitens, like the master),
   `--spot-ring` (`var(--bo)`), `--spot-lead` (the arrows' `#9aa3b2`). Override them in a
   fragment's `<style>` on `:root`; never hard-code a colour.
10. Errors are loud: a selector that matches nothing, an invalid selector, a malformed
   `data-spot-rect`, `data-caption-pos`, `data-caption-lane`, `data-tone`, `data-pad` or `data-ring` (anything but
   `none`, or `none` with a caption) logs a console error, which
   `shot.py` reports under `real_errors`; `assemble.py` also warns on a malformed
   `data-spot-rect`, a bad `data-ring` and an invalid `data-caption-lane` (§7.2).
11. `data-caption-lane` puts the caption in a fixed band instead of beside the ring, centred on
   the ring horizontally and clamped to x 16–1264. `top`: its top edge at canvas y 16, above the
   title band, leader to the ring's top edge. `bottom`: its bottom edge at y 612, just above the
   logo band, leader to the ring's bottom edge. Use it when `data-caption-pos` would put the
   caption on the subtitle or other text.

Verify like any step (§6). `shot.py` adds `"spot"` to each shot of a slide that has markers: the
lit targets' selectors (`" @x,y,w,h"` appended for a sub-rect, `" [no ring]"` for a
`data-ring="none"` hole), `[]` when none is lit.
`--check` exempts the veil from the safe-area test (it covers the canvas by design) but checks
the ring, leader and caption; the ring and veil paths count in `arrows_moved`, so a spotlight
that moves between steps fails like an arrow.

Pitfalls: a ring around an element that is still animating (a `.pop` chip) is measured
mid-animation, so ring its static container; a target whose own transform differs between its
shown and hidden states (a fragment's `.x .step.shown{transform:scale(1.1)}`) is measured hidden;
a caption is the author's words or nothing.

## 6. Build and verify, per slide

The steps are SKILL.md P1; this section is the pass checklist and the tooling.

Screenshot with JSON to a file, under `timeout` (a hung renderer is caught by
`--step-timeout`, but a stuck launch is not yours to wait for):

    timeout 600 python3 <skill>/scripts/shot.py out.html shots/name --all --check --json shots/name.json

Read every PNG. Pass when:
- the entry state is correct and each PNG adds exactly one bucket;
- arrows are identical across steps (`check.arrows_moved` empty) and not clipped;
- nothing is below canvas y = 620 (`check.below_safe_area` empty);
- no text runs out of its box (`check.overflow` empty), including the 1906×1000 pass;
- no `WARNING:` small text (`check.small_text` empty): legible text is ≥ 12 canvas px, body
  text ≥ 16px;
- spotlight steps: `spot` lists the right target, the PNG shows the dim + ring on that region,
  and the next shot clears it; check one `--then left` back-step restores it (§5);
- every formula is visibly rendered (a blank area passes `--check`, so look);
- `real_errors` empty. Failed web-font requests offline are filtered out; fallback fonts in
  screenshots are acceptable.

Then `--size 1024x768`: the same picture, letterboxed. Drill-down: add
`--click '[data-goto=ID]'` and `--click '#back'` and read those PNGs.

### 6.1 shot.py options
- `--all` advances until the last step of the last slide, so no count is guessed; it stops
  early if an advance changes nothing, and combines with `--start K` (K → end). A positional
  count given with it is ignored.
- `--json FILE` writes the JSON result to FILE and leaves stdout empty; every diagnostic goes to
  stderr (`REAL ERRORS: …`, warnings, `CHECK FAILED at …`, `wrote FILE (N shots, pass|FAIL)`).
  A hang result is written to FILE too.
- `--check` runs the arrow and safe-area checks plus:
  - **box fit**: no visible HTML text runs outside the nearest box that frames it (a border,
    a background, or clipped overflow) by more than 1.5 canvas px (`shots[i].overflow`,
    `check.overflow`); a hit fails the check;
  - **an extra size pass**: the same sequence replayed at **1906×1000** (a maximised desktop
    browser window) with the arrow, safe-area and box-fit checks; a PNG is saved only for a
    failing shot (`PREFIX_NN@1906x1000.png`); results in `check.sizes["1906x1000"]`.
    `--check-size WxH` is repeatable and replaces the default; `--check-size none` skips it.
    The fixed canvas makes layout scale-invariant, so this pass catches CSS that reads the
    real viewport (media queries, vw units) and font rasterisation differences;
  - **small text**: visible text rendered below 12 canvas px (CSS font size times every
    transform up to the canvas, SVG viewBox scaling included); a warning, not a failure.
- `--wait` (default **1200 ms**) is the settle time after each action. A kit reveal fades for
  0.5 s, the spotlight lays out 0.4 s after activation and then fades for 0.35 s, and slide
  transitions take 0.5 s; at the old 550 ms, screenshots caught mid-fade frames. Use
  `--wait 1700` on slides with their own animations.
- Actions after the advances (`--click`, `--then`) run in the given order: `right`, `left`,
  `right*K`, `left*K`, `click:SEL`, `key:KEY`, `slide:K`. Quote `right*K` in zsh. Rapid
  `right*K` presses can catch a staggered animation mid-way; use single steps when judging an
  animated step.
- `--step-timeout S` (default 30) ends a run whose slide script loops with `hang`/`stuck_at`.
  Launching Chromium has its own limit of at least 60 s, so a slow launch on a busy machine is
  not reported as a hang at `load`.

### 6.2 No-root runner (fallback)
On a machine without root, `python -m playwright install --with-deps` cannot install
Chromium's system libraries (libatk, libgbm, libXcomposite, …). Unpack them from the
distribution's packages into a user folder (e.g. `~/.local/lib/chromium-deps/root`) and run a
pinned Playwright through uv:

    export LD_LIBRARY_PATH="$HOME/.local/lib/chromium-deps/root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    uv run --quiet --no-project --with playwright==1.64.0 python <skill>/scripts/shot.py DECK.html PREFIX --all --check --json out.json

The tests run the same way from the repo root:
`REQUIRE_PLAYWRIGHT=1 uv run --quiet --no-project --with playwright==1.64.0 python -m unittest discover -s tests -v`
(add `--with pillow` for `tools/make_demo_gif.py`). A small wrapper script that sets the
library path keeps the arguments identical to shot.py's.

## 7. Assembling a deck; several sessions on one deck

### 7.1 Stitch
The recommended stitch (no `sed` on the title, no shell loop over missing fragments).
`--allow-missing` is for mid-build stitches; the final stitch (§10) runs without it.

    assemble.py -o talk.html --master fragments/00-master_fragment.html \
      --order ORDER.txt --allow-missing --title "Talk title" --body-class "slide-numbers progress"

| Option | Effect |
|---|---|
| `--title TEXT` | sets `<title>` (HTML-escaped); replaces the kit's "Slide Kit" |
| `--body-class CLS` | adds classes to the kit's `<body>` (§2.7) |
| `--master FILE` | spliced first; dropped from the list if it is also listed there |
| `--order FILE` | one fragment path per line, relative to the order file's folder; `#` comments and blank lines skipped; command-line fragments come after it; needs `-o` |
| `--allow-missing` | a missing fragment is a warning (stderr and `"warnings"`) and listed under `"skipped"`; otherwise exit 2 |
| `--asset-base DIR` | rewrites relative `assets/…` and `./assets/…` in `src`, `href`, `poster`, `data-src`, `srcset` and CSS `url()` to `DIR/assets/…` (count in `"asset_rewrites"`); absolute URLs and plain text untouched |

Preview one generated fragment from `build/NN/` with the talk's `assets/` two levels up (the
two-argument form and `--master` combine; the master is spliced first):

    assemble.py build/31/31-grid_fragment.html build/31/preview.html \
      --master fragments/00-master_fragment.html --asset-base ../..

### 7.2 Deck lints (warnings; the exit code is unchanged)
- `FILE: N U+FFFD replacement character(s)`: an invalid UTF-8 byte (read with
  `errors="replace"`, so it warns instead of crashing). A publish may refuse the deck (§10).
- The vw/vh check skips `data:` URIs (base64 can spell `5vw`).
- Duplicate `data-title`; non-contiguous `data-section`; mixed `data-section` styles (`number`
  "3", "03a", "4.2" / `number · name` "4 · Patching" / `name` "Results"; the title slide is
  exempt) (§2.8).
- **Unscoped kit-class CSS**: a fragment `<style>` rule whose first compound selector, after
  `html`, `body`, `#stage` and `.slide`, is made only of kit classes (`.chip`,
  `.slide .panel .name`, `.chip.sa:hover`, `.card` inside `@media`) restyles that class on
  every slide. `.myslide .chip`, `#id .panel` and `[data-id=x] .card` are fine.
- Spotlight markers (§5): missing `class="spot step"`, malformed `data-spot-rect`, `data-ring`
  other than `none` (or `none` with a caption), invalid `data-caption-lane`.

### 7.3 Several sessions on one deck
When more than one top-level session works on the same talk:
- One owner session per section, recorded in SPEC.md.
- Only the deck orchestrator edits `ORDER.txt`, `00-master` and the stitch, and publishes.
- Other sessions send cross-section edits to the owner as proposals, never edit them directly.
- Each PRD.md entry records the session that took it down.
- After each merge, re-stitch and re-verify the deck.

## 8. Generated fragments

A slide whose markup is computed (a grid, a matrix, a readout from data) is generated, and the
generator is the source; the fragment is output.
- The generator lives in the talk's `build/NN/` (e.g. `build/NN/gen.py`), never in a scratch
  folder, and writes the installed fragment. Edit the generator, never the fragment.
- Every `build/NN/` has a `README.md`: what it generates, the command, its inputs and its
  **rebuild dependencies** (data files, shared modules), so a change to a shared module
  rebuilds every fragment that imports it.
- Every value on screen is read from its data source and **asserted** against it in the
  generator, not typed in.
- **Byte-identical rebuild check** before any edit: run the generator to a scratch path and
  `cmp` it with the installed fragment. A difference means someone edited the fragment by
  hand: stop and report rather than overwrite it.
- Parallel builders on one section share `build/NN/common.py` (colours, sizes, drawing
  helpers), and deck-wide components (readouts, forward-pass drawing) live in one shared module
  imported by every generator (§3, one visual language).

## 9. Patterns

### 9.1 Camera / zoom continuity
A zoom from slide A into a region of A on slide B reads as one camera move only if B starts
exactly where A ended:
- B's entry state redraws **A's final frame exactly**: same elements, positions, sizes and
  colours (generate both from the same code). The zoom is B's first step, a transform on one
  wrapper.
- Avoid the **fade-from-white dip**: slides cross-fade over 0.5 s on a white stage, so two
  identical frames still flash pale mid-transition. Turn the slide transition off on both
  slides of the pair (`.slide.<clsA>,.slide.<clsB>{transition:none}`): the change is then a
  cut between identical frames, which is invisible, in both directions. Check with `shot.py`
  across the cut, forwards and back.

### 9.2 Lift text, keep geometry (embedded page SVGs)
An SVG taken from a paper page or another tool carries its own fonts, sizes and often text as
outlines. Keep its geometry (paths, boxes, arrows) as it is; lift the text out: delete its
`<text>` (or glyph paths), and re-set each label as kit text (SVG `<text>` in the deck's
fonts, at a legible size, `.halo` where it sits on the drawing) at the same coordinates in the
SVG's `viewBox`. Scope or strip the SVG's `<style>`: an unscoped `.chip{}` or `.card{}` in it
restyles every slide (§7.2).

## 10. Publish (P6)

Before a deck leaves the machine (a hosted page, an e-mail, a shared drive):
1. **Self-contained**: every image is a data URI or ships beside the deck; no local path
   remains (`grep -oE '(src|href)="[^"#][^"]*"' deck.html | grep -v 'data:\|https:'` prints
   nothing); the size is within the host's limit. Web fonts load from Google, so bundle them
   when the room is offline (row 31).
2. **No U+FFFD**: `grep -c $'\xef\xbf\xbd' deck.html` prints 0 (`assemble.py` warns per
   fragment); a host may refuse a page that contains it.
3. **Personal-data and logo scan**: names, e-mail addresses, local paths (`/home/`,
   `/Users/`), unpublished numbers, and the speaker notes, which ship inside the HTML; logos
   only where their use is allowed.
4. **Title**: `--title` set to the talk's title, never the kit's "Slide Kit".
5. **Complete**: the final stitch runs without `--allow-missing`, so `"skipped"` is empty and
   no skipped-fragment warning is printed.
6. Re-run `shot.py --all --check` on the final file and read the PNGs.

## 11. Do-not-regress table

| # | Symptom | Rule |
|---|---|---|
| 1 | Cream or coloured background | White master, `--paper:#fff` |
| 2 | Title centred or low | Title first, top-left, 48px |
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
| 16 | Arrow labels touch boxes or clip | 12px, static, gap, clamped |
| 17 | Text touches a box border | Padding on every box; shrink font first |
| 18 | Prev/next buttons look like arrows | Not shipped |
| 19 | One-hot or id vectors cramped | Wide vectors, ids as columns with `…`, `⋮` centred |
| 20 | "Click to open" text on screen | Never; say it or put it in notes |
| 21 | Sub-labels / role text added unasked | Name + icon only unless given |
| 22 | Fragment CSS leaks into other slides | Scope every rule under the slide class |
| 23 | Two arrow slides break each other | Prefix ids, markers, keyframes per slide |
| 24 | Accent border missing | Use kit tokens only (`--en --sa --bo --gr`) |
| 25 | Hidden component clicked by accident | Kit sets `.step:not(.shown){pointer-events:none}` |
| 26 | Fragment script fails at load | IIFE + `currentScript.closest('.slide')`; no kit calls at load |
| 27 | Spotlight ring a few px off, different on every load | `.has-spot .step` leaves `transform` out of its transition, so adding the class at load does not slide the steps while they are measured |
| 28 | Spotlight veil greys the slide title | The title's text box is a hole in every veil; `data-veil-title` opts out per bucket |
| 29 | Key hint bar shows on every slide | Visible on load, fades after the first navigation key or click; `?`/`H` brings it back |
| 30 | Screenshot run freezes after a slide is left (renderer at full CPU) | A `MutationObserver` on the slide's `class` must write classes only when the state really changes and act only on an active ↔ inactive transition; `classList.remove` of an absent class still rewrites the attribute and re-fires the observer forever |
| 31 | Offline (no network in the room) titles change font, lines wrap | The kit loads fonts from Google; the fallback is ~17% wider. Bundle the woff2 files in the talk's `assets/fonts/` with `@font-face` rules (same family names) in the master fragment; verify with fonts.googleapis/gstatic blocked |
| 32 | Selecting text on a slide (drag, double-click) advanced the deck | Click guard: a drag > 4 px, a selection, or a word-selecting double-click gives no net advance (§2.4) |
| 33 | No slide numbers; notes and reviews cited "slide 23" by guessing | `--body-class slide-numbers`: DOM-order number, none on the title, `data-nonum` opt-out (§2.7) |
| 34 | Progress only per slide, with dots on the right | `--body-class progress`: step-aware bottom bar; replaces the top bar and the dots |
| 35 | Labels unreadable over figures | `.halo` (SVG stroke under the fill, HTML text-shadow) |
| 36 | Spotlight caption landed on the subtitle | `data-caption-lane="top\|bottom"` (§5) |
| 37 | A hosted publish refused the deck (U+FFFD) | `assemble.py` warns `FILE: N U+FFFD`; P6 check (§10) |
| 38 | False vw/vh warning from base64 images | The viewport-unit lint skips `data:` URIs |
| 39 | Two slides with the same title in the section map | Duplicate `data-title` warning |
| 40 | Section map split one section in two | Non-contiguous `data-section` warning; keep sections contiguous (§2.8) |
| 41 | Section labels "3" next to "4 · Name" | Mixed-style warning; use "N · Name" |
| 42 | An embedded page's `.chip{}` restyled every slide | Unscoped kit-class CSS warning; lift text, keep geometry (§9.2) |
| 43 | `sed` on "Slide Kit"; a shell loop for missing fragments | `--title`, `--order`, `--allow-missing`, `--master` (§7.1) |
| 44 | A preview in `build/NN/` lost its images | `--asset-base ../..` |
| 45 | Verifiers guessed advance counts (80–260) | `shot.py --all` |
| 46 | JSON broken by "REAL ERRORS" on a merged stream | `--json FILE`; all diagnostics on stderr |
| 47 | Text overflowed its box on a 1906×1000 desktop window, but `--check` passed | Box-fit check, plus a 1906×1000 pass inside `--check` |
| 48 | 10–11 px text passed review | Small-text warning (< 12 px) |
| 49 | Mid-fade screenshots | Default `--wait` 1200 ms; `--wait 1700` on animated slides |
| 50 | `--check` crashed with "el.getScreenCTM is not a function" on an SVG `<title>` or HTML in a `<foreignObject>` | The small-text pass skips title, desc and metadata, and calls getScreenCTM only where it exists |
| 51 | Catchy title ("Who talks to whom") | Plain, direct, exact, technical (§3) |
| 52 | A paragraph explains what a picture should show | Replace it with a scheme, symbol or formula (§3) |
| 53 | A whole process revealed in one click | One step per stage, no padding steps (§3) |
| 54 | A symbol defined only on an earlier notation slide | Key line on the slide that uses it, in the step it appears (§3) |
| 55 | Arrow, dashed line or legend entry left unexplained; a bare metric value | Explain every connector on screen; every number shows its definition (§3) |
| 56 | The same component drawn differently on two slides | One shared generator module (§8) |
| 57 | A hand edit to a generated fragment lost on rebuild | Edit the generator; byte-identical rebuild check first (§8) |
| 58 | A builder built its default while a question was open | STOP means stop: build nothing until the question is answered |
| 59 | Zoom into a region flashes pale between the two slides | Redraw A's final frame exactly on B; no slide transition across the cut (§9.1) |
