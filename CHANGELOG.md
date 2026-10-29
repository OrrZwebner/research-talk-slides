# Changelog

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
