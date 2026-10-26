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
  slide to my talk deck", "fix the arrows on my slide", "the slide looks different on the
  projector". For a .pptx file use a pptx skill instead.
license: MIT
compatibility: >-
  Python 3.8+. Screenshot verification needs Playwright with Chromium
  (pip install playwright && python -m playwright install chromium). The decks are plain HTML
  and open in any modern browser.
metadata:
  version: "1.0.0"
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
| Single slide | one title + content (or one figure) | `<name>_fragment.html`, `<name>.html`, one PNG per reveal step |
| Drill-down section | an overview whose components each open a detail slide | ONE fragment with overview + all detail sections → one deck file |
| Deck stitch | several finished fragments in talk order | one deck file + a full-deck screenshot pass |
| Partial input | topic only; labels, wording or data missing | a reveal storyboard + questions; build only confirmed content |

## Procedure — one slide (P1)

1. Get title and content from the author. Ask for every missing label, caption, wording and
   data source; lean toward more questions, not fewer. Never fill a gap yourself.
2. Draft a **reveal storyboard**: entry state + N steps in placement/flow order. Confirm label
   and text choices before authoring.
3. Author `<name>_fragment.html`: one `<section class="slide <slidecls>" data-section=".."
   data-title="..">` with its own `<style>`/`<script>`. Scope every CSS rule under
   `.<slidecls>`; prefix ids and `@keyframes` with the slide class. Size in px or cqw/cqh only.
4. Assemble:
   `python3 <skill>/scripts/assemble.py <name>_fragment.html <name>.html`
   Fix every item in `warnings` (duplicate ids, dangling `data-goto`, viewport units).
5. Screenshot every step and **read every PNG**:
   `python3 <skill>/scripts/shot.py <name>.html shots/<name> <N> --check`
   Pass: entry correct; each advance reveals exactly the next bucket; arrows unchanged between
   steps and not clipped; nothing in the bottom ~100px logo band; all inside one 1280×720
   frame; `real_errors` empty and `check.pass` true (exit code 0).
6. Re-run at one off-aspect size: add `--size 1024x768`. It must be the same picture,
   letterboxed.
7. Iterate until all pass. Report the storyboard, the labels used and their source, which
   values are real and which illustrative, and the per-step screenshot verdict. Be brief.

## Procedure — drill-down section (P2)

1. Overview slide: `data-id="<hub>"`; each clickable component `data-goto="<detail-id>"`;
   each detail slide `data-id="<detail-id>"`. All in ONE fragment (navigation resolves only
   within one file); place detail sections right after the overview.
2. Components show **name + icon only**. No "click to open" on screen; that goes in the
   speaker notes.
3. The kit shows `‹ back` top-right (and Backspace); it returns to the overview fully revealed.
   Unrevealed components are not clickable.
4. Verify as P1, plus the click path, e.g.
   `shot.py deck.html shots/dd <N> --click '[data-goto=attn]' --then right --click '#back'`.

## Procedure — pipeline scheme with arrows (P3)

Copy `references/example_pipeline_arrows_fragment.html`. Boxes in a grid (rows of ≤ 3;
enlarge and add rows rather than shrink); one SVG overlay `viewBox="0 0 1280 720"` with one
filled-head `<marker>` in `#9aa3b2`; convert rects with `rectOf()`; compute arrows **once**
(double rAF + ~400 ms, then on resize/slide activation only); per-step arrow groups toggled by
**opacity only**; `.<slidecls> .step{transform:none}`. Within a row: right edge → left edge,
gap ≈ 10px. Between rows: **entry arrow only** (~34px) into the next row's first box. Labels
11px, static, ~10px above the arrow, clamped to x ∈ [70, 1210].

## Procedure — figure slide (P4)

Embed the paper's figure image as-is (data URI or relative path); never redraw it. A
one-figure slide = figure + a side reading panel that step-reveals the marks to read.

## Procedure — deck stitch (P5)

Author and verify fragments independently (parallel subagents are fine; a drill-down section
is one unit). Then `assemble.py -o deck.html f1.html f2.html …` in talk order, fix warnings,
and run `shot.py` across the whole deck (`--start K` jumps to slide K).

## Orchestrating a whole talk (agents)

For more than a slide or two, the main agent orchestrates and the plugin's agents do the work:
`talk-planner` turns the author's content into storyboards in the talk's PLAN file and returns
the open questions (relay them; build nothing with a question open); `talk-builder` builds one
confirmed storyboard per agent, several in parallel; `talk-verifier` then checks mechanics,
clarity, flow and facts on the built slides and again on the stitched deck. Relay its findings
to the author; fixes go back through a builder, never through the verifier.

## Non-negotiables

1. Build against `assets/kit.html`; never re-style a slide from scratch.
2. Master: white background, one large top-left title (Open Sans 48px), **no kicker**, two
   corner logo slots; keep content above canvas y = 620.
3. Fixed 1280×720 canvas scaled by `transform`; px or cqw/cqh only (1cqw = 12.8px,
   1cqh = 7.2px), never vw/vh/dvh/svh.
4. Step reveal: non-`.step` shows on entry; one bucket per advance; group with
   `data-step="k"`; reveal in flow order; not every word gets a step.
5. Arrows: one overlay, computed once, opacity-only reveal, mid-gray with filled heads,
   entry-arrow-only between rows, small labels with a gap.
6. Internal padding on every box; shrink the font before anything clips.
7. Minimal text: never invent labels, role text or UI hints. Ask.
8. Real data; mark illustrative values on the slide; embed figures, don't redraw.
9. Verify: screenshot every step + one off-aspect size; read every PNG.

## Judgment calls

- Wording not given → ask; meanwhile show name + icon only.
- Illustrative numbers → label them ("illustrative") and ask before presenting specifics.
- Slow conceptual step (e.g. splitting text into units) → stagger chips ~0.3 s inside one step.
- Matrices/vectors → real-looking float grids with `…`/`⋮` and highlighted rows; neural
  blocks → hidden layers only, several nodes per column; probability readouts →
  token-aligned rows, `0.58` format, `P` header, argmax highlighted, no bars.
- A transformation slide keeps item counts unless the transform changes them (logits and
  probabilities have the same length).
- One semantic color per concept (`--en` navy, `--sa` blue, `--bo` orange, `--gr` green),
  reused everywhere. Use kit tokens only; undefined variables silently drop borders.
- Fragment JS: self-contained IIFE, find its slide with
  `document.currentScript.closest('.slide')`, react to `kit:step`/`kit:unstep` or the slide's
  `active` class; never call kit functions at load (the kit script runs after fragments).

## Logos (hidden by default)

Set them once in a `<style>` inside a fragment, or edit the kit:
`:root{--logo-left:url("data:image/png;base64,…"); --logo-right:url("right.png")}`.
Or replace a slot `<div>` in the kit with `<img class="brand brand-left" src="…">`. Embed at
≥ 2× display width (left slot is 192px wide). `<body class="show-logo-slots">` outlines the
empty slots while laying out.

## Resources

- `assets/kit.html` — the kit (~19 KB). Read it once to learn the classes (`.panel`, `.chip`,
  `.counter`, `.card`, `.sub`) and the `kit:step` event.
- `references/BUILD_GUIDE.md` — read before authoring a first slide: kit architecture,
  reveal engine, arrows, verify workflow, and the do-not-regress table of past defects.
- `references/example_pipeline_arrows_fragment.html` — copyable P3 pattern.
- `references/example_drilldown_fragment.html` — copyable P2 pattern (hub + detail).
- `scripts/assemble.py` — `FRAGMENT OUT` or `-o OUT FRAG…`; `--kit` overrides the kit.
- `scripts/shot.py` — `DECK PREFIX [N]`, `--size WxH`, `--start K`, `--click SEL`,
  `--then ACTION`, `--check`, `--step-timeout S` (default 30: a slide script stuck in a loop
  ends the run with `hang`/`stuck_at` instead of freezing it); exit 1 on real errors, a failed
  check or a hang, 2 if Playwright is
  missing (tell the user the install command rather than skipping verification silently).
