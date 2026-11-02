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
<skill>/scripts/anim.py            SVG/CSS helpers for generators: transfer(), label_clear() (§8)
<talk>/PRD.md                      the author's words, verbatim (who asked, which session)
<talk>/SPEC.md                     storyboards + slide order; superseded ones -> SPEC-archive.md
<talk>/TBD.md                      open questions (they survive a restart) + the intake ledger (§7.3)
<talk>/ORDER.txt                   fragment paths in talk order (for assemble.py --order)
<talk>/fragments/00-master_fragment.html   the talk's shared CSS/JS, logos, fonts
<talk>/fragments/NN-<slug>_fragment.html   EDITABLE source: <section>(s) + own <style>/<script>
<talk>/build/NN/                   generator of a generated fragment (§8)
<talk>/build/_shared/              modules imported by several generators; orchestrator-owned (§8)
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
**The colour rule** (this is its one home; §3 and SKILL.md point here):
- One semantic colour per concept, reused on every slide where the concept appears.
- A concept colour contrasts with the body ink **and with every other concept colour shown
  with it**: take two concepts from different hue families (`--sa` blue beside `--bo` orange),
  never a blue beside a cyan or a second blue. Check the pair side by side in the PNG at body
  text size.
- Use kit tokens only. A reference to an undefined variable (e.g. `var(--c1)`) silently drops
  the property (row 24).

For non-Latin scripts add a Noto family to the Google Fonts link in the kit.

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
- Backup slides, toggles, hide-at-a-later-step, autoplay and the replay guard: §2.10.
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
Components: `.panel` (rounded card, coloured left accent via `.en/.sa/.bo/.gr`), `.chip` (mono
token box, `.sa`/`.bo` tints, `.pop` animation), `.counter` (large mono number; `<small>` for its
unit line), `.card` (titled card: `.ci` label line, `h3`, `p`), `.sub` (serif subtitle), `.btn`
(`.btn.ghost` outlined), `.note` (12 px mono, muted), `.pbox` + `.pbox-h` (prompt box, §2.10),
`.illus` (illustrative tag, §3), `.halo` (below).

Layout classes:

| Class | Lays out |
|---|---|
| `.arena` | a column of panels, 14 px apart |
| `.panel` / `.lang` | one row: a `.meta` label column, then a `.stage-cell` |
| `.meta` | the fixed 140 px label column of a panel (holds `.name`, `.counter`) |
| `.name` | the 19 px bold component name, in the panel's accent colour |
| `.stage-cell` | the flexible cell beside `.meta`; centres its content and clips overflow |
| `.chips` | a wrapping row of `.chip`s, 6 px gap |
| `.cards` | a wrapping row of `.card`s, 24 px gap |
| `.swap` | stacks its children in one grid cell, to replace A by B in place (§2.10) |

Slide-specific visuals (matrices, nets, heat grids, charts) are built in the fragment
(conventions in `ml-visuals.md`).

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
  counts on-path slides in DOM order, 1-based; drill-down detail slides count (§2.8), backup
  slides (`data-offpath`, §2.10) show none and are not counted. It equals `shot.py --start K`
  only while no backup slide comes earlier in the file; otherwise use `--start-id` (§6.1). The first (title) slide counts as 1 and shows no number; `data-nonum` on a
  slide hides its number but it still counts. Position: `right: var(--num-right)` (default
  170px, just left of the right logo slot), `bottom: var(--num-bottom)` (default 36px); move
  it with e.g. `:root{--num-right:134px; --num-bottom:39px}`.
- **`progress`**: a 6 px bar along the bottom edge (`#kit-bar`) that moves on every slide and
  on every reveal step; hidden on the title slide. It replaces the 3 px top bar (`#prog`) and
  the side dots (`#dots`). Backup slides are not counted; on one, the bar stays where the
  hub left it. Position =
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
  the DOM and take the next numbers, like any slide. There is no "7a / 7b" scheme. A detail
  that must stay out of the linear walk is a **backup slide** (`data-offpath`, §2.10): no
  number, skipped by → and ←, exempt from the contiguity lint.
- **Speaker notes cite slides by title, never by number** ("as on *Activation patching*"),
  because numbers move whenever a slide is added.

### 2.9 Maths: pre-render TeX at build time
No runtime MathJax in a deck: it needs the network in the room and reflows after load.
Render each formula once with `scripts/tex2svg.py` (MathJax 3 in headless Chromium) and paste
the inline SVG into the fragment or the generator:
`tex2svg.py '\alpha_i' --display`, or `tex2svg.py --json IN.json OUT.json` for a batch.
It **needs the network** at build time (it fetches MathJax from jsDelivr) and Playwright; its
output is self-contained, works offline and draws in `currentColor`. `--mathjax URL` loads
another MathJax build (a mirror, or a local copy on a machine behind a proxy); the default,
jsDelivr `mathjax@3.2.2` `tex-svg-full.js`, handles `\class{…}{…}` for colouring a symbol from
a kit token through CSS. Exit 1 if a formula fails to render.

### 2.10 Interaction attributes (1.2)
All optional: a deck without them behaves as with the 1.1 kit. The one always-on change is the
replay guard, which only shortens animations that would otherwise replay. Reference: the
"v1.2 ATTRIBUTES" comment at the head of `assets/kit.html`.

**Backup slides: `data-offpath`.** Extra detail that opens only on a click and is skipped in the
normal sequence.

```html
<section class="slide" data-section="3 · Results" data-title="Results"> …
  <div class="chip" data-goto="res-a">test A</div> <div class="chip" data-goto="res-b">test B</div>
</section>
<section class="slide" data-section="3 · Results" data-title="Test A in detail"
         data-id="res-a" data-offpath> … </section>
```

- The → / ← walk jumps over a backup slide; it opens only through `data-goto` (or `go()`,
  e.g. `shot.py --start-id res-a`).
- On a backup slide, → past its last step or ← before its first step returns to the slide that
  opened it (the drill-down history, so the hub comes back fully revealed). With no history it
  returns to the first on-path slide that links to it; with no such slide it stays put.
  `‹ back` and Backspace work as before.
- Several hubs may link to one backup (the history decides where it returns); a backup may link
  to another backup, and exits unwind the history one level at a time.
- Slide numbers, the progress bar, the top bar, the side dots and the O map count and list
  on-path slides only. `assemble.py` leaves backups out of the section-contiguity lint.
- A backup lives in its hub's fragment, so it is verified standalone with the hub (navigation
  resolves only within one file). A backup kept in a fragment of its own is verified by
  assembling hub + backup together; only then is a dangling-`data-goto` warning in a
  single-fragment preview expected.
- Backups work anywhere in the deck. The on-screen number counts on-path slides only, so after
  the first backup it is lower than the document position that `shot.py --start K` uses.
  Address slides with `--start-id` / `--start-title`, or put all backups at the end of the deck
  if numbers and K must agree.

**Replay guard (built into `go()`).** Arriving on a slide backwards (← from the next slide,
`‹ back`, any `go(n, true)`) or landing on a step > 0 shows its end states at once: every finite
CSS animation and transition inside the slide is jumped to its end (Web Animations `finish()`).
Infinite animations keep running; the slide's own cross-fade is not cut. Fragments no longer
need per-slide `*-instant` classes. Animations driven by JS timers are not covered: such a
fragment listens to `kit:step` / `kit:unstep` itself.

**Animation on entry: `data-autoplay` and `--anim-speed`.**

```html
<style>.qa .orbit.playing{animation:qa-orbit calc(6s / var(--anim-speed)) linear infinite}</style>
<div class="orbit" data-autoplay>…</div>
```

- The kit adds `playing` to every `[data-autoplay]` element of the active slide (and to the
  slide itself if it carries the attribute) and removes it on leaving, so the animation
  restarts from 0 on every entry. Animate only under `.playing`.
- A looping animation (`infinite`) runs while the slide is shown; a finite one plays once per
  forward entry, and arriving backwards shows its end state (replay guard).
- `--anim-speed` (default `1`, on `:root`) divides every duration written as
  `calc(Ts / var(--anim-speed))`: `2` plays twice as fast. Set it per deck
  (`:root{--anim-speed:.8}`) or per slide (`style="--anim-speed:1.5"`), so "slower" or "a bit
  faster" is a one-number change.
- Screenshot it with `shot.py --frames` (§6.1).

**Interactive toggles: `data-toggle="cls"`.**

```html
<button class="btn ghost" data-toggle="show-b">B</button>
<style>.cmp .b{opacity:0;transition:opacity .3s}.cmp.show-b .b{opacity:1}</style>
```

- A click toggles the class(es) (space-separated) on the control's slide. It never advances
  and never steps back.
- The slide returns to the classes it has in the HTML on leaving and on every step change, so
  no toggle state survives navigation.
- Enter toggles a focused control; space and the arrows always navigate. Non-button controls
  get `tabindex="0"` and `role="button"`; every control carries `aria-pressed` (with several
  classes, it follows the last one). A control inside an unrevealed `.step` does nothing.

**Hide or replace at a later step: `data-hide-at="k"`.**

```html
<p class="step" data-step="1" data-hide-at="3">shown at step 1, gone from step 3</p>
<div class="swap"><div data-hide-at="2">A</div><div class="step" data-step="2">B</div></div>
```

- Hidden (opacity 0, `visibility:hidden`, not clickable) while step `k` is revealed; shown
  again when stepping back before it. It keeps its layout space, so spotlight geometry is
  unaffected.
- `k` is a `data-step` key of the same slide; if the slide has no such key, a count (hidden
  from the k-th reveal on, 1-based). Anything else is a console error (`shot.py` reports it
  under `real_errors`) and the element is never hidden; a count beyond the last step never hides
  either, without an error. Reveal order is still DOM order (§2.4). Under
  `prefers-reduced-motion` the hide is instant (no fade).
- `.swap` stacks A and B in one grid cell, so B replaces A in place: use it for a with/without
  pair that flips in place (§3). It replaces `:has(.step[data-step="k"].shown)` CSS.

**Topic overview: `data-topic` + `body.ov-topics`.** With `--body-class "ov-topics"`, the O map
shows one heading per `data-section` and one tile per topic with its slide count; a tile opens
the topic's first slide. A topic starts at a slide with `data-topic="Name"`, at the first slide
and at every section change (named by that slide's `data-title`), and runs to the next start.
The map is built from the slides, so it is never stale. Without `ov-topics` the map is the 1.1
map and `data-topic` is ignored.

**Prompt box: `.pbox` / `.pbox-h`.** A tinted panel with a 5 px left edge in `--accent`
(default `--en`; `.en .sa .bo .gr`, or any colour via `style="--accent:…"`); `.pbox-h` is a
16 px muted header line inside it. Position and width come from the fragment. A master's own
`.pbox` rules override the kit's where they overlap (the kit's edge, padding and radius still
apply elsewhere); check the PNG. For example prompts, see §3.

**Illustrative tags: `.illus` + `body.no-illus`.** `class="illus"` (HTML or SVG text) marks the
on-slide "illustrative" tag (mono, muted); `--body-class "no-illus"` hides every one. Only the
class counts, never text matching. When to use it: §3.

Spotlight caption lane `below-title`: §5.

## 3. Content rules

Each rule is one line in SKILL.md's non-negotiables; the detail is here. The examples are
synthetic.

### 3.1 The slide
- **Show, don't tell.** The slide carries the picture; explanations are spoken. Replace any
  explanatory sentence with a scheme, a symbol or a formula. A rich picture is fine; a paragraph
  is not. A cheap or thin visual is a defect too.
- **Every slide states its purpose.** Its title or its first visible element says what the
  audience should take from it; a slide whose takeaway cannot be said in one line is split or
  dropped. Two slides with one purpose are merged, or one is dropped.
- **Titles are plain, direct, exact and technical.** Name what the slide shows ("Attention
  pattern of head 3.2"), never a catchy phrase ("Who talks to whom").
- **Minimal text, nothing invented.** No captions, sub-labels, role text, UI hints, "?",
  "provisional", claims or status markers the author did not give; no recoloured semantics;
  no sizes the storyboard did not ask for. Ask; lean towards more relevant questions.
- **No internal shorthand, on screen or to the author.** No ids from the working files
  (finding numbers such as `F012`, file or slide ids such as `12-03`, stage codes such as `S2`),
  no terms coined while building ("slot", "band", "pull"), no bare symbols. Write for someone
  who is not in the details: the same rule holds for questions, notes and reports to the author.
  Name a slide by its title, never by its file id.
- One idea per slide; parallel structure.
- Internal padding on every component; if content is tight, shrink the font, never clip.

### 3.2 Reveals and animation
- **Reveal granularity.** A process gets one step per stage, in placement/flow order: never
  all at once, and never padding steps. Not every word gets a step.
- **A method slide animates the mechanism on one example, never the outcome metric.** Show
  what the method does to the computation (one input, one component scaled, the value that
  changes as a result); the metric it moves belongs on a results slide. Never bullets for a
  method. A method's visual metaphor (a cut mark, a source colour and a target colour) is the
  same on every slide that uses the method (one visual language, below; `anim.transfer`, §8).
- **Long formulas are built term by term.** One reveal step per term or factor, each with its
  meaning in words beside it (a muted key line, §3.3); the full formula stands only at the end.
  Example: `s = (a − b) / n` reveals `a − b` ("gap between the two runs"), then `/ n` ("per
  question"), then `s`.
- **Highlight exactly the referent.** A ring, colour or spotlight lands on what the sentence
  names and nothing else: no extra circled marks, no decoy cells, no neighbour lit for balance.
- **Spotlights on results, in the order of the argument.** A results figure is read through
  spotlights, one claim per step, in the order the speaker makes them. One spotlight at a time;
  each covers the whole referent (§5).
- **Example prompts show their context.** An example input sits in a `.pbox` with a header
  naming it ("Input", "Prompt"), shows enough of the surrounding text to be real, and
  highlights the key sentence. A with/without pair flips in place (`.swap` + `data-hide-at`,
  §2.10), so the audience sees only what changes.

### 3.3 Symbols, numbers and legends
- **Symbol key on the slide.** Every symbol is glossed on the slide that uses it, in the step
  it first appears, as a muted key line of at least 16px. Never rely on an earlier notation
  slide. At most 4 key lines per slide; more means the slide carries too many symbols. Every
  on-screen token with a special role is explained the same way (e.g. tokens after `Answer:`
  keyed as "generated by the model").
- **Every connector means something.** Every arrow, dashed line and legend entry is explained
  on screen. Prefer a label on the drawing to a legend.
- **Plain legends.** A legend entry reads "red dot: claim", nothing more: no arrows, ratios or
  formulas in a legend. Better still, label the marks on the drawing.
- **Every number has a definition.** A metric on screen shows what it measures (a formula or a
  comparison), never a bare "restored 0.50".
- **Numbers sit on the drawing.** Values go on the bars, beside the arrows and at the line
  points they describe, not in a separate table. One format per quantity across the deck:
  `0.88` everywhere, never `0.88` on one slide and `88%` on another.
- **The header names the metric and the data.** A plot or table header says what is measured
  and on what: "Accuracy · synthetic QA set, n = 400".
- **Every count names its pool.** "12 of 90 questions", never a bare "12".
- **No plot too small to read.** A plot's tick labels and value labels are at least 12 canvas px
  and its marks are distinguishable in the PNG; if not, enlarge the plot or split the slide.
  Text that is small on purpose (a dense table shown as texture) carries
  `data-small-ok="reason"` (§6.1).

### 3.4 Sources and faithfulness
- **One visual language.** Reuse the deck's components (readouts, forward-pass drawing, block
  illustration, recurring animations) through a shared generator module (§8) rather than
  redrawing them per slide. Colours: the colour rule in §2.2.
- **Faithful notation and maths.** Notation follows the source. Formulas are checked against
  the paper. Index, shape and matrix conventions hold across the deck (`ml-visuals.md`).
- **Real, sourced data; illustrative values declared.** Every value is real and sourced, or
  illustrative. Illustrative values:
  - are used only after the author agrees, and follow the trend of the real data: an
    illustrative value never contradicts the deck's real data;
  - are declared in the speaker notes and in SPEC.md, value by value;
  - carry the on-slide tag `<span class="illus">illustrative</span>` (§2.10), always in the
    markup. If the author switched the tags off for the whole deck, PRD.md records the waiver
    (who, when) and the stitch adds `--body-class no-illus`, which only hides them, so switching
    back is one flag. The verifier checks that the tag is in the source always, and that it is
    visible only without a waiver.
- **Results figures.** Copy the project's figures exactly (axes, units, resolution); embed
  paper figures as images, never redrawn. Every plot names its dataset and n; every panel has a
  y-axis.
- **Small conventions.** The running example is named on screen, never by a nickname;
  citations go in the notes, with at most an origin tag on the slide.

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
| `data-caption-lane` | `top` \| `bottom` \| `below-title`: fixed band (rule 11); overrides `data-caption-pos` | beside the ring |
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
   logo band, leader to the ring's bottom edge. `below-title`: its top 12 px under the slide
   title's text box, leader to the ring; without a title it falls back to the `top` band. Use a
   lane when `data-caption-pos` would put the caption on the subtitle or other text, and
   `below-title` when a `top` caption would cover a tall or two-line title, or when the caption
   should read as the title's subtitle.
12. **Cover the whole referent.** When the thing named appears in several places, light every
   place, each in its own step or together in one bucket: a table row, the heatmap cell it
   refers to and that cell's axis labels. Show the value inside the lit region. Several markers
   in one bucket share one veil (rule 4). Example: the claim "unit 7 in block 3 matters most"
   lights the table row "block 3 · unit 7", then the heatmap cell (3, 7) with `0.62` in it and
   the axis labels "3" and "7".

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
  text ≥ 16px; intended small text carries `data-small-ok="reason"` and its reason in
  `check.small_ok` holds up;
- spotlight steps: `spot` lists the right target, the PNG shows the dim + ring on that region,
  and the next shot clears it; check one `--then left` back-step restores it (§5);
- every formula is visibly rendered (a blank area passes `--check`, so look);
- `real_errors` empty. Failed web-font requests offline are filtered out; fallback fonts in
  screenshots are acceptable;
- no `failed_assets` key: a local font, image or stylesheet that failed to load (e.g. fonts
  missing in a scratch copy) prints `WARNING: N asset(s) failed to load` and makes the PNGs
  wrong, though the exit code is unchanged;
- an autoplay or looping slide: the `--frames` shots cover one full loop and each is right;
- the motion budget holds (below).

Then `--size 1024x768`: the same picture, letterboxed. Drill-down: add
`--click '[data-goto=ID]'` and `--click '#back'` and read those PNGs.

**Motion budget.** Every animated step has a length the storyboard states (e.g. "the value
flies to B in about 2 s"). The generator asserts it (for `anim.transfer`, `t_end`, §8), and
`--wait` covers the longest step plus the kit's 0.5 s fade: a 2.8 s step needs `--wait 3400`
or more. When the author asks for slower or faster motion, change `--anim-speed` (§2.10) and
re-check the budget. `--anim-speed` affects only durations written as
`calc(Ts / var(--anim-speed))`; for `anim.transfer`, change its `speed=` argument and
regenerate (§8.1).

### 6.1 shot.py options
- `--all` advances until the last step of the last slide, so no count is guessed; it stops
  early if an advance changes nothing, and combines with `--start K` (K → end). A positional
  count given with it is ignored.
- **Where to start.** `--start K` jumps to the K-th `<section class="slide">` in document order
  (1-based; the kit's `go(K-1)`). It counts every slide in the file; it equals the on-screen
  number unless a backup (`data-offpath`) slide comes earlier. `slide:K` in `--then` counts the
  same way. Prefer `--start-id ID` (the slide with
  `data-id="ID"`) or `--start-title T` (exact, unique `data-title`); both together must name the
  same slide, neither combines with `--start`, and a name that matches nothing exits 1 with
  `"error"` in the JSON.
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
  transitions take 0.5 s; at the old 550 ms, screenshots caught mid-fade frames. On slides with
  their own animations, `--wait` ≥ the longest step + 600 ms (motion budget, §6), and at least
  1700.
- Actions after the advances (`--click`, `--then`) run in the given order: `right`, `left`,
  `right*K`, `left*K`, `click:SEL`, `key:KEY`, `slide:K`. Quote `right*K` in zsh. Rapid
  `right*K` presses can catch a staggered animation mid-way; use single steps when judging an
  animated step.
- `--step-timeout S` (default 30) ends a run whose slide script loops with `hang`/`stuck_at`.
  Launching Chromium has its own limit of at least 60 s, so a slow launch on a busy machine is
  not reported as a hang at `load`.
- `--load-timeout S` limits the page load itself (default: the larger of 30 and
  `--step-timeout`). The load waits for the DOM, then for fonts and pending images, all within
  this limit. A big deck on a loaded machine can need more than 30 s: use
  `--load-timeout 120` and keep the step timeout short for hang detection. A load past the
  limit ends like a hang: `"stuck_at": "load"`, `"load_timeout_s": S`, exit 1.
- `--frames T1,T2,…` takes extra shots of the entry state at T ms after slide entry (the load,
  or the `--start` jump), before the entry shot, for autoplay and looping slides:
  `shot.py DECK P 0 --start-id outro --frames 0,800,2000` (0 advances). Saved as `PREFIX_00_tNNNNN.png`;
  listed in `shots` with `"action": "frame"`, `"t_ms"` (asked) and `"t_actual_ms"` (measured,
  ≥ `t_ms`). A bad value exits with a JSON error before any browser starts. The entry shot alone
  shows only one moment of a loop.
- `--click SEL` on an element with no box (an empty SVG `<g data-goto>`), or whose centre
  would land on its own ancestor (an SVG `<g>` whose shapes have `fill:none`), dispatches the
  click in JS instead; the shot carries `"click": "js-dispatch (…)"` and stderr a NOTE. An
  element covered by an unrelated one still gets a normal click, so a real blocking bug shows.
- `data-small-ok="reason"` on an element or an ancestor exempts its text from the small-text
  warning; it is listed in the shot's `"small_ok"` and once per item in `check.small_ok`.
- **Parallel runs (slot lock).** At most `SLIDES_SHOT_SLOTS` runs (default 2; 0 = no limit)
  drive Chromium at once on the machine; parallel Chromium runs crash a small VM. A run waits
  for a free slot (`shot.py: waiting for a Chromium slot …` once on stderr; `"slot_wait_s"` in
  the JSON when it waited ≥ 0.5 s) and holds it for the whole run, all `--check-size` passes
  included. The slots are `flock`ed files in `SLIDES_SHOT_LOCK_DIR` (default
  `/tmp/slides-shot-slots`, shared by every session and user on the machine); if the folder
  cannot be used, `shot.py` warns and runs without a limit, and on Windows there is no limit.
  No manual `flock` wrapper is needed; on a bigger machine raise it, e.g. `SLIDES_SHOT_SLOTS=4`.

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

## 7. Assembling a deck; orchestrating a talk

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
| `--check-assets` | warns on every relative URL in the merged deck (same attributes and `url()`, after the `--asset-base` rewrite; not in scripts or comments) whose file does not exist relative to OUT's folder; JSON `"assets": {"relative": N, "missing": [...]}`. Absolute paths, any scheme (`https:`, `data:`), `#anchors` and templates are skipped. Before publishing (§10) |

**Refused calls** exit 2 and write nothing. Without `-o`, a call whose OUT is an existing slide
fragment is refused (`assemble.py a_fragment.html b_fragment.html` used to overwrite `b`). When a
call is refused and its output path holds an earlier assembled deck (it has the kit's
`SLIDES:START` marker), that deck is renamed `OUT.stale` (`"stale_moved_to"` in the error JSON),
so nothing downstream mistakes it for a fresh stitch; one `mv` restores it. Files without the
marker are never moved.

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
  other than `none` (or `none` with a caption), `data-caption-lane` other than `top`, `bottom`
  or `below-title`.
- **Size**: a fragment over 500 KB, or with more than 2,000 `<rect>` (comments and scripts not
  counted). Fix as in §10, size budget.
- Backup slides (`data-offpath`) are left out of the section-contiguity lint only; every other
  lint includes them.
- The markup lints (duplicate ids, dangling `data-goto`, spotlight markers, `data-title`,
  `data-section`, the slide count) skip `<script>` bodies, so JS text such as a
  `'<section class="slide">'` template is not read as markup. The viewport-unit lint still reads
  scripts (`style.width = '50vw'` does use one).

### 7.3 Orchestrating a talk; several sessions on one deck
The **orchestrator** is the session that talks to the author: the main agent, or one deck
orchestrator when several top-level sessions share a talk.

**Roles**
- The orchestrator takes the author's notes, plans, routes and publishes. It delegates
  execution (planning a batch, building, verifying) to agents or other sessions, so it stays free
  for the next notes.
- One owner session per section, recorded in SPEC.md. Only the orchestrator edits `ORDER.txt`,
  `00-master` and the stitch, allocates shared ids (question or finding numbers), and publishes.
- Other sessions send cross-section edits to the owner as proposals, never edit them directly.
- Each PRD.md entry records the session that took it down.
- Before taking over a slide, ask its owner session what is in flight; before an author's new
  notes reach a slide another builder holds, route them to that builder, not around it.
- The orchestrator may take over a stalled session (usage limit, crash, no answer). A session
  that stopped mid-task can leave the generator edited but the fragment not regenerated: run
  each generator into scratch and `cmp` with `fragments/` to see exactly what landed, then brief
  a new builder with that state.
- Before each round with the author, the orchestrator collects the open questions from every
  session into TBD.md and asks them in one batch, in plain words (§3.1, no internal shorthand).
- A builder's "Wording I chose (author to confirm)" list is relayed to the author: on-screen
  wording is never a builder's decision. The list covers only wording that adapts a sourced
  item (a unit or axis label copied from the cited source, a given label shortened to fit, case
  or punctuation). A label, caption or number with no source in the storyboard, PRD.md or the
  cited source is a STOP, never a listed choice.

**Intake ledger.** Every author note gets one row in TBD.md when it arrives, so "where did my
note go?" has an answer:

| Note (short, verbatim) | Slide title (number as cited) | Mode | Owner | Status | Published version |
|---|---|---|---|---|---|
| "put the value next to the arrow" | *Effect on the output* (cited as 14) | execute | session B | verified | v12 |
| "maybe merge these two?" | *Setup* / *Data* (cited as 3, 4) | plan-only | orchestrator | planned | — |

- **Mode**: each note is plan-only (storyboard into SPEC.md, build nothing) or execute (plan
  and build). A note that does not say is asked about.
- **Slide numbers → titles at intake.** Resolve every slide number the author cites to the
  slide's title at once, against the deck the author was looking at, and record both: numbers
  move as soon as a slide is added.
- **Route** the row to the slide's owner; a question about the research rather than the deck
  goes to TBD.md (or the research owner) and is answered in plain words, not built.
- **Status**: received → planned → building → built → verified → published.
- **Removed notes go to TBD.** Text the author removes from a slide or its notes moves to TBD.md
  with the slide title and date, never deleted, so it can come back.

**One version label.** Use the published version (the host's version number, or the publish
date and time) in the ledger, in reports and in every message to the author. No private build
counters next to it.

**Stitch lock.** One stitch at a time: two sessions writing one deck file interleave. Wrap the
stitch in a lock on the talk folder, e.g. on Linux
`flock <talk>/.stitch.lock python3 <skill>/scripts/assemble.py -o talk.html …` (elsewhere a lock
directory made with `mkdir`, removed after). Builders and verifiers check a **fresh assembly**
(`assemble.py` of the current `00-master` + the fragments under test into scratch), never the
last stitched deck: it predates every edit since the stitch, so it shows stale styles and passes
or fails the wrong thing. After each merge, re-stitch and re-verify.

**Incremental check.** After a change, check the changed slides and their seams (the slide
before and after each, where a transition or a zoom pair can break) rather than the whole deck:
`shot.py talk.html shots/inc N --start-title "<title of the slide before>" --check` (or
`--start-id ID` when that slide has a `data-id`), with N the steps of the three slides plus 2.
N goes straight after PREFIX. The full `--all --check` runs before every publish unless a deadline freeze is
declared.

**Deadline freeze.** When time is short (the talk is today, a usage limit is near), the
orchestrator declares a freeze, recorded in SPEC.md: no new content; only blocker fixes; each fix gets the
incremental check. If the full check cannot run before publishing, tell the author which slides
were checked and which were not; never publish unchecked silently.

**Option decks.** For a creative choice the author cannot judge from a description (an
animation style, a closing slide), build 2–3 options as separate slides (backup slides, §2.10,
or a small option deck) and let the author pick after seeing them. Archive the others.

**Republishing a live link.** Viewers of a shared link see every republish at once. While a
link is shared (a talk in progress, a link sent round), ask the author before republishing.

**Git in a shared working tree.** Commit only your own paths (`git commit --only -- <paths>`),
never `git add -A`; other sessions' staged files stay out. Before any push, check
`git log origin/main..HEAD`: a push carries every local commit, including other sessions', so
each one needs its author's approval.

## 8. Generated fragments

A slide whose markup is computed (a grid, a matrix, a readout from data) is generated, and the
generator is the source; the fragment is output.
- The generator lives in the talk's `build/NN/` (e.g. `build/NN/gen.py`), never in a scratch
  folder, and writes the installed fragment. Edit the generator, never the fragment.
- **Every generator folder has a `README.md`**, `build/_shared/` included: what it generates,
  the command, its inputs and its **rebuild dependencies** (data files, shared modules), so a
  change to a shared module rebuilds every fragment that imports it. A generator without one is
  a finding.
- Every value on screen is read from its data source and **asserted** against it in the
  generator, not typed in.
- **Byte-identical rebuild check** before any edit: run the generator to a scratch path and
  `cmp` it with the installed fragment. A difference means someone edited the fragment by
  hand: stop and report rather than overwrite it.
- Parallel builders on one section share `build/NN/common.py` (colours, sizes, drawing
  helpers). Deck-wide components (readouts, forward-pass drawing, a recurring animation) live in
  **`build/_shared/`**, owned by the orchestrator, and every generator imports them from there
  (§3.4, one visual language). Builders propose changes to `_shared/`; they do not edit it.
- **A copied module carries its origin.** When a generator must hold its own copy of a shared
  file (it runs elsewhere, or under `python3 -I`), the copy starts with a header naming the
  source path and the source's SHA-256 (`# copied from build/_shared/draw.py sha256=…`), and a
  test recomputes the hash of the source and fails when they differ. Three silent copies of one
  module drift apart; a hashed copy fails loudly.
- **Changing a shared module** (one slide needs a new layout): add the new behaviour behind an
  opt-in argument whose default is the old behaviour (e.g. `dot_layout='stack'|'rowcol'`), pass
  it only from the slide that needs it, then regenerate **every** user into scratch and `cmp` each
  with its installed fragment; all must be byte-identical before handing over. Some generators
  import siblings and fail under `python3 -I`; run those from their own folder.

### 8.1 `scripts/anim.py`: animation and label helpers
A stdlib-only module of SVG and CSS helpers for generators; it returns strings and never
touches files. Import it by path: `sys.path.insert(0, '<skill>/scripts'); import anim`.
`python3 anim.py` runs its docstring examples (CI does).

- **`anim.transfer(src, dst, payload_svg, t0=0.0, dur=2.8, cut=True, recolour=None, uid='xfer',
  scope='', trigger='.step.shown', c1=None, c2=None, bend=0.35, ring=14, land_ring=None,
  recolour_target=None, speed=1.0, path_colour='#9aa3b2', mark_colour='var(--ink, #1a1a1a)')`** animates any value moving from point A to
  point B: with `cut=True`, a ring at A, two scissor snips and a dashed cut line (`t_cut`); at
  `t_fly` the curve and arrow appear and the payload flies (a cubic Bézier arc, `bend` × the
  distance); at `t_land` a flash, and with `recolour` a ring and dot in that colour stay at B
  (`recolour_target=SEL` also refills an element). It returns
  `Transfer(svg, css, t_cut, t_fly, t_land, t_end, points)`.
  - `t0` delays the first beat (s after the trigger); `path_colour` colours the curve and arrow
    head, `mark_colour` the ring, scissors and cut line.
  - `trigger` is the state that starts it: `.step.shown` (put `svg` inside a
    `<g class="step">`), or `.slide.playing` for an autoplay slide
    (`<section class="slide demo" data-autoplay>`, §2.10). A trigger that starts with `.slide`
    is joined to the scope on the slide itself (`.demo.slide.playing .UID-fly`); any other
    trigger is a descendant of the scope (`.demo .step.shown .UID-fly`), so `.playing` on a
    `data-autoplay` wrapper `<g>` works too.
  - `uid` prefixes every class and `@keyframes`; `scope` (the slide class) prefixes every rule.
  - `speed` > 1 plays faster, < 1 slower; every returned time is divided by it. The durations are baked
    into the CSS, so `--anim-speed` does not reach them: to change the pace, change `speed=`
    and regenerate.
  - Screenshot no earlier than `t_end` plus the kit fade (motion budget, §6).
- **`anim.label_clear(labels, obstacles, min_px, between_labels=True)`** asserts that value
  labels keep `min_px` from every mark: obstacles are boxes, points or polylines (e.g.
  `transfer(...).points`), measured exactly per segment. It raises `anim.ClearanceError` (an
  `AssertionError`) listing every pair below `min_px`, and returns the smallest gap. Call it in
  the generator next to the value asserts.
- Helpers: `anim.text_box(x, y, text, size=15)` (a generous box for an SVG `<text>`),
  `anim.bezier_points(...)`, `anim.fmt(v)` (1 decimal, no trailing zeros).

```python
tr = anim.transfer((100, 200), (500, 200), '<rect x="-30" y="-8" width="60" height="16"/>',
                   t0=0.5, recolour='#7b4fd0', uid='mv1', scope='.demo')
svg, css = '<g class="step">' + tr.svg + '</g>', tr.css     # t_end = 4.34 s
anim.label_clear([anim.text_box(300, 120, '0.62', size=14)], [tr.points], 6)
```

## 9. Patterns

### 9.1 Camera / zoom continuity
A zoom from slide A into a region of A on slide B reads as one camera move only if B starts
exactly where A ended:
- B's entry state redraws **A's final frame exactly**: same elements, positions, sizes and
  colours, the slide title included (a different title on B shows as a visible cut); generate
  both from the same code. The zoom is B's first step, a transform on one wrapper. Trigger it
  with an empty step marker, `<i class="step" data-step="zoom"></i>`, and
  `.<clsB>:has(.step[data-step="zoom"].shown) .<wrapper>{transform:…}`.
- Avoid the **fade-from-white dip**: slides cross-fade over 0.5 s on a white stage, so two
  identical frames still flash pale mid-transition. Turn the slide transition off on both
  slides of the pair (`.slide.<clsA>,.slide.<clsB>{transition:none}`): the change is then a
  cut between identical frames, which is invisible, in both directions. Check with `shot.py`
  across the cut, forwards and back.
- Going back, the kit's replay guard (§2.10) shows A at its end state at once, so `←` from B
  lands on A's final frame without replaying the zoom.

Check (tested: `tests/test_kit_v12.py`, `test_zoom_pair_seam`):
`shot.py deck.html shots/zoom N --start-id <A> --check --then left`, with N = A's steps + 1, so
the run ends on B's entry and then steps back. A's last PNG, B's entry PNG and the back-step PNG
must be identical (`cmp`, or a pixel diff), with no pale frame.

### 9.2 Lift text, keep geometry (embedded page SVGs)
An SVG taken from a paper page or another tool carries its own fonts, sizes and often text as
outlines. Keep its geometry (paths, boxes, arrows) as it is; lift the text out: delete its
`<text>` (or glyph paths), and re-set each label as kit text (SVG `<text>` in the deck's
fonts, at a legible size, `.halo` where it sits on the drawing) at the same coordinates in the
SVG's `viewBox`. Scope or strip the SVG's `<style>`: an unscoped `.chip{}` or `.card{}` in it
restyles every slide (§7.2).

### 9.3 Fold / shrink morph (the inverse of a zoom)
A whole drawing on slide A shrinks into a small component that slide B keeps in a corner (a
full model folds into a mini model, which B then uses as one box). It is the zoom pair run
backwards:
1. One generator draws the drawing once at full size, as a function with a scale and an
   origin (e.g. `mini(x, y, s)`); A and B both call it, so the mini copy is the same drawing.
2. A's last step is the fold: one wrapper `<g>` (or `<div>`) gets
   `transform: translate(x, y) scale(s)` with a CSS transition, from the identity to B's corner
   position. Trigger it with an empty step marker, `<i class="step" data-step="fold"></i>`, and
   `.<clsA>:has(.step[data-step="fold"].shown) .<wrapper>{transform:…}`. Fade out, in the same
   step, everything on A that B does not keep (`data-hide-at="<that step's key>"`, §2.10).
3. B's entry state draws exactly A's final frame: the mini copy at `(x, y, s)` and nothing else
   new. B's own content then arrives on its steps.
4. No slide transition across the cut: `.slide.<clsA>,.slide.<clsB>{transition:none}` (§9.1).
5. Motion budget (§6): the fold step's transition length is set in the generator and `--wait`
   covers it.

Check as in §9.1 (tested: `tests/test_kit_v12.py`, `test_fold_morph_seam`): A's last PNG equals B's entry PNG; `←` from B shows A folded (replay guard),
and one more `←` unfolds it. Example: a five-block pipeline on A folds into an 80 × 45 px
"pipeline" box in B's top-left corner, from which B's arrows start.

## 10. Publish (P6)

Before a deck leaves the machine (a hosted page, an e-mail, a shared drive):
1. **Self-contained**: stitch with `--check-assets`. `"assets": {"relative": 0}` means no
   relative URL is left; otherwise copy the assets next to the published file or inline them
   as data URIs, and `"missing"` must be `[]` in any case. No local path remains
   (`/home/`, `/Users/`, `file:`). Web fonts load from Google, so bundle them when the room is
   offline (row 31).
2. **Size budget**: the deck is within the host's limit, and no fragment draws the size lints
   (§7.2: over 500 KB, or over 2,000 `<rect>`). A large SVG is usually one dense heatmap or grid:
   - put attributes shared by many elements on a parent `<g>` or a CSS class, not on every
     `<rect>` (`stroke`, `stroke-width`, `shape-rendering`);
   - round coordinates and sizes to 1 decimal (`anim.fmt`, §8.1);
   - above about 500 cells, draw the grid as an image (a PNG data URI) or a `<canvas>`, and keep
     only the labels, highlighted cells and spotlight targets as SVG.
   Measure before cutting (`wc -c` per fragment).
3. **No U+FFFD**: `grep -c $'\xef\xbf\xbd' deck.html` prints 0 (`assemble.py` warns per
   fragment); a host may refuse a page that contains it.
4. **Personal-data and logo scan**: names, e-mail addresses, local paths (`/home/`,
   `/Users/`), unpublished numbers, and the speaker notes, which ship inside the HTML; logos
   only where their use is allowed.
5. **Title**: `--title` set to the talk's title, never the kit's "Slide Kit".
6. **Complete**: the final stitch runs without `--allow-missing`, so `"skipped"` is empty and
   no skipped-fragment warning is printed.
7. Re-run `shot.py --all --check` on the final file and read the PNGs (under a deadline freeze,
   §7.3, say which slides only had the incremental check).
8. **Verifier**: flow and compliance (every PRD.md input, quoted verbatim, mapped to slide and
   step) have run on this version; without both the verdict is "not ready".
9. **Live link**: if an earlier version's link is shared, ask the author before republishing
   (§7.3).

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
| 49 | Mid-fade screenshots | Default `--wait` 1200 ms; on animated slides ≥ the longest step + 600 ms, at least 1700 |
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
| 60 | Backup slides appended at the end with a hand-written off-path list and patched `advance`/`back`; numbers and bar re-implemented in the master | `data-offpath` on the slide; the kit skips it in the walk, numbers, bar, dots and map (§2.10) |
| 61 | A backup slide exited to the next slide in DOM order, not to the hub that opened it | → past the end / ← before the start returns via the history, else to the first linking hub |
| 62 | Stepping back replayed every build of the slide (bars regrew, arrows redrew) | Replay guard in `go()`: arriving backwards finishes finite animations; infinite ones keep running |
| 63 | A per-fragment `*-instant` class to stop replays | Drop it; the kit guard covers CSS animations and transitions |
| 64 | A looping entry animation started on load or never restarted | `data-autoplay` + animate under `.playing`; speed through `calc(Ts / var(--anim-speed))` |
| 65 | A toggle's state survived leaving the slide (an overlay still on when coming back) | `data-toggle="cls"`; the kit resets it on leave and on every step change |
| 66 | A toggle click also advanced the slide; space re-triggered a focused toggle | `data-toggle` controls never advance; space and arrows always navigate |
| 67 | `:has(.step[data-step="k"].shown)` CSS to hide an element at a later step | `data-hide-at="k"`; to replace A by B, pair it with `data-step="k"` inside `.swap` |
| 68 | An overview with one tile per slide in a long deck; a topic list kept by title in the master | `data-topic` on topic starts + `--body-class ov-topics` |
| 69 | Prompt and example panels styled differently on every slide | `.pbox` (+ `.pbox-h`, `--accent`) |
| 70 | A spotlight caption covered the slide title | `data-caption-lane="below-title"` (or `top` / `bottom`) (§5) |
| 71 | A runtime script text-matched "illustrative" to hide tags; screenshots and the source disagreed | `class="illus"` on the tag; `--body-class no-illus` hides them; values declared in notes + SPEC (§3.4) |
| 72 | A big deck on a loaded VM timed out at page load (30 s), again and again | `--load-timeout`, default max(30, `--step-timeout`); a load timeout ends as a hang with `stuck_at: "load"` (§6.1) |
| 73 | Parallel `shot.py` runs crashed Chromium | Machine-wide slot lock, `SLIDES_SHOT_SLOTS` (default 2) |
| 74 | Autoplay or looping slides could not be captured (one entry shot only) | `--frames t1,t2,…`, each frame with `t_ms` and `t_actual_ms` |
| 75 | `--click` timed out on an SVG `<g data-goto>` | JS dispatch when the element has no box or a point click lands on its ancestor; noted in the shot and on stderr |
| 76 | Fonts missing in a scratch copy went unnoticed (fallback fonts in the PNGs) | `failed_assets` + a stderr WARNING |
| 77 | The small-text warning fired on every run for intended small text | `data-small-ok="reason"`, listed in `small_ok` |
| 78 | The dangling-`data-goto` lint matched `<script>` text | Markup lints skip script bodies (comment-aware) (§7.2) |
| 79 | Several fragments without `-o` left the stale deck in place; two fragments without `-o` overwrote the second | Refused (exit 2, nothing written); a fragment as OUT is refused; an earlier deck at OUT is renamed `OUT.stale` (§7.1) |
| 80 | A deck of several MB, most of it one heatmap of thousands of `<rect>` with inline attributes | Warnings over 500 KB per fragment and over 2,000 `<rect>`; size budget (§10) |
| 81 | Backup slides placed last gave a false "section not contiguous" | The contiguity lint skips `data-offpath` slides |
| 82 | Relative `assets/` fonts and logos missing after publishing | `--check-assets` (§7.1, §10) |
| 83 | `--start K` was read as the on-screen number; it differs once a backup slide comes earlier | `--start-id` / `--start-title` (§6.1) |
| 84 | Internal ids (finding numbers, file ids, stage codes) or coined terms on screen and in messages to the author | No internal shorthand (§3.1); the verifier greps for ids |
| 85 | One quantity as `0.88` on one slide and `88%` on another; values in a side table | Numbers on the drawing, one format per quantity (§3.3) |
| 86 | A method slide animated the outcome metric instead of the mechanism | Animate the mechanism on one example (§3.2) |
| 87 | Extra marks circled beside the referent; a spotlight on the table row only | Highlight exactly the referent, all of it (§3.2, §5 rule 12) |
| 88 | On-screen wording chosen by a builder reached the deck unconfirmed | "Wording I chose (author to confirm)" in the builder's report, relayed by the orchestrator (§7.3) |
| 89 | Author notes lost, sent to the wrong session, or cited by a stale slide number | Intake ledger in TBD.md; slide numbers resolved to titles at intake (§7.3) |
| 90 | Two sessions wrote the stitched deck at once; version labels diverged from the published ones | Stitch lock; one version label, the published one (§7.3) |
| 91 | A "ready" verdict without flow or compliance; text beyond the author's words shipped | Flow and compliance mandatory before any publish (§10) |

## 12. Migrating a deck started before 1.1 or 1.2

A deck whose stitch script or master implements by hand what the kit and scripts now do keeps
working unchanged: a master's wrappers reassign `advance` / `back` and rebuild the map after the
kit, and its replay guard and the kit's are idempotent. Move to the built-in features one at a
time, with a full `shot.py --all --check` after each change.

**From before 1.1**
1. **Stitch script.** Replace a shell `stitch.sh` (a `sed` on "Slide Kit", a loop that skips
   missing fragments, a hand-kept order) by one `assemble.py -o … --master … --order ORDER.txt
   --title "…"` call (§7.1); `--allow-missing` only mid-build.
2. **Numbers and progress bar in the master.** Delete the master's numbering script and its own
   bar, turn on `--body-class "slide-numbers progress"` (§2.7), and move the number's position
   into `--num-right` / `--num-bottom`.

**From 1.1 to 1.2**
3. **Backups.** Add `data-offpath` to each slide in the master's off-path list, then delete the
   list, the `advance`/`back` wrapper and any CSS that hides the kit's `#prog` / `#dots`.
   Backups may now sit next to their hub in the order file (§2.10).
4. **Replay guard.** Delete the master's `getAnimations().finish()` observer and the fragments'
   `*-instant` classes.
5. **Autoplay.** Replace "start on `.active`" CSS or entry scripts with `data-autoplay` +
   `.playing`; express durations with `var(--anim-speed)`.
6. **Toggles.** Replace click handlers that set a class on the slide (and `data-noadvance`) with
   `data-toggle="cls"`; delete any `kit:step` listener that only cleared that class.
7. **Hide later.** Replace `:has(.step[data-step="k"].shown) .x{opacity:0}` rules with
   `data-hide-at="k"` on `.x`.
8. **Topics.** Put `data-topic="…"` on each slide whose title is in the master's topic list,
   add `ov-topics` to `--body-class`, and delete the rebuild script and its overview CSS.
9. **Prompt box.** Delete the master's `.pbox` rules; map its edge modifiers to `--accent`
   (e.g. `.pbox.alt{--accent:var(--sa)}` in the master).
10. **Illustrative.** Put `class="illus"` on each tag, delete any text-matching script, and add
    `no-illus` to `--body-class` if the author switched the tags off (recorded in PRD.md).
11. **Copied modules.** Move modules copied between generators into `build/_shared/`, or give
    each copy a hash header and a test (§8).
