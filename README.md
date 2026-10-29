# research-talk-slides

A Claude skill that builds research-talk slides as interactive HTML on a fixed kit: you
describe a slide, it writes a small fragment, splices it into the kit, and screenshots every
reveal step to check it before you see it.

![Demo: a four-slide synthetic deck with step reveals and a drill-down into an attention detail slide](docs/demo.gif)

*Synthetic demo deck ([examples/](examples/)); all values are illustrative.*

## Installation

**There are three ways to install this. They are alternatives: pick the one that matches how
you use Claude.**

### Option A — claude.ai or the Claude app (no terminal)

1. Download **`research-talk-slides.zip`** from the
   [latest release](https://github.com/OrrZwebner/research-talk-slides/releases/latest). Don't unzip it.
2. In Claude, open **Customize → Skills** (older apps: **Settings → Capabilities → Skills**),
   click **Upload skill**, choose the file, and switch the skill on.

Use the release file, not the green **Code → Download ZIP** button: that gives you the whole
repository, which is not a valid skill upload.

### Option B — Claude Code, as a plugin

```
/plugin marketplace add OrrZwebner/research-talk-slides
/plugin install research-talk-slides@research-talk-slides
```

### Option C — Claude Code, as a standalone skill

Copy `skills/research-talk-slides/` into `~/.claude/skills/` (personal) or `.claude/skills/`
(one project).

Screenshot verification needs Python 3 and Playwright:
`pip install playwright && python -m playwright install chromium`.

## Usage

- "Make a slide for my talk showing our pipeline: A → B → C, reveal one stage per click."
- "Add an overview slide whose three components open detail slides."
- "Check my slide at 1024×768 and fix anything that clips."
- "On the next click, spotlight the third box and caption it 'our method'." (built-in spotlight: dims the slide except one region, rings it; see [the example](skills/research-talk-slides/references/example_spotlight_fragment.html))

As a plugin it also ships three agents for a whole talk (only the Claude Code plugin install
ships them; the claude.ai zip and the standalone skill do not): `talk-planner` (author's content →
reveal storyboards + open questions), `talk-builder` (one confirmed storyboard → verified
fragment; run several in parallel) and `talk-verifier` (read-only check of mechanics, clarity,
flow and facts after building, plus a compliance mode that maps every author request to a
slide). They keep the talk record in `PRD.md` (the author's words), `SPEC.md` (storyboards)
and `TBD.md` (open questions).

## What's new in 1.1.0

- **Kit**: built-in figure spotlight; optional running slide numbers and a step-aware progress
  bar (`--body-class "slide-numbers progress"`); `.halo` for labels over figures; a click guard,
  so selecting text no longer advances the deck.
- **assemble.py**: `--title`, `--master`, `--order` with `--allow-missing`, `--body-class`,
  `--asset-base`, and new lints (U+FFFD, duplicate titles, non-contiguous or mixed section
  labels, unscoped kit-class CSS).
- **shot.py**: `--all` (no step count to guess), `--json FILE`, a box-fit check and a
  1906×1000 pass inside `--check`, a small-text warning, and a 1200 ms default settle wait.
- **tex2svg.py**: pre-renders TeX to static SVG at build time (needs the network once).
- **Docs**: content rules for talk slides, ML drawing conventions
  ([ml-visuals.md](skills/research-talk-slides/references/ml-visuals.md)), generated
  fragments, several sessions on one deck, and a publish check.

Full list: [CHANGELOG.md](CHANGELOG.md).

## License

MIT — see [LICENSE](LICENSE).
