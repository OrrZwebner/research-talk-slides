---
name: research-talk-slides
description: >-
  Builds research-talk slides as interactive HTML on a fixed kit: a 1280×720 canvas that
  scales identically to any screen, a white master with a top-left title and corner
  logo slots, presenter step-reveal (one build per click), drill-down from an overview component
  to its detail slide and back, stable SVG arrows for pipeline schemes, speaker notes and a
  section map. Each slide is a small fragment spliced into the kit; every reveal step is
  screenshotted and checked before delivery. Enforces talk rules: minimal text,
  no invented labels, real data or values marked illustrative, paper figures embedded rather
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
  version: "1.1.0"
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
| Deck stitch (P5) | several finished fragments in talk order | one deck file + a full-deck screenshot pass |
| Publish (P6) | a finished deck leaves the machine | the checked deck file |
| Partial input | topic only; labels, wording or data missing | a reveal storyboard + questions; build only confirmed content |

## Procedure — one slide (P1)

1. Get title and content from the author. Ask for every missing label, caption, wording and
   data source; lean toward more questions, not fewer. Never fill a gap yourself.
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
   box fit at 1906×1000, no small text, formulas rendered, `check.pass` true, exit code 0).
6. Re-run at one off-aspect size: add `--size 1024x768`. It must be the same picture,
   letterboxed.
7. Iterate until all pass. Report the storyboard, the labels used and their source, which
   values are real and which illustrative, and the per-step screenshot verdict. Be brief.

## Procedure — drill-down section (P2)

1. Overview slide: `data-id="<hub>"`; each clickable component `data-goto="<detail-id>"`;
   each detail slide `data-id="<detail-id>"`. All in ONE fragment (navigation resolves only
   within one file); place detail sections right after the overview (they are numbered
   linearly, like any slide).
2. Components show **name + icon only**. No "click to open" on screen; that goes in the
   speaker notes.
3. The kit shows `‹ back` top-right (and Backspace); it returns to the overview fully revealed.
   Unrevealed components are not clickable.
4. Verify as P1, plus the click path, e.g.
   `python3 <skill>/scripts/shot.py deck.html shots/dd --all --check --click '[data-goto=attn]' --then right --click '#back'`.

## Procedure — pipeline scheme with arrows (P3)

Copy `references/example_pipeline_arrows_fragment.html`. Boxes in a grid (rows of ≤ 3;
enlarge and add rows rather than shrink); one SVG overlay `viewBox="0 0 1280 720"` with one
filled-head `<marker>` in `#9aa3b2`; convert rects with `rectOf()`; compute arrows **once**
(double rAF + ~400 ms, then on resize/slide activation only); per-step arrow groups toggled by
**opacity only**; `.<slidecls> .step{transform:none}`. Within a row: right edge → left edge,
gap ≈ 10px. Between rows: **entry arrow only** (~34px) into the next row's first box. Labels
12px, static, ~10px above the arrow, clamped to x ∈ [70, 1210]. Details: BUILD_GUIDE §4.

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
(`--start K` jumps to slide K).

## Procedure — publish (P6)

Before the deck leaves the machine: self-contained (no local paths; size within the host's
limit), no U+FFFD, a personal-data and logo scan (notes ship inside the HTML), `--title` set,
a final stitch without `--allow-missing` (`"skipped"` empty, no skipped-fragment warning), and a
final `shot.py --all --check`. Commands: BUILD_GUIDE §10.

## Orchestrating a whole talk (agents)

For more than a slide or two, the main agent orchestrates and the plugin's agents do the work
(Claude Code plugin install only; otherwise run the same roles yourself, in order).
The talk record is **PRD.md** (the author's words, verbatim, never reworded), **SPEC.md**
(storyboards; superseded ones go to `SPEC-archive.md`) and **TBD.md** (open questions); a
small talk may keep them in one PLAN file.
- `talk-planner` turns dictated content into storyboards in SPEC.md and returns the open
  questions (also written to TBD.md). Relay them to the author; it plans nothing before the
  author has dictated content.
- `talk-builder` builds one confirmed storyboard per agent, several in parallel. **STOP means
  stop**: while a question is open it builds nothing, not even a default.
- `talk-verifier` checks mechanics, clarity, flow and facts on the built slides and again on
  the stitched deck; in **compliance mode** it maps every author input in PRD.md to slide ·
  step · PNG · status. Relay its findings; fixes go back through a builder, never the verifier.
- A report longer than about 30 lines goes to a file; agents return a summary plus its path.
- Several sessions on one deck: one owner per section; only the orchestrator edits ORDER,
  master and stitch, and publishes (BUILD_GUIDE §7.3).

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
8. Real data; mark illustrative values on the slide; embed figures, don't redraw.
9. Verify: screenshot every step + one off-aspect size; read every PNG.

Content rules (detail and examples in BUILD_GUIDE §3):

10. Titles plain, direct, exact and technical; never catchy.
11. Picture over text: an explanatory sentence becomes a scheme, symbol or formula.
12. A process gets one reveal step per stage; never all at once, never padding steps.
13. Every symbol is keyed on its slide, in the step it appears: a muted line ≥ 16px; ≤ 4 per slide.
14. Every arrow, dashed line and legend entry is explained on screen; prefer labels on the drawing.
15. Every number on screen shows its definition (a formula or a comparison).
16. One visual language: reuse the deck's components through a shared generator module.
17. Notation and formulas follow the source and are checked against it.
18. Results figures copied exactly, with dataset and n on every plot and a y-axis on every panel.
19. Sections labelled "N · Name" and contiguous; notes cite other slides by title, never number.

## Judgment calls

- Wording not given → ask; meanwhile show name + icon only.
- Illustrative numbers → label them ("illustrative") and ask before presenting specifics.
- A model drawing (tokens × layers grid, matrices, neural blocks, probability readouts, string
  tokens in quotes) → follow `references/ml-visuals.md`.
- One semantic colour per concept (`--en` navy, `--sa` blue, `--bo` orange, `--gr` green),
  reused everywhere. Use kit tokens only; undefined variables silently drop borders.
- Maths → pre-render TeX at build time with `scripts/tex2svg.py`; no runtime MathJax.
- Labels on a busy figure → `.halo`. A spotlight caption that would land on text →
  `data-caption-lane`. One spotlight at a time, only where it adds something.
- Fragment JS → self-contained IIFE; rules in BUILD_GUIDE §2.6.

## Resources

- `assets/kit.html` — the kit (~35 KB). Read it once to learn the classes (`.panel`, `.chip`,
  `.counter`, `.card`, `.sub`, `.halo`) and the `kit:step` event. Optional chrome:
  `slide-numbers` and `progress` body classes (BUILD_GUIDE §2.7).
- `references/BUILD_GUIDE.md` — read before authoring a first slide: kit architecture,
  reveal engine and click guard, content rules, arrows, spotlight, verify workflow, stitch and
  lints, generated fragments, publish, and the do-not-regress table of past defects.
- `references/ml-visuals.md` — conventions for model drawings; read before any ML slide.
- `references/example_pipeline_arrows_fragment.html` — copyable P3 pattern.
- `references/example_drilldown_fragment.html` — copyable P2 pattern (hub + detail).
- `references/example_spotlight_fragment.html` — built-in spotlight: one `<i class="spot step"
  data-spot="SEL">` per step dims the slide except SEL, rings it (optional sub-rect, caption,
  caption lane); API and rules in BUILD_GUIDE §5.
- `scripts/assemble.py` — `FRAGMENT OUT` or `-o OUT FRAG…`; `--kit`, `--title`,
  `--body-class`, `--master`, `--order` (+ `--allow-missing`), `--asset-base` (BUILD_GUIDE §7).
- `scripts/shot.py` — `DECK PREFIX --all` (preferred) or `DECK PREFIX [N]` (default 8),
  `--size WxH`, `--start K`, `--click SEL`, `--then ACTION`, `--check` (+ `--check-size`),
  `--json FILE`, `--wait MS` (default 1200), `--step-timeout S` (default 30); exit 1 on real
  errors, a failed check or a hang, 2 if Playwright is missing (tell the user the install command
  rather than skipping verification silently; no root: BUILD_GUIDE §6.2).
- `scripts/tex2svg.py` — pre-renders TeX to static inline SVG (`tex2svg.py '\alpha_i'
  --display`, or `--json IN.json OUT.json`; `--mathjax URL` overrides the CDN; exit 1 if a formula
  fails to render). **Needs the network** at build time (MathJax from
  jsDelivr) and Playwright; the output works offline and draws in `currentColor`.
