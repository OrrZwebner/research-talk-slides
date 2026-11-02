---
name: research-talk-slides
description: >-
  Builds research-talk slides as interactive HTML on a fixed kit: a 1280×720 canvas that
  scales identically to any screen, a white master with a top-left title and corner
  logo slots, presenter step-reveal (one build per click), drill-down from an overview component
  to its detail slide and back, backup slides, stable SVG arrows for pipeline schemes, speaker
  notes and a section map. Each slide is a small fragment spliced into the kit; every reveal
  step is screenshotted and checked before delivery. Enforces talk rules: minimal text, no
  invented labels, real data or declared illustrative values, paper figures embedded rather
  than redrawn. Use for "conference talk / seminar / lab meeting / thesis defense slides in
  HTML", "research talk", "slide for my paper", "pipeline diagram slide with arrows",
  "step-by-step reveal", "drill-down slide", "overview slide that opens detail slides", "add a
  slide to my talk deck", "fix the arrows on my slide". For a .pptx file use a pptx skill
  instead.
license: MIT
compatibility: >-
  Python 3.8+. Screenshot verification needs Playwright with Chromium
  (pip install playwright && python -m playwright install chromium). The decks are plain HTML
  and open in any modern browser.
metadata:
  version: "1.2.0"
---

# Research-talk slides

Build talk slides as small HTML **fragments** on the bundled kit, assemble them into a
standalone deck, and verify every reveal step by screenshot before handing anything over.
The kit already holds the canvas, master, reveal engine, drill-down and chrome: build against
it, never re-style a slide from scratch.

`<skill>` below is this skill's folder (as a plugin:
`${CLAUDE_PLUGIN_ROOT}/skills/research-talk-slides`). Scripts print JSON on stdout.

## Pick the mode

| Mode | When | Output |
|---|---|---|
| Single slide (P1) | one title + content | `<name>_fragment.html`, `<name>.html`, one PNG per reveal step |
| Pipeline scheme (P3) | boxes joined by arrows, revealed stage by stage | as P1 |
| Figure slide (P4) | one paper figure plus a reading panel | as P1 |
| Drill-down section (P2) | an overview whose components each open a detail slide | ONE fragment with overview + all detail sections → one deck file |
| Backup / interactive (P1–P2) | detail only on a click; animation on entry; toggle; hide at a later step | as P1; attributes in BUILD_GUIDE §2.10 |
| Deck stitch (P5) | several finished fragments in talk order | one deck file + a full-deck screenshot pass |
| Publish (P6) | a finished deck leaves the machine | the checked deck file |
| Partial input | topic only; labels, wording or data missing | a reveal storyboard + questions; build only confirmed content |
| Author notes | notes arriving in batches, marked plan-only or execute | an intake-ledger row each (BUILD_GUIDE §7.3) |

## Procedure — one slide (P1)

1. Get title and content from the author. Ask for every missing label, caption, wording and
   data source; lean towards more questions, not fewer. Never fill a gap yourself.
2. Draft a **reveal storyboard**: entry state + N steps in placement/flow order. Confirm label
   and text choices before authoring.
3. Author `<name>_fragment.html`: one `<section class="slide <slidecls>" data-section="N · Name"
   data-title="..">` with its own `<style>`/`<script>`. Scope every CSS rule under
   `.<slidecls>`; prefix ids and `@keyframes` with the slide class. Size in px or cqw/cqh only.
   A computed slide is generated: edit its generator in `build/NN/` (BUILD_GUIDE §8).
4. Assemble (with the talk's master, if it has one):
   `python3 <skill>/scripts/assemble.py <name>_fragment.html <name>.html --master <master> --title "<talk>"`
   Fix every item in `warnings`.
5. Screenshot every step and **read every PNG**:
   `timeout 600 python3 <skill>/scripts/shot.py <name>.html shots/<name> --all --check --json shots/<name>.json`
   Pass = the checklist in BUILD_GUIDE §6 (one bucket per advance, arrows still, safe area,
   box fit at 1906×1000, no small text, formulas rendered, no `failed_assets`, motion budget,
   `check.pass` true, exit code 0). Autoplay or loop: add `--frames 0,800,2000`.
6. Re-run with `--size 1024x768`: it must be the same picture, letterboxed.
7. Iterate until all pass. Report the storyboard, the labels used and their source, which
   values are real and which illustrative, the per-step verdict, and wording you adapted from a
   source (author to confirm; new unsourced wording is a question, rule 7). Brief, plain words.

## Procedure — drill-down section (P2)

1. Overview slide: `data-id="<hub>"`; each clickable component `data-goto="<detail-id>"`;
   each detail slide `data-id="<detail-id>"`. All in ONE fragment (navigation resolves only
   within one file); place detail sections right after the overview (numbered linearly).
   A detail outside the linear walk is a backup slide: `data-offpath` (BUILD_GUIDE §2.10).
2. Components show **name + icon only**; "click to open" goes in the speaker notes. The kit's
   `‹ back` (and Backspace) returns to the overview fully revealed.
3. Verify as P1, plus the click path, e.g.
   `shot.py deck.html shots/dd 0 --start-id <hub> --check --click '[data-goto=<detail-id>]' --then right --click '#back'`;
   no `js-dispatch` note may appear.

## Procedure — pipeline scheme with arrows (P3)

Copy `references/example_pipeline_arrows_fragment.html`. Boxes in a grid (rows of ≤ 3;
enlarge and add rows rather than shrink); one SVG overlay `viewBox="0 0 1280 720"` with one
filled-head `<marker>` in `#9aa3b2`; convert rects with `rectOf()`; compute arrows **once**
(double rAF + ~400 ms, then on resize/slide activation only); per-step arrow groups toggled by
**opacity only**; `.<slidecls> .step{transform:none}`. Within a row: right edge → left edge,
gap ≈ 10px. Between rows: **entry arrow only** (~34px) into the next row's first box. Labels
12px, static, ~10px above the arrow, clamped to x ∈ [70, 1210]. Details: BUILD_GUIDE §4. A value
moving from A to B: `scripts/anim.py` `transfer()` (BUILD_GUIDE §8.1).

## Procedure — figure slide (P4)

Embed the paper's figure image as-is (data URI or relative path); never redraw it. A
one-figure slide = figure + a side reading panel that step-reveals the marks to read. Results
plots copy the project's figures exactly and name dataset and n (BUILD_GUIDE §3). An SVG from a
page: lift the text, keep the geometry (BUILD_GUIDE §9.2).

## Procedure — deck stitch (P5)

Author and verify fragments independently (parallel subagents are fine; a drill-down section
is one unit). Then stitch in talk order and fix every warning:
`python3 <skill>/scripts/assemble.py -o talk.html --master fragments/00-master_fragment.html --order ORDER.txt
--allow-missing --title "<talk>" --body-class "slide-numbers progress"` (options and lints:
BUILD_GUIDE §7). `--allow-missing` is for mid-build stitches only. Run
`python3 <skill>/scripts/shot.py talk.html shots/deck --all --check` across the whole deck
(`--start-id ID` jumps to a slide); after a small change, BUILD_GUIDE §7.3 incremental check.

## Procedure — publish (P6)

Self-contained (`--check-assets`), size budget, no U+FFFD, a personal-data and logo scan (notes
ship inside the HTML), `--title`, a final stitch without `--allow-missing`, `shot.py --all
--check` (deadline freeze: BUILD_GUIDE §7.3), the verifier's flow and compliance; ask before
republishing a live shared link. Commands: BUILD_GUIDE §10.

## Orchestrating a whole talk (agents)

For more than a slide or two, the main agent orchestrates and the plugin's agents do the work
(plugin install only; otherwise run the same roles yourself, in order).
The talk record is **PRD.md** (the author's words, verbatim, never reworded), **SPEC.md**
(storyboards; superseded ones go to `SPEC-archive.md`) and **TBD.md** (open questions and the
intake ledger); a small talk may keep them in one PLAN file.
- `talk-planner`: dictated content → storyboards in SPEC.md + open questions (TBD.md); per
  note: plan-only or execute, slide numbers resolved to titles, an intake-ledger row.
- `talk-builder`: one confirmed storyboard per agent, several in parallel. **STOP means stop**.
  Wording adapted from a source goes under "Wording I chose (author to confirm)"; relay it.
- `talk-verifier`: mechanics, clarity, flow, facts; **compliance** maps every PRD.md input to
  slide · step · PNG. Flow and compliance are mandatory before a publish; fixes go to a builder.
- You delegate execution to stay free for new notes, may take over a stalled session, own
  ORDER, master, `build/_shared/`, the locked stitch and publishing, and use one version label
  (the published one). Freeze, option decks, removed notes: BUILD_GUIDE §7.3.
- Talk to the author in plain words: no internal ids or coined terms; slides by title.
- Reports over about 30 lines go to a file; agents return a summary plus its path.

## Non-negotiables

1. Build against `assets/kit.html`; never re-style a slide from scratch.
2. Master: white background, one large top-left title (Open Sans 48px), **no kicker**, two
   corner logo slots (BUILD_GUIDE §2.1); keep content above canvas y = 620.
3. Fixed 1280×720 canvas scaled by `transform`; px or cqw/cqh only (1cqw = 12.8px,
   1cqh = 7.2px), never vw/vh/dvh/svh.
4. Step reveal: non-`.step` shows on entry; one bucket per advance; group with
   `data-step="k"`. **Reveal order follows the DOM**, not the `data-step` number.
5. Arrows: one overlay, computed once, opacity-only reveal; details in P3 and BUILD_GUIDE §4.
6. Internal padding on every box; shrink the font before anything clips.
7. Minimal text: never invent labels, role text, UI hints, "?", status markers or sizes. Ask.
   Only wording adapted from a source (copied unit, shortened label) may be built and listed.
8. Real data; illustrative values agreed, declared in notes + SPEC, never contradicting real
   data, `.illus` on screen unless PRD records `no-illus`. Embed figures, don't redraw.
9. Verify: screenshot every step + one off-aspect size; read every PNG.

Content rules (detail and examples in BUILD_GUIDE §3):

10. Titles plain, direct, exact and technical; never catchy. Every slide states its purpose.
11. Picture over text: an explanatory sentence becomes a scheme, symbol or formula.
12. One reveal step per stage; a method shows its mechanism on one example, never the metric.
13. Every symbol is keyed on its slide, in the step it appears: a muted line ≥ 16px; ≤ 4 per slide.
14. Every arrow, dashed line and legend entry explained on screen; plain legends; readable plots.
15. Every number defined, on the drawing, one format per quantity; every count names its pool.
16. One visual language: reuse the deck's components through a shared generator module.
17. Notation and formulas follow the source and are checked against it.
18. Results figures copied exactly, with dataset and n on every plot and a y-axis on every panel.
19. Sections labelled "N · Name" and contiguous; notes cite other slides by title, never number.
20. No internal shorthand on screen or to the author: no working ids, stage codes, coined terms.

## Judgment calls

- Wording not given → ask, name + icon meanwhile; illustrative numbers → ask, then rule 8 (§3.4).
- A model drawing (tokens × layers grid, matrices, neural blocks, readouts) → `ml-visuals.md`.
- Colour → the colour rule, BUILD_GUIDE §2.2 (one per concept, contrasting, kit tokens only).
- Labels on a busy figure → `.halo`. A spotlight caption that would land on text →
  `data-caption-lane` (`top`, `bottom`, `below-title`). Results get spotlights one at a time,
  in the order of the argument, each covering the whole referent (BUILD_GUIDE §5).
- Highlight exactly the referent; long formula → term by term; prompt → `.pbox` (BUILD_GUIDE §3.2).
- Maths → `scripts/tex2svg.py` at build time, no runtime MathJax. Fragment JS → IIFE (§2.6).

## Resources

- `assets/kit.html` — the kit; read it once (classes: BUILD_GUIDE §2.5; `kit:step`). Body
  classes `slide-numbers`, `progress` (§2.7), `ov-topics`, `no-illus` (§2.10).
- `references/BUILD_GUIDE.md` — read before a first slide: kit, content rules, verify, stitch,
  orchestration, generators, patterns, publish, do-not-regress table, migration (§12).
- `references/ml-visuals.md` — model drawings and statistics; read before any ML slide.
- `references/example_{pipeline_arrows,drilldown,spotlight}_fragment.html` — copyable P3, P2
  and spotlight patterns (one `<i class="spot step" data-spot="SEL">` per step; BUILD_GUIDE §5).
- `scripts/assemble.py` — `FRAGMENT OUT` or `-o OUT FRAG…`; `--kit`, `--title`, `--body-class`,
  `--master`, `--order`, `--allow-missing`, `--asset-base`, `--check-assets` (BUILD_GUIDE §7).
- `scripts/shot.py` — `DECK PREFIX --all` (preferred) or `DECK PREFIX [N]`, `--size WxH`,
  `--start K` / `--start-id` / `--start-title`, `--click SEL`, `--then ACTION`, `--check`
  (+ `--check-size`), `--frames`, `--json FILE`, `--wait MS` (1200), `--step-timeout S` (30),
  `--load-timeout S`; `SLIDES_SHOT_SLOTS` caps parallel runs (§6.1). Exit 1: real errors, failed
  check, hang; 2: no Playwright (give the install command, never skip; no root: §6.2).
- `scripts/anim.py` — generator helpers `transfer()` (A → B) and `label_clear()` (§8.1);
  `scripts/tex2svg.py` — TeX to static SVG; **needs the network** at build time (§2.9).
