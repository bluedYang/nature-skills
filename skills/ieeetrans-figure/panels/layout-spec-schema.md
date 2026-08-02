# Layout Spec — plan JSON, natural ratio table, IEEE sizes, assembly conventions

Reference for Stage 3 of `multi-panel-workflow.md`. This file defines the JSON
contract consumed by `layout-draft.py`, the natural aspect-ratio table used in
Stage 2, the IEEE size targets, and the placement convention that Stage 4 must
follow so the final figure matches the confirmed draft.

---

## 1. Layout plan JSON

```json
{
  "title": "Fig. 3 — method comparison",
  "target_width_in": 7.16,
  "target_height_in": 4.5,
  "gutter_in": 0.14,
  "edge_in": 0.05,
  "tolerance": 0.15,
  "panels": {
    "a": { "w": 1.00, "h": 4.64, "span": [2, 1] },
    "b": { "w": 2.00, "h": 2.50 },
    "c": { "w": 1.875, "h": 2.50 },
    "d": { "w": 1.875, "h": 2.50 },
    "e": { "w": 2.00, "h": 2.00 },
    "f": { "w": 3.89, "h": 2.00, "span": [1, 2] }
  },
  "grid": [["a", "b", "c", "d"], ["a", "e", "f", "f"]]
}
```

| Field | Meaning |
|---|---|
| `title` | Figure name printed on the draft and in the report |
| `target_width_in` | IEEE column target in inches: `3.5` single, `7.16` double |
| `target_height_in` | Height cap in inches (default cap 4.5 for a half-page figure) |
| `gutter_in` | Uniform gap between panels, in inches |
| `edge_in` | Margin around the panel block, in inches |
| `tolerance` | Max acceptable ratio deviation / row or column height/width spread, as a fraction (default `0.15`) |
| `panels` | Map `label -> {"w": natural width in, "h": natural height in[, "span": [rows, cols]]}` from Stage 1/2 |
| `grid` | Reading order, top row first, each row is a list of panel labels left→right |

### Spans (asymmetric layouts)

A panel with `"span": [rows, cols]` covers `rows × cols` grid cells and its
label **repeats in the grid at every cell it covers** (see `a` spanning rows
0–1 in column 0, and `f` spanning columns 2–3 in row 1 above). The geometry
engine computes column widths and row heights from non-spanning panels; a
spanning panel's region is the union of the cells it covers, and it is placed at
its natural size inside that region (bottom-left aligned). Validation rejects a
label whose cells do not form a contiguous `rows × cols` rectangle.

Design rule for spans: set the spanning panel's natural width to the sum of the
column widths it covers plus the gutters between them (and likewise for height),
so it fills its region instead of protruding or leaving a gap.

Rules:
- Every panel label's span must cover the exact cells it occupies in `grid`; a
  `span [1,1]` (the default) appears exactly once.
- Rows may have different lengths (ragged), but a ragged row with a big empty
  trailing cell is reported as a WARN — prefer grouping so columns align.

### Checks run by `layout-draft.py`

| Check | Status on violation |
|---|---|
| Column width / height cap vs IEEE targets | **FAIL** (does not fit the column or exceeds the height cap) |
| Fill-stretch — a panel would be distorted by more than `tolerance` to fill its region | **FAIL** (the "no squeezing" gate) |
| Protrusion — a panel is larger than its region and sticks out | **FAIL** (the "凸一块" gate) |
| Row / column height or width spread > `tolerance` | WARN (shorter panels leave whitespace, bottom-aligned) |
| Coverage of the panel block < 60% | WARN (large empty regions) |
| Extreme natural ratio (outside ~0.5–4.0) | WARN (verify it is content-driven, e.g. a method strip) |

Exit code is non-zero whenever any FAIL is present.

---

## 2. Natural aspect-ratio table (Stage 2)

Set each panel's natural `w × h` from its content type. `ratio = w/h`.

| Content type | Natural ratio (w : h) | Example sizes (in) |
|---|---|---|
| Time series / 1-D trend lines | 2.0 – 2.5 | 2.4 × 1.1, 3.0 × 1.3 |
| Line plots with legend | 1.6 – 2.2 | 2.2 × 1.2 |
| Bar / grouped bar | 1.3 – 1.8 | 2.0 × 1.3 |
| Distribution (box / violin / hist) | 1.1 – 1.6 | 1.6 × 1.2 |
| Scatter / correlation | 1.0 – 1.35 | 1.4 × 1.2, 1.5 × 1.4 |
| ROC / PR curves | 1.1 – 1.4 | 1.5 × 1.2 |
| Contour / 2-D field | 1.0 – 1.4 | match the physical domain |
| Heatmap / matrix | match data cols:rows, 0.8 – 1.5 | derive from the matrix shape |
| Image / microscopy | match the image's native ratio | never stretch |

Two consequences of this table:

1. **Compatibility:** panels that will share a row should be chosen so their
   natural *heights* are close; panels that will share a column so their natural
   *widths* are close. That is what lets a grid look aligned without distortion.
2. **Extremes:** a panel whose ratio falls outside roughly 0.5 – 4.0 is reported
   as a WARN — verify it is genuinely content-driven (e.g. a very long
   heatmap), not an artifact of squeezing.

---

## 3. IEEE size specs

- **Single column:** 3.5 in (88.9 mm) wide.
- **Double column (full text width):** 7.16 in (181.9 mm) wide.
- **Text block height:** ~9.0 in; **figure height cap:** 8.9 in. Practical
  target: ≤ 4.5 in for a half-page figure; a full-page plate may use up to the
  cap.
- **Text in figures:** 7–9 pt at final size, prefer 8 pt; never below 6 pt at
  final print size. Panel labels bold lowercase ~10 pt, top-left.
- Vector output (PDF/EPS) preferred; deliver the inherited SVG+PDF+600-dpi TIFF
  bundle.

`layout-draft.py` renders two vertical guide lines on the draft at the target
width so the composability against the column is visible at a glance.

---

## 4. Assembly convention (Stage 4 must match the draft)

The draft and the final figure must be the same picture. Conventions
`layout-draft.py` assumes — reproduce them in Stage 4:

- Panels in a row are **bottom-aligned** within the row (so shared x-axes line
  up along the bottom edge).
- Panels in a column are **left-aligned** within the column.
- Row height = max natural height in the row; column width = max natural width
  in the column. A smaller panel inside its cell keeps its natural size and
  leaves whitespace — it is **not** stretched.
- The whole composed block (panels + gutters + edge) is scaled **uniformly** so
  the total width equals `target_width_in`. Uniform scaling preserves every
  panel's aspect ratio exactly; that is why the draft's ratios are faithful.
- Panel labels sit at the top-left **corner of the cell**, outside the panel
  body, ~10 pt bold.

Because assembly places each panel at natural size (never stretches to fill a
cell), the "no squeezing" rule is enforced by construction. If you want a
panel to fill its cell exactly, that is a deliberate layout choice: state it in
the plan and confirm the resulting (small) distortion stays within `tolerance`.

---

## 5. Per-panel output set (子图独立交付物)

Each standalone panel is a *deliverable*, saved under the figure's working
directory — not scaffolding. Users routinely take the individual panels and
reassemble, restyle, or reuse them (own Illustrator/PPT plate, hand-composed
variant, a different journal's template).

| Path | Content |
|---|---|
| `<outdir>/panels/<label>.png` | Standalone panel at its **natural size**, 300 dpi, `bbox_inches="tight"` (2-D) |
| `<outdir>/panels/<label>.pdf` | Same panel as vector PDF (editable text) |
| `<outdir>/panels/README.txt` (optional) | Panel label → natural size in inches, for the user's own assembly |

Rules:
- Filename = the panel's layout-plan label (`a`, `b`, …). A panel's natural
  `w × h` (in inches) is the same value recorded in the plan's `panels{}` map.
- **3-D panels:** keep `bbox_inches="tight"` off (it computes a wrong box for
  3-D axes); export at the exact figure size with margin reserved inside the
  figure for labels + legend band.
- These files are produced in Stage 1 and are not re-scaled later; Stage 4
  renders the *same* `ax`-centric function inside the confirmed grid, so the
  standalone panel and its in-figure copy stay identical.

---

## 6. No-occlusion gate reference

Every standalone panel and the assembled composite must pass the two-layer
no-occlusion gate before it counts as done (full protocol in
`multi-panel-workflow.md` → *The two-layer no-occlusion gate*).

- **Layer 1 — geometric:** `panels/check_overlap.py`, importable
  `check_no_overlap(fig, label=..., map_path=...)` → `[(status, msg)]`;
  FAIL = text↔text or legend↔text collision (must be empty), WARN = legend
  inside plot area / text clipped at edge (vision resolves). Exit code non-zero
  when a FAIL is present (`python panels/check_overlap.py --demo` self-check).
- **Layer 2 — vision:** `mcp__glm-vision__image_understand` on each saved PNG
  with the fixed occlusion checklist in the workflow doc. The image is the final
  authority: an on-data legend or a call-out crossing a curve fails regardless of
  what the bbox math printed.
