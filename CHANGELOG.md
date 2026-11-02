# Changelog

## 1.2.0 — 2026-11-02

Every new kit feature is opt-in: a deck without the new attributes and classes behaves as with
the 1.1.0 kit, and the 1.1.0 tests are kept; one expected lint message changed to name the
new `below-title` lane. The one always-on change is the
replay guard, which only shortens animations that would otherwise replay.

### Kit (`assets/kit.html`)
- **Backup slides** (`data-offpath`): skipped by the → / ← walk and opened only by
  `data-goto`; → past the last step or ← before the first returns to the slide that opened it
  (else to the first slide that links to it). Several hubs may share one backup. Slide numbers,
  progress bars, side dots and the overview count on-path slides only.
- **Replay guard** in `go()`: arriving on a slide backwards, or on a step > 0, finishes its
  finite CSS animations and transitions; infinite ones keep running.
- **`data-autoplay`**: class `playing` while the slide is active, so an entry or looping
  animation restarts on every entry; `--anim-speed` (default 1) scales durations written as
  `calc(Ts / var(--anim-speed))`.
- **`data-toggle="cls"`**: a click toggles a class on the slide without advancing; reset on
  leaving the slide and on every step change; keyboard-safe.
- **`data-hide-at="k"`**: hide an element once step k is revealed; with `.swap`, replace A by B
  in place. A malformed value is a console error.
- **Topic overview**: `data-topic` + `body.ov-topics` gives one tile per topic, grouped by
  section, built from the slides.
- **`.pbox` / `.pbox-h`**: a prompt box with an accent edge (`--accent`, or `.en .sa .bo .gr`).
- **Spotlight caption lane `below-title`**: the caption sits 12 px under the title.
- **`.illus`** marks the on-slide "illustrative" tag; `body.no-illus` hides them all.

### `scripts/shot.py`
- `--load-timeout S` bounds the page load (default: the larger of 30 and `--step-timeout`); a
  load past it ends as a hang with `"stuck_at": "load"`. The load waits for
  `DOMContentLoaded`, then for fonts and pending images, instead of the `load` event.
- `--frames T1,T2,…`: timed shots of the entry state, for autoplay and looping slides.
- `--start-id ID` / `--start-title T`: start at a named slide. `--start K` keeps its meaning
  (the K-th slide in the file, 1-based): it equals the on-screen number unless a backup
  (`data-offpath`) slide comes earlier.
- Machine-wide Chromium slot lock: `SLIDES_SHOT_SLOTS` (default 2; 0 = no limit),
  `SLIDES_SHOT_LOCK_DIR`.
- `--click` falls back to a JS dispatch on an element with no box, or whose point click lands
  on its own ancestor (SVG `<g data-goto>`); the shot notes it.
- A font, image, stylesheet or media file that fails to load prints a warning and is listed
  under `"failed_assets"`.
- `data-small-ok="reason"` exempts intended small text from the small-text warning (`small_ok`).
- `--help` says that `--json` needs a path.

### `scripts/assemble.py`
- `--check-assets`: warns on relative URLs whose file is missing; JSON `"assets"`.
- Size lints: a fragment over 500 KB, or with more than 2,000 `<rect>`.
- Markup lints skip `<script>` bodies (a `data-goto` or `<section>` in JS text no longer counts).
- Backup slides are left out of the section-contiguity lint.
- Refused calls write nothing and leave no stale output: a fragment as OUT (two fragments
  without `-o`) is refused, and an earlier deck at OUT is renamed `OUT.stale`.
- The caption-lane lint accepts `below-title`.

### `scripts/anim.py` (new)
- `transfer()`: SVG + CSS for a value moving from A to B (optional cut mark, flight, recolour
  on landing), with its timings and path points; triggered by a step (`.step.shown`) or an autoplay
  slide (`.slide.playing`, joined to the scope); `speed=` sets the pace.
- `label_clear()`: asserts that value labels keep a minimum distance from marks and paths.
- `text_box()`, `bezier_points()`, `fmt()`. Stdlib only; `python3 anim.py` runs the examples.

### Documentation
- `SKILL.md`: version 1.2.0; mode table and procedures point to the new abilities; rule 8 and
  its judgment call follow the illustrative-values decision (declared in notes and SPEC, `.illus`
  unless a `no-illus` waiver is recorded in PRD.md, never contradicting real data); content
  rules on purpose, mechanism over metric, number placement and format, and no internal
  shorthand; the orchestration section covers note intake and the orchestrator's role.
- `references/BUILD_GUIDE.md`:
  - §2.10 interaction attributes; layout classes listed in §2.5; `--mathjax` in §2.9; the
    colour rule kept once, in §2.2;
  - §3 content rules regrouped, with new rules (no internal shorthand; numbers on the drawing
    with one format; headers naming metric and data; counts naming their pool; mechanism on one
    example; formulas term by term; exact referent; plain legends; readable plots; slide
    purpose; example prompts with context and in-place flips; spotlights in argument order;
    contrast between concept colours; illustrative values);
  - §5 rule 12, spotlights cover the whole referent; the `below-title` lane;
  - §6 `--frames`, the slot lock, `--load-timeout`, `--start` semantics, the motion budget;
  - §7 `--check-assets`, refused calls, new lints; §7.3 orchestration (intake ledger,
    plan-only vs execute, slide numbers resolved to titles, delegation and take-over, stitch
    lock, one version label, incremental check, deadline freeze, option decks, removed notes to
    TBD, asking before republishing a live link);
  - §8 `build/_shared/`, hashed copies with a test, a README per generator, §8.1 `anim.py`;
  - §9.1 back-navigation and a check for the zoom pair; §9.3 fold / shrink morph;
  - §10 `--check-assets`, a size budget, verifier and live-link steps;
  - §11 do-not-regress rows 60–91; §12 migrating decks started before 1.1 or 1.2.
- `references/ml-visuals.md`: interpretable statistics (confusion matrix and per-label accuracy
  before AUROC or F1, CIs, classifier and split named, a baseline beside a changed outcome); a
  value moving between components (`anim.transfer`); heatmap size.
- README and CONTRIBUTING updated.

### Agents
- `talk-planner`: note intake (plan-only or execute, slide numbers mapped to titles, an
  intake-ledger row in TBD.md, research questions to TBD); illustrative values per the new rule;
  option decks; plain words to the author.
- `talk-builder`: on-screen wording is never its decision ("Wording I chose (author to
  confirm)"); exact referent; reuses shared animations; `.illus` unless waived; motion budget
  and `--frames`.
- `talk-verifier`: a mechanical symbol-key check; a grep for internal ids; slide purpose,
  mechanism and term-by-term formulas; deck-wide duplicate-purpose and number-format checks;
  facts recomputed from on-screen formulas, schematics checked against the run configuration,
  counts naming their pool; flow and compliance mandatory before any publish; a reminder to ask
  before republishing a live link.

### Tests and CI
- New kit tests (`tests/test_kit_v12.py`, fixtures `k12_*`), including a walk of existing decks
  on the 1.1.0 and 1.2.0 kits comparing the state at every step, and seam tests for the zoom
  pair and the fold morph (BUILD_GUIDE §9.1, §9.3); script tests
  (`tests/test_scripts_v12.py`, fixtures `s12_*`). CI compiles `anim.py` and runs its examples.
  Demo deck and GIF rebuilt.

### Since 1.1.0, before this release
- Commit 5633a1d (BUILD_GUIDE §7.3 and §8): verify a fresh assembly rather than the last
  stitched deck; route new notes to the slide's current builder; detect a stopped builder's
  half-done work with a scratch rebuild and `cmp`; commit only your own paths and check
  `git log origin/main..HEAD` before pushing; change a shared module behind an opt-in argument,
  then byte-compare every user.

## 1.1.0 — 2026-10-29

### Kit (`assets/kit.html`)
- **Spotlight**: an `<i class="spot step" data-spot="SEL">` marker whitens the slide except
  one region (and the title), rings it, and optionally shows the author's caption with a leader
  line, for exactly one reveal step. Options: `data-spot-rect`, `data-pad`, `data-caption`,
  `data-caption-pos`, `data-tone`, `data-veil-title`, `data-ring="none"`. Invalid values log a
  console error. New example: `references/example_spotlight_fragment.html`.
- **Spotlight caption lane**: `data-caption-lane="top|bottom"` puts the caption in a fixed band
  so it does not land on the subtitle.
- **Click guard**: a drag of more than 4 px, a click while text is selected, or a
  word-selecting double-click gives no net advance. Buttons, links, inputs, `[data-goto]`,
  `[data-noadvance]` and the kit chrome never advance.
- **Slide numbers** (`<body class="slide-numbers">`): DOM-order number in the logo band; the
  title slide shows none; `data-nonum` hides one; position via `--num-right` / `--num-bottom`.
- **Progress bar** (`<body class="progress">`): a 6 px bottom bar that moves on every slide and
  every reveal step; replaces the top bar and the side dots in that mode.
- **`.halo`**: white outline for text over figures (SVG stroke under the fill; HTML
  text-shadow); colour via `--halo`.
- All new chrome is off by default; existing decks look the same.

### `scripts/assemble.py`
- New options: `--title`, `--body-class`, `--master`, `--order` (needs `-o`),
  `--allow-missing`, `--asset-base`. The old forms and JSON keys are unchanged.
- New lints (warnings only): U+FFFD replacement characters (a fragment with an invalid UTF-8
  byte now warns instead of crashing); duplicate `data-title`; non-contiguous `data-section`;
  mixed `data-section` styles; unscoped CSS that restyles kit classes on every slide; invalid
  `data-caption-lane`; spotlight markers without `step`; malformed `data-spot-rect`;
  `data-ring` other than `none` (or `none` with a caption).
- The vw/vh lint skips `data:` URIs.

### `scripts/shot.py`
- `--all`: advance until the deck's last step; works with `--start K`.
- `--json FILE`: JSON to a file, all diagnostics on stderr.
- `--check` adds a box-fit check (text outside its framing box by > 1.5 canvas px) and an
  extra pass at 1906×1000 (`--check-size WxH`, repeatable; `none` to skip).
- Small-text warning under `--check` for text rendered below 12 canvas px.
- Default `--wait` raised from 550 to 1200 ms, so screenshots no longer catch mid-fade frames.
- Chromium launch has its own watchdog (≥ 60 s), separate from `--step-timeout`.
- The small-text pass no longer crashes on an SVG `<title>`, `<desc>` or `<metadata>`, or on
  HTML inside a `<foreignObject>`.
- Shots of slides with spotlight markers report the lit targets under `"spot"`.

### `scripts/tex2svg.py` (new)
- Pre-renders TeX to self-contained static SVG with MathJax 3 in headless Chromium
  (`--display`, `--json IN OUT`). Needs the network at build time; the output works offline.
- CI compiles it and runs `--help`.

### Documentation
- `SKILL.md`: content rules as one-line non-negotiables (plain titles, picture over text,
  one reveal step per stage, symbol keys on the slide, every connector and number explained,
  one visual language, faithful notation, results figures, section labels); a publish
  procedure (P6); the agents' talk record and STOP contract. Duplicated text moved to
  `BUILD_GUIDE.md`.
- `references/BUILD_GUIDE.md`: click guard; slide numbers and progress bar; sections and
  numbering ("N · Name", contiguous, drill-down slides numbered linearly, notes cite slides by
  title); reveal order follows the DOM; TeX pre-rendering; content rules in detail; shot.py
  options and the wait default; a no-root runner; stitch options and lints; several sessions
  on one deck; generated fragments (generator in `build/NN/`, README, asserted values,
  byte-identical rebuild check, shared modules); camera/zoom continuity; "lift text, keep
  geometry" for embedded SVGs; the publish check; do-not-regress rows 27–29 and 32–59.
- `references/ml-visuals.md` (new): tokens × layers grid, matrices and vectors, neural blocks,
  probability readouts, string tokens in quotes, formulas.

### Agents
- All three use the talk record PRD.md / SPEC.md / TBD.md (a single PLAN file for a small
  talk) and send reports longer than about 30 lines to a file.
- `talk-planner`: plans nothing before content is dictated; collects notes until the author
  says go; writes open questions to TBD.md; applies the content rules.
- `talk-builder`: STOP means stop; edits generators in `build/NN/` after a byte-identical
  rebuild check; previews with the talk's master; uses `--all --check --json` under `timeout`;
  never adds labels, sizes or status markers; re-reads files after an interruption.
- `talk-verifier`: symbol inventory, unrequested or repeated content, drawn data flow, number
  definitions, rendered formulas, box fit at the author's desktop viewport (default 1906×1000),
  notes that cite slides by title, fixes that never add text, and a compliance mode.

### Tests and CI
- Tests and fixtures for every new `assemble.py` and `shot.py` option, lint and kit feature;
  `tex2svg.py` is checked with `--help` only (rendering needs the network). CI runs `--check` at
  1280×720, 1024×768 and 1906×1000. Demo deck and GIF rebuilt.

## 1.0.0

- Initial release: kit, `assemble.py`, `shot.py`, BUILD_GUIDE and examples. Later commits
  under the same version number added the three talk agents, `shot.py --step-timeout` and
  do-not-regress rows 30–31.
