#!/usr/bin/env python3
"""
check_overlap.py — geometric no-occlusion checker for matplotlib figures.

Deterministic first layer of the "no overlap" gate (the final layer is the
mandatory glm-vision visual double-check described in multi-panel-workflow.md).
It paints the figure once, measures every text / legend bounding box through
the matplotlib renderer, and flags:

  FAIL   two text boxes overlapping (annotations, title, axis labels, ticks)
  FAIL   a legend frame overlapping any text box
  WARN   a legend sitting inside the axes data area (may be covering data)
  WARN   any text or legend box clipped beyond the figure canvas

The check is deliberately conservative: it *proves* that text/legend boxes do
not collide, which is the mechanical part of "严格无任何遮挡". Whether a legend
visually covers *data* marks is a semantic judgement — that is decided by the
vision double-check, not here.

Primary usage is as an import inside the plotting session (copy it next to your
plotting script, or add the skill's panels/ dir to sys.path):

    from check_overlap import check_no_overlap
    report = check_no_overlap(fig, label="panel a", map_path="panel_a_overlaps.png")
    fails  = [m for st, m in report if st == "FAIL"]   # must be empty before next step
    warns  = [m for st, m in report if st == "WARN"]   # every WARN needs a vision pass

The CLI only runs a headless self-check demo that constructs a figure with
deliberate overlaps, checks it, and writes an overlap-map PNG:

    python panels/check_overlap.py --demo

Exit code is non-zero whenever any FAIL is present.
"""

import sys

try:
    import matplotlib
    from matplotlib import cbook
    from matplotlib.patches import Rectangle
    from matplotlib.transforms import Bbox
except ImportError as exc:  # pragma: no cover
    sys.exit(f"check_overlap.py needs matplotlib. ({exc})")

# No backend is forced here: in a normal plotting session the user already
# holds a pyplot backend and overriding it would be wrong. Tests and the CLI
# opt into Agg themselves (headless) before importing pyplot.
if "matplotlib.pyplot" not in sys.modules:
    try:
        matplotlib.use("Agg")
    except Exception:  # pragma: no cover
        pass


def use_agg():
    """Pin the Agg backend if pyplot is not imported yet (headless safety)."""
    if "matplotlib.pyplot" not in sys.modules:
        matplotlib.use("Agg")


# --------------------------------------------------------------------------
# collection
# --------------------------------------------------------------------------

def _extent(artist, renderer):
    try:
        return artist.get_window_extent(renderer)
    except Exception:  # pragma: no cover - a text without a renderer mock
        return None


def _short(label, limit=24):
    label = (label or "").replace("\n", " ")
    return label if len(label) <= limit else label[: limit - 1] + "…"


def _box(x0, y0, x1, y1):
    return Bbox([[x0, y0], [x1, y1]])


def _tick_is_painted(tl_bb, axbb, horizontal):
    """A tick label is painted only if it sits on its own axis. Phantom labels
    for hidden ticks map to window coordinates far off the axis (matplotlib
    keeps them in the label list), so require the label to overlap the axis
    window's extent along its own dimension."""
    if horizontal:
        return tl_bb.x0 < axbb.x1 and tl_bb.x1 > axbb.x0
    return tl_bb.y0 < axbb.y1 and tl_bb.y1 > axbb.y0


def _axis_label_box(label_obj, axbb, renderer, horizontal, dpi, pad,
                    band_edge):
    """Deterministic box for an axis label.

    `Text.get_window_extent` disagrees with the rasterized output for axis
    labels on some matplotlib versions (y offset off by ~1/4 in), so the box is
    computed from the *tick-label band edge* + labelpad + the renderer's text
    metrics instead — matplotlib lays the axis label beyond the tick labels.
    `horizontal` selects the x-label (below the x ticks) vs y-label (rotated,
    left of the y ticks); `band_edge` is the min tick-label y0 (x) or x0 (y);
    `pad` is the axis's ``labelpad`` in points.
    """
    s = label_obj.get_text()
    fp = label_obj.get_fontproperties()
    # The Agg renderer requires an explicit ismath flag; reuse matplotlib's own
    # mathtext detector so \$ / math labels measure correctly.
    w, h, d = renderer.get_text_width_height_descent(
        s, fp, ismath=bool(cbook.is_math_text(s)))
    pad_disp = float(pad) * dpi / 72.0  # points -> px
    if horizontal:
        cx = axbb.x0 + axbb.width / 2.0
        ytop = band_edge - pad_disp
        return _box(cx - w / 2.0, ytop - h, cx + w / 2.0, ytop)
    cy = axbb.y0 + axbb.height / 2.0
    xright = band_edge - pad_disp
    return _box(xright - h, cy - w / 2.0, xright, cy + w / 2.0)


def collect(fig):
    """Draw the figure once and return everything the checks need.

    Returns a dict with:
      texts      list of {"name", "kind", "bbox"}   (every text artist)
      legends    list of {"name", "bbox"}           (legend frames; one blocker each)
      axes_boxes list of Bbox                       (per-axes plot areas)
      canvas_w/h pixel size of the figure canvas
    """
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    dpi = fig.get_dpi()

    texts, legends = [], []
    for tx in fig.texts:
        bb = _extent(tx, renderer)
        if bb is not None:
            texts.append({"name": f"fig-text “{_short(tx.get_text())}”",
                          "kind": "figure", "bbox": bb})

    axes_boxes = []
    for i, ax in enumerate(fig.axes, 1):
        ab = _extent(ax, renderer)
        if ab is not None:
            axes_boxes.append(ab)

        for tx in ax.texts:
            bb = _extent(tx, renderer)
            if bb is not None:
                texts.append({"name": f"ax{i} text “{_short(tx.get_text())}”",
                              "kind": "annotation", "bbox": bb})

        title = getattr(ax, "title", None)
        if title is not None:
            bb = _extent(title, renderer)
            if bb is not None:
                texts.append({"name": f"ax{i} title", "kind": "axis",
                              "bbox": bb})

        # Measure painted tick labels first: the axis label sits beyond the
        # *tick-label band* (not the spine), and ticks also feed the phantom
        # filter. Order matters — collect painted tick boxes, then the label.
        def painted_ticks(labels, horizontal):
            boxes = []
            for tl in labels:
                bb = _extent(tl, renderer)
                if bb is None or (ab is not None and
                                  not _tick_is_painted(bb, ab, horizontal)):
                    continue
                boxes.append(bb)
            return boxes

        xticks = painted_ticks(ax.get_xticklabels(), True)
        yticks = painted_ticks(ax.get_yticklabels(), False)
        for n, bb in enumerate(xticks):
            texts.append({"name": f"ax{i} x-tick{n}", "kind": "axis", "bbox": bb})
        for n, bb in enumerate(yticks):
            texts.append({"name": f"ax{i} y-tick{n}", "kind": "axis", "bbox": bb})

        if ab is not None:
            xl = ax.xaxis.get_label()
            xbottom = (min(bb.y0 for bb in xticks) if xticks else ab.y0)
            texts.append({"name": f"ax{i} x-label", "kind": "axis",
                          "bbox": _axis_label_box(xl, ab, renderer, True, dpi,
                                                  ax.xaxis.labelpad,
                                                  band_edge=xbottom)})
            yl = ax.yaxis.get_label()
            yleft = (min(bb.x0 for bb in yticks) if yticks else ab.x0)
            texts.append({"name": f"ax{i} y-label", "kind": "axis",
                          "bbox": _axis_label_box(yl, ab, renderer, False, dpi,
                                                  ax.yaxis.labelpad,
                                                  band_edge=yleft)})

        leg = ax.get_legend()
        if leg is not None:
            lbf = _extent(leg, renderer)
            if lbf is not None:
                legends.append({"name": f"ax{i} legend", "bbox": lbf})

    return {
        "texts": texts,
        "legends": legends,
        "axes_boxes": axes_boxes,
        "canvas_w": float(fig.canvas.get_width_height()[0]),
        "canvas_h": float(fig.canvas.get_width_height()[1]),
    }


# --------------------------------------------------------------------------
# checks — each returns a list of records dicts; flattened later
# --------------------------------------------------------------------------

def _overlap(a, b):
    try:
        return a.overlaps(b)
    except Exception:  # pragma: no cover
        return False


def _check_text_text(texts):
    out = []
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            a, b = texts[i], texts[j]
            if _overlap(a["bbox"], b["bbox"]):
                out.append({
                    "status": "FAIL",
                    "msg": (f"text “{a['name']}” overlaps “{b['name']}” "
                            f"at ({a['bbox'].x0:.0f},{a['bbox'].y0:.0f}).."
                            f"({a['bbox'].x1:.0f},{a['bbox'].y1:.0f})"),
                    "nameA": a["name"], "nameB": b["name"],
                    "bboxA": a["bbox"], "bboxB": b["bbox"],
                })
    return out


def _check_legend_text(legends, texts):
    out = []
    for lg in legends:
        for tx in texts:
            if _overlap(lg["bbox"], tx["bbox"]):
                out.append({
                    "status": "FAIL",
                    "msg": f"legend “{lg['name']}” overlaps text “{tx['name']}”",
                    "nameA": lg["name"], "nameB": tx["name"],
                    "bboxA": lg["bbox"], "bboxB": tx["bbox"],
                })
    return out


def _check_legend_inside(legends, axes_boxes):
    """A legend whose frame sits mostly inside the axes plot area may be covering
    data marks. Not decidable geometrically -> WARN and let the vision check rule."""
    out = []
    for lg in legends:
        lg_area = lg["bbox"].width * lg["bbox"].height
        for ab in axes_boxes:
            inter = lg["bbox"].intersection(lg["bbox"], ab)
            if inter is None:
                continue
            share = (inter.width * inter.height) / lg_area if lg_area > 0 else 0.0
            if share > 0.25:
                out.append({
                    "status": "WARN",
                    "msg": (f"legend “{lg['name']}” sits inside the axes plot area "
                            f"(overlaps {share:.0%} of its frame) — move it or confirm "
                            "via the vision double-check that no data is covered"),
                    "nameA": lg["name"],
                    "bboxA": lg["bbox"],
                })
                break
    return out


def _check_clip(boxes, w, h):
    out = []
    eps = 1.0  # px
    for b in boxes:
        bb = b["bbox"]
        if bb.x0 < -eps or bb.y0 < -eps or bb.x1 > w + eps or bb.y1 > h + eps:
            out.append({
                "status": "WARN",
                "msg": (f"“{b['name']}” is clipped at the figure edge "
                        f"(bbox {bb.x0:.0f},{bb.y0:.0f} .. {bb.x1:.0f},{bb.y1:.0f}; "
                        f"canvas {w:.0f}x{h:.0f}px)"),
                "nameA": b["name"],
                "bboxA": bb,
            })
    return out


# --------------------------------------------------------------------------
# public API
# --------------------------------------------------------------------------

def check_no_overlap(fig, label="figure", map_path=None):
    """Run the geometric no-overlap checks on a rendered figure.

    Returns a list of ``(status, message)`` tuples::
        PASSLESS / WARN / FAIL. FAIL means a hard collision (text-text or
        legend-text); WARN means "verify with the vision double-check".

    ``map_path`` optionally writes an annotated PNG drawing every element box and
    highlighting every FAIL pair, which speeds up fixing and gives the vision
    tool a labelled reference.
    """
    data = collect(fig)
    records = []
    records += _check_text_text(data["texts"])
    records += _check_legend_text(data["legends"], data["texts"])
    records += _check_legend_inside(data["legends"], data["axes_boxes"])
    records += _check_clip(data["texts"] + data["legends"],
                           data["canvas_w"], data["canvas_h"])
    if map_path:
        render_overlap_map(data, records, label, map_path)
    return [(r["status"], r["msg"]) for r in records]


def render_overlap_map(data, records, title, out_path, dpi=100):
    """Draw every measured box; highlight every box that participates in a FAIL."""
    from matplotlib import pyplot as plt
    w, h = data["canvas_w"], data["canvas_h"]
    mfig = plt.figure(figsize=(w / dpi, h / dpi), dpi=dpi)
    ax = mfig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")

    for ab in data["axes_boxes"]:
        ax.add_patch(Rectangle((ab.x0, ab.y0), ab.width, ab.height,
                               fill=False, edgecolor="#999999",
                               linestyle="--", linewidth=0.6))

    fail_names = set()
    for r in records:
        if r["status"] == "FAIL":
            fail_names.add(r["nameA"])
            fail_names.add(r.get("nameB") or r["nameA"])

    def draw(name, bb, is_fail):
        color = "#c62828" if is_fail else "#1f77b4"
        ax.add_patch(Rectangle((bb.x0, bb.y0), bb.width, bb.height,
                               fill=False, edgecolor=color, linewidth=1.5))
        ax.text(bb.x0, bb.y1 + 1.5, name, fontsize=6, color=color,
                ha="left", va="bottom")

    for t in data["texts"]:
        draw(t["name"], t["bbox"], t["name"] in fail_names)
    for lg in data["legends"]:
        draw(lg["name"], lg["bbox"], lg["name"] in fail_names)

    ax.set_title(f"overlap map — {title}", fontsize=8, loc="left",
                 color="#333333")
    mfig.savefig(out_path, dpi=dpi)
    plt.close(mfig)
    return out_path


# --------------------------------------------------------------------------
# headless self-check demo + CLI
# --------------------------------------------------------------------------

def demo():
    """Build a figure with deliberate overlaps, run the checks."""
    use_agg()
    from matplotlib import pyplot as plt
    fig, ax = plt.subplots(figsize=(3.6, 2.4), dpi=110)
    x = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    ax.plot(x, [v * v for v in x], marker="o", label="quadratic")
    ax.plot(x, [2.0 * v + 0.5 for v in x], label="linear")
    ax.set_xlabel("time (s)")
    ax.set_ylabel("error")
    ax.legend(loc="center")                      # parked on top of the data
    ax.plot([1.25, 1.25], [1.0, 6.0], ls="--", color="green")  # a line under the legend
    # two texts pinned to the same spot -> guaranteed FAIL
    fig.text(0.35, 0.52, "annotation A", fontsize=12)
    fig.text(0.355, 0.52, "annotation B", fontsize=12)
    checks = check_no_overlap(fig, label="demo", map_path="demo_overlap_map.png")
    return checks


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--demo", action="store_true",
                    help="build a demo figure with deliberate overlaps, run the checks, "
                         "save demo_overlap_map.png")
    args = ap.parse_args(argv)
    if not args.demo:
        ap.print_help()
        return 0
    checks = demo()
    fails = sum(1 for st, _ in checks if st == "FAIL")
    warns = sum(1 for st, _ in checks if st == "WARN")
    for st, msg in checks:
        print(f"{st:<5} {msg}")
    print(f"overlap map written to demo_overlap_map.png")
    print(f"RESULT  {fails} FAIL, {warns} WARN")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())