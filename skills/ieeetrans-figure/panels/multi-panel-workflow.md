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

Create a per-figure **working directory `<outdir>`** for this run up front; it
holds the standalone panels, the layout plan + draft, and the final exports:

```
<outdir>/
  panels/                 # one standalone panel per label (Stage 1 deliverable)
    a.png  a.pdf
    b.png  b.pdf
    ...
  layout_plan.json        # written in Stage 3
  layout_draft.png
  <fig>.pdf  <fig>.svg  <fig>.tiff
```

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
os.makedirs(f"{outdir}/panels", exist_ok=True)
fig.savefig(f"{outdir}/panels/a.png", bbox_inches="tight", dpi=300)  # review copy
fig.savefig(f"{outdir}/panels/a.pdf")                       # vector, editable text
# record natural = (w, h) in the layout plan (Stage 3)
```

**The standalone files are deliverables, not scaffolding.** `panels/<label>.png`
+ `.pdf` ship with the figure so the user can take the individual panels and
reassemble, restyle, or reuse them (e.g. drop into their own Illustrator/PPT
plate, or compose a variant layout by hand). Keep each panel's natural size in
page-inches and its label in the filename. 2-D panels may use
`bbox_inches="tight"`; 3-D panels follow the same exact-size rule as the final
export (reserve margin inside the figure for labels + legend band).

**Completion gate for every panel** — a panel is *done* only when it passes both
layers of the no-occlusion gate (see the section below):

1. **Geometric check** — `check_no_overlap(fig, label="panel a")` must return no
   FAIL. Iterate the panel's content on its own (move the legend, reposition
   annotations, thin crowded ticks, enlarge the panel) until clean.
2. **Vision double-check** — run the glm-vision checklist on the saved
   `panels/a.png`; a FAIL or a WARN-that-is-real defeats. All items clear, then —
   and only then — move on to the next panel.

Do not tune a panel while it is already sitting in the final grid — that is how
squeezing happens.

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
   python panels/layout-draft.py <outdir>/layout_plan.json --out <outdir>/layout_draft.png
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
3. **No-occlusion gate on the composite (geometric layer, pre-export).** Run
   `check_no_overlap(fig, label="<fig> composite")` on the assembled figure
   *in memory, before any export*. Composite assembly is exactly where new
   collisions appear — panel labels near data, shared axes, gutters closing up.
   Iterate fixes (move legends/labels, clear gutters, add `edge_in` margin) and
   re-render until the report has no FAIL.
4. Export the bundle — SVG + PDF + 600-dpi TIFF + 300-dpi review PNG — using the
   inherited save helper (`save_pub_py` in `static/fragments/backend/python.md`).
   **3-D panels:** `bbox_inches="tight"` is broken for 3-D axes (matplotlib
   computes a square-ish or oversized bounding box). Export 3-D panels at the
   exact figure size instead and reserve margin inside the figure for the 3-D
   axis labels and a legend band.
5. **Vision double-check on the final PNG (vision layer, post-export).** Run the
   glm-vision checklist on the exported review PNG of the *whole composite* (see
   the no-occlusion section below). Nothing is final until it passes. A failure
   here means fixing, re-exporting, and re-running the gate — never shipping a
   "mostly fine" figure.
6. Final QA: run `scripts/validate_figure.py` on the source; open the exports at
   final size; verify text is readable (≥ 8 pt preferred), no overlaps, and the
   assembled panel sizes/alignment match the confirmed draft exactly. If the
   exact-size export clips tick labels at the figure edge, increase the layout
   `edge_in` margin rather than switching back to `bbox_inches="tight"`.

---

## The two-layer no-occlusion gate (严格无任何遮挡)

Complex legends, call-outs, axis labels, and annotations crowd a panel and can
cover data or one another — the exact "bad, 混乱" look we forbid. Nothing in this
skill is *done* unless it survives this gate, at **two points**: once for every
standalone panel (end of Stage 1) and once for the assembled composite (Stage 4).
The two layers play different roles:

| Layer | What it proves | Verdicts |
|---|---|---|
| 1. Geometric check (`check_overlap.py`) | Measured text/legend bounding boxes do **not** intersect (text↔text, legend↔text). Legend inside the plot area and text clipped at the edge are surfaced. | FAIL = definite collision → must fix. WARN = needs human/vision eyes. |
| 2. Vision double-check (glm-vision) | Read the rendered pixels: does a legend *cover a curve*, does a call-out *cross a point*? Geometry cannot judge this; the image can. | any real hit → fix, re-render, re-check. |

The geometric layer is per-panel cheap and deterministic, so run it on every
render; the vision layer is the mandatory final verdict on every standalone
panel and on the assembled figure.

### Layer 1 — `check_overlap.py`

Copy the script next to your plotting script (or add its `panels/` dir to
`sys.path`), then, after `fig` is drawn:

```python
from check_overlap import check_no_overlap
report = check_no_overlap(fig, label="panel a", map_path=f"{outdir}/maps/a_overlaps.png")
fails = [m for st, m in report if st == "FAIL"]   # must be empty
warns = [m for st, m in report if st == "WARN"]   # each one => vision resolves it
```

- `map_path` writes an annotated PNG drawing every element's box and highlighting
  every FAIL pair — hand it to the vision tool or the user for fast locating.
- Common fixes iteration order: move/`bbox_to_anchor` the legend to an empty
  grass area → shorten or reposition annotations → thin crowded tick labels
  (`MaxNLocator`, `plt.setp(labels, rotation=...)`) → enlarge the panel / add
  `edge_in` margin (clipped-text WARN). Fixes go into the **shared `ax`-centric
  function**, so both the standalone panel and the future composite inherit them.

### Layer 2 — glm-vision double-check

Every standalone `panels/<label>.png` **and** the final composite PNG is
inspected with the vision tool. In this skill's environment that is
`mcp__glm-vision__image_understand` — pass the saved PNG as `image_source` and
this fixed checklist as the reader prompt (adjust for whatever vision tool the
session exposes; the checklist is the contract):

```text
Check this scientific figure panel for occlusions. For each item reply PASS or
FAIL with a one-line reason:
1. Does any legend cover or block data — points, lines, bars, heatmap cells,
   other text?
2. Do any annotations/text cross, touch, or sit on top of plotted data
   (curves, symbols, fills, cells)?
3. Do any two texts collide: title vs axis label, annotation vs legend,
   annotation vs tick label, tick labels among themselves?
4. Is any element clipped at the figure/canvas edge?
5. Overall: is the panel visually crowded or messy because of overlaps?
Verdict line: FAIL if any item FAILs, else PASS.
```

A FAIL (or a WARN from layer 1 that the image confirms) sends the panel back to
iteration. Only an all-PASS world proceeds to the next panel / to delivery.

**The rule that outranks both layers:** if the vision image shows a legend
sitting on data marks or a text crossing a curve — regardless of what the
geometric bbox math printed — it is covered, fix it.

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
5. Every panel ships standalone to `<outdir>/panels/` (PNG + vector PDF) as a
   deliverable for the user's own assembly. (独立交付)
6. Two-layer no-occlusion gate on every panel and on the composite:
   geometric `check_overlap.py` + glm-vision double-check. All-clear only. (无遮挡)
