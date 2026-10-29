# Contributing

## Layout rules
- `skills/research-talk-slides/SKILL.md` loads on **every** invocation. Keep it procedures and
  hard rules, under ~500 lines (currently ~200); details belong in `references/`, which load
  only when needed.
- SKILL.md frontmatter may contain only `name`, `description`, `license`, `compatibility`,
  `metadata`, `allowed-tools`. Any other key makes claude.ai uploads and packaging fail. Keep
  `description` ≤ 1024 characters.
- `skills/` is auto-discovered; do not list it in `plugin.json` or the marketplace entry.
- Scripts: Python ≥ 3.8, stdlib only (Playwright is the one optional dependency, imported
  lazily), JSON on stdout, `--help` documenting every option, exit 0 pass / 1 fail / 2
  dependency missing.
- No personal or institutional material: examples use synthetic content only, and the kit
  ships with empty logo slots.

## Tests
Run the suite before a pull request; CI (`.github/workflows/ci.yml`) runs the same command,
with Playwright + Chromium installed, on Python 3.9 and 3.12:

```bash
python3 -m unittest discover -s tests -v     # shot.py tests skip if Playwright is absent
```

The fixtures in `tests/fixtures/` are synthetic, and every expected value is fixed by how the
fixture was built (stated in its header comment), not recorded from script output. Never update an
expectation to match new output: if a value moves, the code is wrong until proven otherwise. The
one exception is `test_demo_deck_is_up_to_date`, a consistency check that the committed
`examples/demo_deck.html` matches the kit and fragment; rebuild the deck when either changes.

Rebuild the demo after changing the kit or the demo fragment, and look at the frames:

```bash
python3 skills/research-talk-slides/scripts/assemble.py examples/demo_fragment.html examples/demo_deck.html
python3 skills/research-talk-slides/scripts/shot.py examples/demo_deck.html shots/demo --all --check
python3 tools/make_demo_gif.py          # rewrites docs/demo.gif
```

## Releases
1. Bump `version` in `.claude-plugin/plugin.json` and `metadata.version` in SKILL.md.
2. Tag `vX.Y.Z` and push the tag. The release workflow (`.github/workflows/release.yml`) builds `research-talk-slides.zip` with
   `SKILL.md` one level deep (the archive for claude.ai uploads).
3. Download the zip and confirm `research-talk-slides/SKILL.md` sits at its top level.

## Volatile sources — re-check before each release
| Source | What to verify |
|---|---|
| https://playwright.dev/python/docs/intro | install command `pip install playwright` + `python -m playwright install chromium` |
| https://code.claude.com/docs/en/plugins | `plugin.json` / `marketplace.json` fields; `/plugin marketplace add` and `/plugin install name@marketplace` syntax |
| https://support.claude.com (Skills upload) | menu path for uploading a skill zip in claude.ai / the Claude app |
| https://pypi.org/project/playwright/ | the `playwright==…` pin and the Debian library path in BUILD_GUIDE §6.2 (no-root runner) |
| https://fonts.google.com | css2 API URL form used in `assets/kit.html` |
