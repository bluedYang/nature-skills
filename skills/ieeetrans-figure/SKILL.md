---
name: ieeetrans-figure
description: >-
  Create, revise, audit, and export submission-grade scientific figures for IEEE Transactions and other journals in Python (matplotlib/seaborn) or R. Inherits the full nature-figure logic — figure contract, default stance, Python/R backend gate, QA contract, and export bundle — via the shared static/references/scripts/assets layer. Adds one new panel-first workflow for composite (2+ subplot) figures: draw each panel one at a time at its own natural aspect ratio (no squeezing panels into long thin strips to fill a grid), then render a placeholder-only layout draft that arranges each panel at its true size, checks it against IEEE single-column (3.5 in) or double-column (7.16 in) width with alignment / aspect-fidelity / gutter checks, show the draft to the user for confirmation, then assemble the final multi-panel figure. Single-panel figures behave exactly as nature-figure. Use for IEEE Trans figures, 多子图组合图、实验对比图、子图排版、论文配图、科研绘图、科研作图、出图、论文图表. Do not use for interactive dashboards, statistics-only analysis, data cleaning, literature review, code debugging, pure photo editing, or non-manuscript infographics.
---

# IEEE Trans Figure Making — Router (subclass of nature-figure)

This skill **inherits all of `nature-figure`'s logic** and adds one new capability:
a disciplined **panel-first** workflow for multi-panel composite figures.

- The shared layer — `static/`, `references/`, `scripts/`, `assets/` — is a
  symlink to `../nature-figure/`. Everything inherited stays identical and picks
  up future `nature-figure` updates automatically. Do not treat it as this
  skill's own content.
- The new logic lives in this file plus `panels/` (`multi-panel-workflow.md`,
  `layout-spec-schema.md`, `layout-draft.py`).

Do not try to apply the figure logic from memory or from this router. Always load
fragments from disk as described below.

## Routing protocol

Follow these steps every time the skill is invoked.

### 0. OpenRouter AI-schematic route (inherited)

If the user explicitly asks to generate a manuscript schematic, graphical
abstract, mechanism diagram, concept illustration, or paper schematic with
OpenRouter, GPT Image 2, or an image-generation API, do **not** ask "Python or
R?". Read `references/openrouter-image-generation.md` and use
`scripts/generate_openrouter_schematic.py`, treating the output as a draft
schematic. Only continue to the Python/R backend gate for plotting, charting,
data visualization, or manuscript figure assembly tasks that are not explicit
AI image-generation requests.

### 1. Load the inherited core layer

Read `static/core/contract.md` and `static/core/stance.md` (the figure contract,
the backend gate, the missing-runtime rule, the privacy rule, and the default
operating stance). These are inherited verbatim from `nature-figure`.

Read `manifest.yaml` for this skill's own axes and the `panels/` reference table.
The full `nature-figure` reference table is declared in `../nature-figure/manifest.yaml`
and is reachable through the symlinked `references/` directory; open those files
on demand exactly as `nature-figure` does.

### 2. Resolve the backend — a blocking gate (inherited)

Backend selection blocks plotting tasks, but should not annoy the same user
forever. Decide the `backend` value in this order:

1. If the current request explicitly chooses Python or R, use that backend and
   save it with `scripts/nature_figure_backend.py set python` or
   `scripts/nature_figure_backend.py set r`.
2. If the request provides a clearly language-specific input file/workflow, use
   that backend and save it.
3. Otherwise run `scripts/nature_figure_backend.py get`. If it returns `python`
   or `r`, use the saved preference.
4. If no saved preference exists, ask exactly one concise question — **Python or
   R? I will remember this as your default.** — and stop. Save the answer before
   proceeding.

`python` — matplotlib / seaborn. `r` — ggplot2 / patchwork / ComplexHeatmap.
Once selected, the backend is **exclusive** for all drawing, previewing,
exporting, and visual QA (see `static/core/contract.md`). This gate does not
apply to the OpenRouter route in step 0.

### 3. Load the matching backend fragment (inherited)

After the backend is resolved, Read the mapped fragment
(`static/fragments/backend/python.md` or `static/fragments/backend/r.md`). Do
**not** load the other backend's fragment.

### 4. Count the panels — the new branching rule

Determine how many panels the figure has:

- **Single panel** — follow `nature-figure` exactly: apply the loaded contract
  and stance, build the figure, export, QA. No layout work needed.
- **Composite figure with 2+ panels** (multi-subplot / comparison / experiment
  figure) — load `panels/multi-panel-workflow.md` and follow its protocol:
  1. **Panel isolation** — draw one panel at a time, each as an `ax`-centric
     function at its natural size.
  2. **Natural aspect ratio** — no panel is squeezed to fit a grid cell; ratio
     deviation beyond tolerance is forbidden.
  3. **Draft layout gate** — write the layout plan JSON, run
     `panels/layout-draft.py` to render a placeholder-only draft and geometry
     checks, then **STOP and show the draft + report to the user for
     confirmation** before assembling.
  4. **Final assembly** — only after confirmation, reuse the same panel
     functions inside the confirmed grid and export.

The chart serves the scientific logic; aesthetic polish is subordinate to making
the core conclusion clear, defensible, and reviewable.

### 5. Reach for references only when needed

- `references/figure-contract.md` — convert the request into core conclusion,
  evidence chain, panel map, archetype.
- `panels/multi-panel-workflow.md` — the panel-first protocol for 2+ panel figures.
- `panels/layout-spec-schema.md` — layout-plan JSON format, natural aspect-ratio
  table, IEEE size specs, assembly conventions.
- `references/asset-adaptation.md` — reuse bundled examples or user templates.
- `references/api.md` — Python palette and helpers.
- `references/common-patterns.md`, `references/chart-types.md`,
  `references/nature-2026-observations.md` — layout/chart recipes.
- `references/qa-contract.md` — load before final delivery.

### 6. Delivery preflight (inherited)

Before final delivery, load `references/qa-contract.md`, run
`scripts/validate_figure.py` on the plotting source, then inspect the rendered
outputs at final size. For multi-panel figures, additionally verify that the
assembled figure matches the confirmed draft (same panel sizes, same alignment,
no panel visibly distorted).

## Why this split

- `ieeetrans-figure` is a thin subclass router: it inherits the complete
  `nature-figure` static/reference/script layer and adds only the multi-panel
  discipline that Nature-style single-figure routing does not enforce.
- The new logic is a hard gate: panels are drawn in isolation, the layout is
  drafted and checked against IEEE column widths before any content is composed,
  and assembly only happens after the user confirms the draft.
- This file is short on purpose. Update `panels/` files, not this router, when
  adding scope.
