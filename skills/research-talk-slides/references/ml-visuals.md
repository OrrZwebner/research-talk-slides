# ML visuals — conventions for machine-learning and NLP slides

Load this when a slide draws a model: tokens, layers, matrices, neural blocks, attention,
probability readouts. The general rules (BUILD_GUIDE §3) still apply; this file adds the
ML-specific ones.

## 1. The tokens × layers grid

The standard picture of a transformer forward pass.

- **Tokens across, layers up.** The x axis is the token position, left to right in input order;
  the y axis is depth, with the embeddings at the bottom and the last layer (or the unembedding)
  at the top. Never swap the axes between slides.
- **Components sit in cells.** An attention block, an MLP or a head is drawn at its
  (token, layer) cell, or spans the cells it reads from.
- **Arrows run between components, never token to token.** An arrow means "this component's
  output feeds that component": attention at position i reading from position j is an arrow
  from a component in j's column into a component in i's column, not a line between the token
  labels.
- **Token indices and layer indices are distinct symbols** (e.g. `i, j` for positions and `ℓ`
  for layers), and both are keyed on the slide that uses them (BUILD_GUIDE §3.3, symbol key).
- **The drawn data flow must be correct.** What feeds which component (e.g. what the MLP
  reads as its input) is checked against the source like a number.
- Reuse one drawing of the grid across the deck through a shared generator module
  (BUILD_GUIDE §8) so that every slide uses the same spacing, colours and arrow style.

## 2. Matrices and vectors

- Real-looking float grids (`0.12  −0.47  …`), with `…` and `⋮` to elide, and highlighted rows
  or columns for the entries being discussed. A grid of identical placeholder digits looks fake.
- One-hot or id vectors are wide, with the ids as columns, `…` between them and `⋮` centred.
- **Shapes are explicit and stable.** One matrix convention for the whole deck (row vectors
  times matrices, `x W`, or matrices times column vectors, `W x`), stated once and never mixed.
  The operator order on a slide matches that convention, and vector shapes agree with it
  (a `d`-dimensional row vector stays a row).
- **Notation follows the source paper.** Symbols, subscripts and formulas are copied from it
  and checked against it, not paraphrased.

## 3. Neural blocks

- Draw hidden layers only, with several nodes per column. A lone input or output node reads as
  a single neuron and misleads.
- Name the block the way the source does (MLP, FFN, attention); do not invent sub-labels.

## 4. Probability readouts

- Rows aligned with the tokens they score; a `P` column header; values in `0.58` format; the
  argmax highlighted; no bars.
- A transformation slide keeps item counts unless the transform changes them: logits and
  probabilities have the same length.
- Every readout says what it measures on screen (a formula or a comparison), never a bare
  "restored 0.50" (BUILD_GUIDE §3.3, every number has a definition).

## 5. Tokens and text

- String tokens in quotes: `"5"`, `" Paris"` (keep a leading space when the tokenizer has one),
  so a token is never mistaken for a number or a symbol.
- An example input sits in a `.pbox` with a header naming it (e.g. "Prompt"), with enough
  context to be real and its key sentence highlighted (BUILD_GUIDE §3.2). The running example
  is named on screen in full, never by a nickname.
- A slow conceptual step (e.g. splitting text into tokens) staggers the chips by ~0.3 s inside
  one reveal step rather than spending one click per chip.

## 6. Formulas

- Pre-render TeX at build time with `scripts/tex2svg.py`; no runtime MathJax in a deck
  (BUILD_GUIDE §2.9).
- Check every formula against the paper, and check in the PNG that it actually rendered: a
  blank area passes `shot.py --check`.

## 7. Statistics a reader can interpret

- **Counts before summary scores.** For a classifier or a probe, show the confusion matrix
  (counts, with each row's pool: "40 of 50 true positives") and the accuracy per label before
  AUROC or F1. A summary score comes second, with its definition on screen (BUILD_GUIDE §3.3).
- **Name the classifier and the split.** Every score says which model or probe produced it and
  on which split: "logistic probe · held-out test split, n = 200".
- **Uncertainty where a claim needs it.** A comparison the talk relies on ("A beats B") shows a
  confidence interval or a test result (e.g. a 95% bootstrap CI as an error bar, or a p-value
  with the test named in the notes). A difference inside the interval is not called a win.
- **A baseline beside every changed outcome.** A value after an intervention stands next to the
  same value without it (and the chance level where that helps), on the same axis.

## 8. A value moving between components

A method that takes a value from one place and puts it in another (a cached activation, a
parameter, a token, a vector) is drawn with `anim.transfer` (BUILD_GUIDE §8.1):
- the **cut mark** at A says "taken out of A"; the **flight** shows the value moving; the
  **recolour** at B says "B now holds A's value";
- the source colour and the target colour are two different concept colours (BUILD_GUIDE §2.2),
  kept for the whole deck;
- reuse the same helper call (same `uid` style, colours and speed) on every slide that shows the
  method, from `build/_shared/` (BUILD_GUIDE §8), so the method has one visual metaphor;
- the animation shows the mechanism on one example; the outcome metric goes on a results slide
  (BUILD_GUIDE §3.2);
- value labels near the flight path are checked with `anim.label_clear(..., [tr.points], 6)`.

## 9. Heatmaps and dense grids

- A value that a claim relies on goes inside its cell (`0.62`; `.halo` on a dark cell).
- A spotlight on a cell also lights its row and column labels and the table row that names it
  (BUILD_GUIDE §5, rule 12).
- **Size.** Shared attributes (`stroke`, `stroke-width`, `shape-rendering`) go on a parent
  `<g>` or a CSS class, never on every `<rect>`; coordinates are rounded to 1 decimal
  (`anim.fmt`). Above about 500 cells, draw the grid as an image or a `<canvas>` and keep only
  the labels and highlighted cells as SVG. `assemble.py` warns over 2,000 `<rect>` or 500 KB per
  fragment (BUILD_GUIDE §10).
