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
  for layers), and both are keyed on the slide that uses them (BUILD_GUIDE §3, symbol key).
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
  "restored 0.50" (BUILD_GUIDE §3, every number has a definition).

## 5. Tokens and text

- String tokens in quotes: `"5"`, `" Paris"` (keep a leading space when the tokenizer has one),
  so a token is never mistaken for a number or a symbol.
- An example input sits in a box with a header naming it (e.g. "Prompt"). The running example
  is named on screen in full, never by a nickname.
- A slow conceptual step (e.g. splitting text into tokens) staggers the chips by ~0.3 s inside
  one reveal step rather than spending one click per chip.

## 6. Formulas

- Pre-render TeX at build time with `scripts/tex2svg.py`; no runtime MathJax in a deck
  (BUILD_GUIDE §2.9).
- Check every formula against the paper, and check in the PNG that it actually rendered: a
  blank area passes `shot.py --check`.
