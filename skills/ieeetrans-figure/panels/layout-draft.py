#!/usr/bin/env python3
"""
layout-draft.py — placeholder layout draft + geometry checks for multi-panel
IEEE-style figures.

Reads a layout plan JSON (see panels/layout-spec-schema.md), renders a
placeholder-only draft PNG (empty boxes at each panel's true size — no data
content), runs the geometry checks against the IEEE column targets, prints a
PASS / FAIL / WARN report, and exits non-zero if any FAIL is present.

Supports asymmetric layouts: a panel may span multiple rows/columns with an
optional `"span": [rows, cols]` in its spec (see the schema doc). A spanning
panel's label repeats in the grid at every cell it covers.

This is Stage 3 of the panel-first workflow. The draft deliberately contains no
data so the layout can be reviewed and confirmed before any content is composed.

Usage:
    python panels/layout-draft.py plan.json
    python panels/layout-draft.py plan.json --out draft_layout.png --dpi 200
    python panels/layout-draft.py plan.json --json
"""

import argparse
import json
import sys

try:
    import matplotlib
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
except ImportError as exc:  # pragma: no cover
    sys.exit(f"layout-draft.py needs matplotlib. Install it or use the right env. ({exc})")

# IEEE column widths, inches
IEEE_SINGLE_IN = 3.5
IEEE_DOUBLE_IN = 7.16

# colors for the placeholder draft
CELL_FACE = "#e8e8e8"
CELL_EDGE = "#b0b0b0"
PANEL_EDGE = "#1f77b4"
GUIDE = "#999999"
TEXT = "#333333"

# --------------------------------------------------------------------------
# plan loading / validation
# --------------------------------------------------------------------------

def load_plan(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _span(spec):
    """Return (sr, sc); default [1, 1]."""
    sp = spec.get("span", [1, 1])
    if isinstance(sp, dict):
        return int(sp.get("rows", 1)), int(sp.get("cols", 1))
    return int(sp[0]), int(sp[1])


def validate(plan):
    """Return a list of hard plan errors (empty list = valid)."""
    errors = []
    panels = plan.get("panels", {})
    grid = plan.get("grid")

    if not isinstance(panels, dict) or not panels:
        errors.append("'panels' must be a non-empty dict of label -> {w,h[,span]}")
    if not isinstance(grid, list) or not grid:
        errors.append("'grid' must be a non-empty list of rows")
    for lab, spec in panels.items():
        if not isinstance(spec, dict):
            errors.append(f"panel '{lab}' must be an object with w and h")
            continue
        w, h = spec.get("w"), spec.get("h")
        if not (isinstance(w, (int, float)) and isinstance(h, (int, float)) and w > 0 and h > 0):
            errors.append(f"panel '{lab}' needs positive numeric w and h")
        sr, sc = _span(spec)
        if sr < 1 or sc < 1:
            errors.append(f"panel '{lab}' has invalid span [{sr}, {sc}]")

    if not errors and isinstance(grid, list):
        # build position -> label map
        pos = {}
        for r, row in enumerate(grid):
            if not isinstance(row, list) or not row:
                errors.append(f"grid row {r} is empty (every row needs at least one panel)")
                continue
            for c, lab in enumerate(row):
                if lab not in panels:
                    errors.append(f"grid references '{lab}' but 'panels' has no such key")
                    continue
                if (r, c) in pos:
                    errors.append(f"cell ({r},{c}) is covered twice")
                    continue
                pos[(r, c)] = lab

        # every declared panel must be placed and its positions must form the span rectangle
        from collections import defaultdict
        occ = defaultdict(list)
        for (r, c), lab in pos.items():
            occ[lab].append((r, c))
        for lab in panels:
            if lab not in occ:
                errors.append(f"panel '{lab}' is declared but never placed in 'grid'")
                continue
            sr, sc = _span(panels[lab])
            cells = occ[lab]
            if len(cells) != sr * sc:
                errors.append(f"panel '{lab}' span [{sr},{sc}] needs {sr*sc} cells "
                              f"but appears {len(cells)} time(s)")
                continue
            rs = sorted({r for r, _ in cells})
            cs = sorted({c for _, c in cells})
            rect = {(r, c) for r in range(rs[0], rs[0] + sr)
                             for c in range(cs[0], cs[0] + sc)}
            if set(cells) != rect:
                errors.append(f"panel '{lab}' cells do not form a contiguous "
                              f"{sr}x{sc} rectangle")
        # every grid cell must be reachable (no gaps): covered above via 'covered twice'
    return errors


# --------------------------------------------------------------------------
# geometry (span-aware, clean model)
# --------------------------------------------------------------------------

def compute_geometry(plan):
    """Return regions/sizes. Column widths and row heights come from
    non-spanning panels; a spanning panel's region is the union of the cells it
    covers, and it is placed at its natural size inside that region."""
    panels = plan["panels"]
    grid = plan["grid"]
    gutter = float(plan.get("gutter_in", 0.14))
    edge = float(plan.get("edge_in", 0.05))
    target_w = float(plan.get("target_width_in", IEEE_DOUBLE_IN))
    target_h = float(plan.get("target_height_in", 4.5))
    tol = float(plan.get("tolerance", 0.15))

    nrows = len(grid)
    ncol = max(len(r) for r in grid)

    # position -> label
    cell = {}
    for r, row in enumerate(grid):
        for c, lab in enumerate(row):
            cell[(r, c)] = lab

    # collect per-panel metadata
    info = {}
    for lab, spec in panels.items():
        sr, sc = _span(spec)
        info[lab] = {
            "w": float(spec["w"]), "h": float(spec["h"]),
            "sr": sr, "sc": sc, "spanning": (sr, sc) != (1, 1),
        }
    # anchor + occupied cells per panel
    for lab, meta in info.items():
        cells = [k for k, v in cell.items() if v == lab]
        meta["anchor"] = (min(r for r, _ in cells), min(c for _, c in cells))
        meta["cols"] = sorted({c for _, c in cells})
        meta["rows"] = sorted({r for r, _ in cells})

    # column widths / row heights: non-spanning panels define the base; a
    # spanning panel contributes only to columns/rows that have no non-spanning
    # panel (so its size does not feed back into the rows/cols it spans).
    col_w = [0.0] * ncol
    row_h = [0.0] * nrows
    for (r, c), lab in cell.items():
        meta = info[lab]
        if not meta["spanning"]:
            col_w[c] = max(col_w[c], meta["w"])
            row_h[r] = max(row_h[r], meta["h"])
    for lab, meta in info.items():
        if meta["spanning"]:
            for c in meta["cols"]:
                if col_w[c] == 0.0:
                    col_w[c] = max(col_w[c], meta["w"] / meta["sc"])
            for r in meta["rows"]:
                if row_h[r] == 0.0:
                    row_h[r] = max(row_h[r], meta["h"] / meta["sr"])

    total_w = sum(col_w) + (ncol - 1) * gutter + 2 * edge
    total_h = sum(row_h) + (nrows - 1) * gutter + 2 * edge
    scale = target_w / total_w
    scaled_total_h = scale * total_h

    # region per panel (inches, unscaled)
    region = {}
    for lab, meta in info.items():
        rw = sum(col_w[c] for c in meta["cols"]) + (meta["sc"] - 1) * gutter
        rh = sum(row_h[r] for r in meta["rows"]) + (meta["sr"] - 1) * gutter
        region[lab] = (rw, rh)

    return {
        "panels": panels, "info": info, "cell": cell, "region": region,
        "nrows": nrows, "ncol": ncol, "col_w": col_w, "row_h": row_h,
        "gutter": gutter, "edge": edge,
        "target_w": target_w, "target_h": target_h, "tol": tol,
        "total_w": total_w, "total_h": total_h, "scale": scale,
        "scaled_total_h": scaled_total_h,
    }


def placement(g):
    """Scaled geometry of each region + each panel's natural box, in inches."""
    s = g["scale"]
    # cumulative positions in SCALED units (boxes are scaled; positions must be too)
    col_x0 = []
    x = g["edge"] * s
    for c in range(g["ncol"]):
        col_x0.append(x)
        x += (g["col_w"][c] + g["gutter"]) * s
    row_top0 = []
    top = g["scaled_total_h"] - g["edge"] * s
    for r in range(g["nrows"]):
        row_top0.append(top)
        top -= (g["row_h"][r] + g["gutter"]) * s

    out = []
    for lab, meta in g["info"].items():
        r0, c0 = meta["anchor"]
        rw, rh = g["region"][lab]
        rx0 = col_x0[c0]
        ry_top = row_top0[r0]              # top of the anchor row (y-up)
        rx1 = rx0 + rw * s
        ry_bot = ry_top - rh * s           # bottom of the region
        # natural box, bottom-left aligned inside the region
        nw = meta["w"] * s
        nh = meta["h"] * s
        px0, py0 = rx0, ry_bot
        out.append({
            "label": lab,
            "region": (rx0, ry_bot, rx1, ry_top),
            "panel": (px0, py0, px0 + nw, py0 + nh),
            "nat_ratio": meta["w"] / meta["h"],
            "region_ratio": rw / rh,
            "spanning": meta["spanning"],
            "span": (meta["sr"], meta["sc"]),
        })
    return out


# --------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------

def run_checks(g, panels):
    out = []
    tol = g["tol"]

    # 1. width conformance (by construction) and height cap
    out.append(("PASS", f"composed width {g['total_w']:.2f} in -> scaled to target {g['target_w']:.2f} in"))
    if g["scaled_total_h"] <= g["target_h"]:
        out.append(("PASS", f"height {g['scaled_total_h']:.2f} in <= cap {g['target_h']:.2f} in"))
    else:
        out.append(("FAIL", f"height {g['scaled_total_h']:.2f} in > cap {g['target_h']:.2f} in — "
                            "add a row/column, shrink natural sizes, or raise the cap"))

    # 2. fill-stretch: distortion if a panel were forced to fill its region.
    #    Assembly uses natural placement, so this is the "no squeezing" gate.
    for p in panels:
        dev = abs(p["region_ratio"] / p["nat_ratio"] - 1.0) if p["region_ratio"] > 0 else 0.0
        if dev > tol:
            out.append(("FAIL", f"panel '{p['label']}' would be stretched {dev:.0%} to fill its region "
                                f"({p['region_ratio']:.2f}:1 vs natural {p['nat_ratio']:.2f}:1) — "
                                "regroup or resize, never squeeze"))
        else:
            out.append(("PASS", f"panel '{p['label']}' aspect OK (fill-stretch {dev:.0%})"))

    # 3. protrusion: a panel that is larger than its region sticks out ("凸一块")
    for p in panels:
        rw = p["region"][2] - p["region"][0]
        rh = p["region"][3] - p["region"][1]
        nw = p["panel"][2] - p["panel"][0]
        nh = p["panel"][3] - p["panel"][1]
        if nw > rw * 1.02 or nh > rh * 1.02:
            out.append(("FAIL", f"panel '{p['label']}' is {nw:.2f}x{nh:.2f} in but its region is "
                                f"only {rw:.2f}x{rh:.2f} in — it protrudes; shrink it or widen the region"))
        else:
            fill = (nw * nh) / (rw * rh) if rw * rh > 0 else 1.0
            if fill < 0.6:
                out.append(("WARN", f"panel '{p['label']}' fills only {fill:.0%} of its region — "
                                    "large empty area; consider a different grouping"))
            else:
                out.append(("PASS", f"panel '{p['label']}' fits its region (fills {fill:.0%})"))

    # 4. row/column spread of NON-spanning panels (alignment hint; hierarchy is allowed)
    for r in range(g["nrows"]):
        hs = [g["info"][lab]["h"] for (rr, cc), lab in g["cell"].items()
              if rr == r and not g["info"][lab]["spanning"]]
        if len(hs) >= 2:
            spread = (max(hs) - min(hs)) / max(hs)
            if spread > tol:
                out.append(("WARN", f"row {r} mixes heights (spread {spread:.0%} > {tol:.0%}) — "
                                    "shorter panels will leave whitespace (bottom-aligned)"))
            else:
                out.append(("PASS", f"row {r} heights compatible (spread {spread:.0%})"))
    for c in range(g["ncol"]):
        ws = [g["info"][lab]["w"] for (rr, cc), lab in g["cell"].items()
              if cc == c and not g["info"][lab]["spanning"]]
        if len(ws) >= 2:
            spread = (max(ws) - min(ws)) / max(ws)
            if spread > tol:
                out.append(("WARN", f"column {c} mixes widths (spread {spread:.0%} > {tol:.0%})"))
            else:
                out.append(("PASS", f"column {c} widths compatible (spread {spread:.0%})"))

    # 5. coverage of the panel block
    block_area = (g["total_w"] - 2 * g["edge"]) * (g["total_h"] - 2 * g["edge"])
    panel_area = sum(float(g["panels"][lab]["w"]) * float(g["panels"][lab]["h"])
                     for lab in g["panels"])
    coverage = panel_area / block_area if block_area > 0 else 0.0
    if coverage < 0.6:
        out.append(("WARN", f"coverage {coverage:.0%} < 60% — large empty regions"))
    else:
        out.append(("PASS", f"coverage {coverage:.0%} of the panel block"))

    # 6. extreme natural ratios (content-driven strips are legitimate)
    for lab, spec in g["panels"].items():
        ratio = float(spec["w"]) / float(spec["h"])
        if ratio < 0.5 or ratio > 4.0:
            out.append(("WARN", f"panel '{lab}' has extreme ratio {ratio:.2f}:1 — "
                                "verify it is content-driven (e.g. a method strip), not a squeeze"))

    # 7. gutter sanity
    if g["gutter"] < 0.05:
        out.append(("WARN", f"gutter {g['gutter']:.2f} in is very tight"))
    else:
        out.append(("PASS", f"gutter {g['gutter']:.2f} in uniform"))

    return out


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def render_draft(g, panels, out_path, dpi):
    fig = plt.figure(figsize=(g["target_w"], g["scaled_total_h"]), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, g["target_w"])
    ax.set_ylim(0, g["scaled_total_h"])
    ax.axis("off")

    # IEEE column guides
    if abs(g["target_w"] - IEEE_DOUBLE_IN) < 0.05:
        ax.axvline(IEEE_SINGLE_IN, color=GUIDE, ls=":", lw=1.0)
        ax.text(IEEE_SINGLE_IN + 0.03, g["scaled_total_h"] - 0.12, "IEEE single col 3.5 in",
                fontsize=7, color=GUIDE, ha="left", va="top")
        ax.text(g["target_w"] - 0.03, g["scaled_total_h"] - 0.12,
                f"IEEE double col {IEEE_DOUBLE_IN:.2f} in",
                fontsize=7, color=GUIDE, ha="right", va="top")

    # row / column boundaries (dashed) — all in scaled units
    s = g["scale"]
    x = g["edge"]
    for c in range(g["ncol"] - 1):
        x += g["col_w"][c] + g["gutter"] / 2
        ax.axvline(x * s, color=GUIDE, ls="--", lw=0.7)
        x += g["gutter"] / 2
    top = g["scaled_total_h"] - g["edge"] * s
    for r in range(g["nrows"] - 1):
        top -= g["row_h"][r] * s + g["gutter"] * s / 2
        ax.axhline(top, color=GUIDE, ls="--", lw=0.7)
        top -= g["gutter"] * s / 2

    # regions + panels
    for p in panels:
        rx0, ry0, rx1, ry1 = p["region"]
        cell = FancyBboxPatch((rx0, ry0), rx1 - rx0, ry1 - ry0,
                              boxstyle="square,pad=0", linewidth=0.8,
                              edgecolor=CELL_EDGE, facecolor=CELL_FACE)
        ax.add_patch(cell)
        px0, py0, px1, py1 = p["panel"]
        panel = FancyBboxPatch((px0, py0), px1 - px0, py1 - py0,
                               boxstyle="square,pad=0", linewidth=1.4,
                               edgecolor=PANEL_EDGE, facecolor="white")
        ax.add_patch(panel)
        span_txt = f"  [{p['span'][0]}x{p['span'][1]}]" if p["spanning"] else ""
        ax.text(rx0 + 0.03, ry1 - 0.03, p["label"] + span_txt,
                fontsize=10, fontweight="bold", color=TEXT, ha="left", va="top")

    fig.savefig(out_path, dpi=dpi)
    plt.close(fig)
    return out_path


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("plan", help="path to the layout plan JSON")
    ap.add_argument("--out", default="draft_layout.png", help="output PNG path")
    ap.add_argument("--dpi", type=int, default=150, help="draft resolution")
    ap.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = ap.parse_args(argv)

    try:
        plan = load_plan(args.plan)
    except OSError as exc:
        sys.exit(f"cannot read plan {args.plan}: {exc}")
    except json.JSONDecodeError as exc:
        sys.exit(f"plan {args.plan} is not valid JSON: {exc}")

    errors = validate(plan)
    if errors:
        for e in errors:
            print(f"ERROR  {e}")
        sys.exit(2)

    g = compute_geometry(plan)
    panels = placement(g)
    checks = run_checks(g, panels)

    n_fail = sum(1 for st, _ in checks if st == "FAIL")
    n_warn = sum(1 for st, _ in checks if st == "WARN")

    if args.json:
        report = {
            "title": plan.get("title", ""),
            "target_width_in": g["target_w"],
            "composed_height_in": round(g["scaled_total_h"], 3),
            "scale": round(g["scale"], 4),
            "failures": n_fail, "warnings": n_warn,
            "checks": [{"status": st, "message": msg} for st, msg in checks],
            "panels": [
                {"label": p["label"], "span": list(p["span"]),
                 "natural_in": [round(p["panel"][2] - p["panel"][0], 3),
                                round(p["panel"][3] - p["panel"][1], 3)],
                 "region_in": [round(p["region"][2] - p["region"][0], 3),
                               round(p["region"][3] - p["region"][1], 3)]}
                for p in panels],
        }
        print(json.dumps(report, indent=2))
    else:
        title = plan.get("title", "layout draft")
        print("=" * 72)
        print(f"{title}  |  target width {g['target_w']:.2f} in, "
              f"composed height {g['scaled_total_h']:.2f} in")
        print("=" * 72)
        for st, msg in checks:
            print(f"{st:<5} {msg}")
        print("-" * 72)
        print(f"draft written to {render_draft(g, panels, args.out, args.dpi)}")
        print(f"RESULT  {n_fail} FAIL, {n_warn} WARN"
              + ("  ->  do not assemble; revise the grid" if n_fail else "  ->  ready for user confirmation"))

    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
