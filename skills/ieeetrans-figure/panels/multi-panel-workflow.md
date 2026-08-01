# Multi-Panel (Panel-First) Workflow — the new logic in ieeetrans-figure

This file supplements the inherited `nature-figure` core (contract, stance,
backend fragment). It applies **only to composite figures with 2+ panels**
(multi-subplot, comparison, experiment figures). For single-panel figures,
behave exactly as `nature-figure`.

The problem this workflow solves: when a multi-panel figure is built by starting
from a shared grid and squeezing every panel into it, panels get distorted into
long thin strips, edges misalign, and the composite looks ad hoc. The fix is a
hard discipline: **panels are drawn in isolation first, the layout is drafted
and checked before any content is composed, and assembly only happens after the
user confirms the draft.**

The pipeline has four stages. None may be skipped or reordered.

---

## Stage 1 — Panel isolation: draw one panel at a time (逐图绘制)

Do **not** create the shared figure / `GridSpec` first and fill it in. Author
every panel as an **`ax`-centric function** that draws onto a given axes and
returns nothing:

```python
def panel_a(ax):
    ax.plot(...)
    ax.set_xlabel("time (s)", fontsize=8)
    ax.set_ylabel("error", fontsize=8)
```

The `ax`-centric signature is the key enabler: the **same function** renders a
standalone panel at its natural size (Stage 1) and later renders identically
inside the confirmed grid (Stage 4). Never call `plt.figure` / `plt.subplots`
inside a panel function.

Draw each panel standalone to discover its natural size:

```python
import matplotlib.pyplot as plt
w, h = 2.4, 1.2                      # natural size, from the ratio table below
fig, ax = plt.subplots(figsize=(w, h))
panel_a(ax)
fig.savefig("panels/a.png", dpi=300) # one file per panel
# record natural = (w, h) in the layout plan (Stage 3)
```

One panel at a time. Iterate each panel's content until it is right **on its
own** before any layout work. Do not tune a panel while it is already sitting in
the final grid — that is how squeezing happens.

---

## Stage 2 — Natural aspect-ratio rule (自然形状, 禁止拉伸)

- A panel's aspect ratio must come from its **content and data shape**, never
  from being fitted into a grid cell.
- Set each panel's natural size using the ratio table in
  `layout-spec-schema.md` (time series are wide; scatters near-square; heatmaps
  follow the data matrix; images keep native ratio).
- **Hard rule:** a panel may be stretched at most ±`tolerance` (default 15%)
  relative to its natural ratio to achieve grid alignment. If the layout demands
  more, restructure the grid (change rows / columns / spans) — **never distort
  the panel**. A squeezed long-thin panel is the exact failure this skill
  exists to prevent; it is a FAIL in the draft check.
- Whitespace inside a cell is acceptable; a distorted panel is not. If the
  natural sizes of the panels you need do not tile a clean grid, choose
  different rows/columns so panels that share a row have compatible natural
  heights and panels that share a column have compatible natural widths.

---

## Stage 3 — Draft layout with placeholders, then STOP for confirmation (排版草稿)

After every panel is drawn at natural size, design the layout **without any data
content**:

1. Write a **layout plan JSON** (`layout-spec-schema.md` for the format): each
   panel's label + natural size, the proposed `grid` (rows left→right, top→bottom),
   the IEEE column target (`target_width_in`: `3.5` single, `7.16` double), the
   height cap, the gutter, and the tolerance.
2. Run the draft helper on the plan:

   ```bash
   python panels/layout-draft.py plan.json --out layout_draft.png
   ```

   The script:
   - **Renders a placeholder-only draft** — empty boxes at each panel's true
     size, panel label in the corner, dashed row/column guides, IEEE width
     guides. No data, no axes — geometry only, so the discussion is purely about
     layout.
   - **Runs the geometry checks** and prints a PASS / FAIL / WARN report:
     | Check | Pass condition |
     |---|---|
     | Column width | composed width fits the IEEE target (3.5 / 7.16 in) |
     | Height cap | composed height ≤ `target_height_in` (default 4.5 in half-page) |
     | Row compatibility | panels in the same row have natural heights within tolerance (no "凸一块" step-ups) |
     | Column compatibility | panels in the same column have natural widths within tolerance |
     | Aspect fidelity | no panel's ratio deviates from natural beyond tolerance (no squeezing) |
     | Gutter uniformity | inter-panel gaps are uniform |
     | Coverage | panel area ≥ ~70% of the figure canvas (no orphan voids) |
   - Exits non-zero if any FAIL is present.
3. **Mandatory gate — STOP and show the user** the placeholder draft image and
   the check report. Ask for confirmation. If any check FAILs, revise the grid
   (regroup panels, change row/column spans, or nudge a natural size within its
   allowed range) and re-run the draft until all checks pass **and the user
   confirms**. Do not assemble before confirmation.

The user sees the arrangement of the real sizes — this is exactly the check
"排版后是否符合科研论文绘图标准" done cheaply, before content exists.

---

## Stage 4 — Final assembly (最终排版)

Only after the user confirms the draft:

1. Rebuild the figure with the **confirmed grid**, reusing the **same** `ax`-
   centric panel functions. Do not re-author any panel, do not change sizes.
2. Apply the confirmed geometry:

   ```python
   fig = plt.figure(figsize=(W_in, H_in), dpi=100)
   gs = fig.add_gridspec(nrows, ncols,
                         width_ratios=[...], height_ratios=[...],
                         wspace=0, hspace=0)          # gutters via the plan
   ax = fig.add_subplot(gs[r, c]); panel_a(ax)
   ```

   Place each panel at its natural size inside its cell (the same placement the
   draft rendered). Add panel labels **a, b, c** bold lowercase, top-left,
   ~10 pt.
3. Export the bundle — SVG + PDF + 600-dpi TIFF + 300-dpi review PNG — using the
   inherited save helper (`save_pub_py` in `static/fragments/backend/python.md`).
   **3-D panels:** `bbox_inches="tight"` is broken for 3-D axes (matplotlib
   computes a square-ish or oversized bounding box). Export 3-D panels at the
   exact figure size instead and reserve margin inside the figure for the 3-D
   axis labels and a legend band.
4. Final QA: run `scripts/validate_figure.py` on the source; open the exports at
   final size; verify text is readable (≥ 8 pt preferred), no overlaps, and the
   assembled panel sizes/alignment match the confirmed draft exactly. If the
   exact-size export clips tick labels at the figure edge, increase the layout
   `edge_in` margin rather than switching back to `bbox_inches="tight"`.

---

## IEEE-specific overrides (vs nature-figure)

These override the generic values where IEEE differs; everything else is
inherited unchanged.

- **Columns:** single = 3.5 in (88.9 mm); double (full text width) = 7.16 in
  (181.9 mm). Figures are typically one-column or double-column; do not invent
  intermediate widths.
- **Height cap:** 8.9 in absolute; prefer ≤ 4.5 in for a half-page figure.
- **Text size:** 7–9 pt at final size, prefer 8 pt (dense IEEE figures read
  better at 8+). Panel labels bold lowercase ~10 pt. Nature-figure's 7 pt is the
  floor, not the default here.
- Keep the inherited rcParams (Arial/Helvetica sans-serif, top/right spines off,
  `svg.fonttype="none"`, `pdf.fonttype=42`) unchanged.
- IEEE accepts PDF/EPS for vector figures; still deliver the inherited
  SVG+PDF+TIFF bundle.

---

## Summary of the new discipline

1. One panel at a time, `ax`-centric, natural size. (逐图绘制)
2. Natural aspect ratio or restructure — never squeeze. (自然形状)
3. Placeholder draft + geometry checks → STOP → user confirms. (排版草稿)
4. Assemble with the same functions at the confirmed sizes, then QA. (最终排版)
