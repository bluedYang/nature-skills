# ieeetrans-figure

A Claude Code skill for producing **submission-grade IEEE Transactions
multi-panel figures** in Python (matplotlib/seaborn) or R. It is a subclass of
the [nature-figure] skill: it inherits the full figure contract, default
stance, Python/R backend gate, QA contract, and export bundle, and adds one
new capability — a disciplined **panel-first** workflow that prevents the
layout defects that appear when a large composite figure is drawn in a single
pass (squeezed long-thin panels, uneven edges, "sticking-out" cells).

## Why this skill exists

When a big multi-panel figure (a method strip + a hero panel + matched
validation panels + a quantitative panel) is plotted by drawing the whole
`GridSpec` at once, panels get squeezed into the fixed grid cells, aspect
ratios distort, and the composite looks ad hoc. This skill enforces a gate:

1. **Panel isolation** — draw one panel at a time, each as an `ax`-centric
   function at its natural size.
2. **Natural aspect ratio** — a panel may be stretched at most ±`tolerance`
   (default 15%) to achieve grid alignment; beyond that the grid is
   restructured, never the panel.
3. **Draft layout gate** — after all panels are drawn, `panels/layout-draft.py`
   renders a placeholder-only draft (no data) at each panel's true size and
   runs geometry checks against the IEEE column targets (single 3.5 in, double
   7.16 in). It **stops for user confirmation** before any content is composed.
4. **Final assembly** — the same `ax`-centric functions are reused at the
   confirmed sizes and exported SVG + PDF + 600-dpi TIFF.

## Layout plan

A composite figure is described by a small JSON plan (see
`panels/layout-spec-schema.md`): each panel's natural size, an optional
`"span": [rows, cols]` for asymmetric layouts, and the grid. Example:

```bash
python panels/layout-draft.py plan.json                 # checks + draft.png
python panels/layout-draft.py plan.json --json          # machine-readable
python panels/layout-draft.py plan.json --out d.png --dpi 200
```

`layout-draft.py` reports **FAIL** when a panel would be stretched, protrudes
beyond its region, or the composed figure exceeds the column width / height
cap, and exits non-zero. A bundled example is in `panels/example-plan.json`.

## Directory structure

```
ieeetrans-figure/
├── SKILL.md                    # router: inherits nature-figure + adds the panel-first gate
├── manifest.yaml                # always_load + the panels/ reference table
├── panels/                     # THE new logic (this skill's only own content)
│   ├── multi-panel-workflow.md # the 4-stage panel-first protocol
│   ├── layout-spec-schema.md   # plan JSON, natural-ratio table, IEEE specs
│   ├── layout-draft.py         # placeholder draft renderer + geometry checks
│   ├── test_layout_draft.py    # regression tests for the geometry engine
│   └── example-plan.json       # runnable example (0 FAIL)
├── static/    ─┐
├── references/─┤  symlinked to ../nature-figure/   ← inherited logic
├── scripts/   ─┤
└── assets/    ─┘
```

## Inheriting nature-figure (read before publishing)

The `static/`, `references/`, `scripts/` and `assets/` directories are
**symbolic links** to `../nature-figure/`. That is what makes this a subclass:
any `nature-figure` update propagates automatically. When publishing this repo,
decide how to make the inheritance reproducible:

- **Option A (recommended):** publish `nature-figure` alongside, keep the
  symlinks, and document the layout (`nature-figure/` must sit as a sibling),
  or add it as a git submodule.
- **Option B:** vendor the four directories (copy them in) so the repo is fully
  self-contained; you lose automatic updates.

Only `panels/` and the two top-level files (`SKILL.md`, `manifest.yaml`) are
this skill's own work.

## Dependencies

- Python 3.9+
- `matplotlib` (for `layout-draft.py`; figures themselves are drawn by the
  selected backend)
- No other runtime requirements. The geometry engine is pure arithmetic;
  `panels/test_layout_draft.py` runs without matplotlib.

## Tests

```bash
python panels/test_layout_draft.py       # 15 regression checks (no matplotlib needed)
```

Covers the two historical placement bugs (region boxes shifted down; positions
not scaled when the composition is rescaled to the target column width), span
handling, the protrusion check, and the validation errors.

## License / attribution

`ieeetrans-figure` is a derivative of the [nature-figure] skill from
[`Yuan1z0825/nature-skills`](https://github.com/Yuan1z0825/nature-skills)
(commit `fac88c4`), which is licensed under the **Apache License 2.0**. The
inherited `static/`, `references/`, `scripts/` and `assets/` directories are
unmodified upstream content; this skill's own additions are `panels/`,
`SKILL.md`, `manifest.yaml` and this README. This work is distributed under the
same Apache-2.0 license (see the repository `LICENSE`).

[nature-figure]: ../nature-figure
