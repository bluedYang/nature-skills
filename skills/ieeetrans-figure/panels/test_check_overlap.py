#!/usr/bin/env python3
"""Regression tests for the geometric no-overlap checker (check_overlap.py).

Builds small figures through the Agg backend and asserts the invariants the
"严格无任何遮挡" gate relies on:
  - a clean figure has 0 FAIL and 0 WARN;
  - a legend parked on the data raises the inside-axes WARN;
  - two co-located texts raise a FAIL;
  - a legend frame touching an annotation raises a FAIL;
  - a text anchored outside the canvas raises a clip WARN.

Run:  python panels/test_check_overlap.py        (or `python -m pytest`)
"""

import importlib.util
import pathlib
import sys

import matplotlib

matplotlib.use("Agg")                # headless; before pyplot import
from matplotlib import pyplot as plt

HERE = pathlib.Path(__file__).resolve().parent


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


co = load_module("check_overlap", HERE / "check_overlap.py")

PASS = 0


def check(cond, msg):
    global PASS
    if not cond:
        sys.exit(f"FAIL: {msg}")
    PASS += 1
    print(f"ok  {msg}")


# ---------------------------------------------------------------------------
# shared figure builders
# ---------------------------------------------------------------------------

def base_fig():
    """A quiet two-line figure: legend above the axes, explicit roomy margins
    so that nothing touches the canvas edge (a genuinely clean figure)."""
    fig, ax = plt.subplots(figsize=(4.2, 2.8), dpi=100)
    fig.subplots_adjust(left=0.15, right=0.97, top=0.78, bottom=0.17)
    x = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    ax.plot(x, [v * v for v in x], marker="o", label="quadratic")
    ax.plot(x, [2.0 * v + 0.5 for v in x], label="linear")
    ax.set_xlabel("time (s)")
    ax.set_ylabel("error")
    ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.02))  # above the axes
    return fig, ax


def any_status(report, status, needle, what):
    return [m for st, m in report if st == status and needle in m], what


# ---------------------------------------------------------------------------
# 1. clean figure -> 0 FAIL, 0 WARN
# ---------------------------------------------------------------------------
fig, _ = base_fig()
report = co.check_no_overlap(fig, label="clean")
fails = [m for st, m in report if st == "FAIL"]
warns = [m for st, m in report if st == "WARN"]
check(not fails, f"clean figure has no FAIL ({fails})")
check(not warns, f"clean figure has no WARN ({warns})")
plt.close(fig)

# ---------------------------------------------------------------------------
# 2. legend parked on the data -> inside-axes WARN
# ---------------------------------------------------------------------------
fig, _ = base_fig()
fig.axes[0].legend(loc="center")                 # dead centre, on top of the lines
report = co.check_no_overlap(fig, label="legend-on-data")
inner, what = any_status(report, "WARN", "sits inside", "legend-inside WARN")
check(bool(inner), f"{what} present for loc='center' legend ({report})")
plt.close(fig)

# ---------------------------------------------------------------------------
# 3. two co-located texts -> FAIL
# ---------------------------------------------------------------------------
fig, _ = base_fig()
fig.text(0.35, 0.52, "annotation A", fontsize=12)
fig.text(0.355, 0.52, "annotation B", fontsize=12)
report = co.check_no_overlap(fig, label="colliding-texts")
coll, what = any_status(report, "FAIL", "overlaps", "text-text FAIL")
check(bool(coll), f"{what} present for co-located texts ({report})")
plt.close(fig)

# ---------------------------------------------------------------------------
# 4. legend frame touching an annotation drawn beneath it -> FAIL
# ---------------------------------------------------------------------------
fig, ax = base_fig()
fig.axes[0].legend(loc="center")                   # legend centred in the axes...
ax.text(0.5, 0.5, "central label", fontsize=12,
        transform=ax.transAxes)                    # ...right where the annotation is
report = co.check_no_overlap(fig, label="legend-vs-annotation")
coll, what = any_status(report, "FAIL", "legend", "legend-text FAIL")
check(bool(coll), f"{what} present for legend touching an annotation ({report})")
plt.close(fig)

# ---------------------------------------------------------------------------
# 5. text anchored outside the canvas -> clip WARN
# ---------------------------------------------------------------------------
fig, _ = base_fig()
fig.text(-0.03, -0.03, "peeking out", fontsize=10)
report = co.check_no_overlap(fig, label="clipped")
clip, what = any_status(report, "WARN", "clipped", "clip WARN")
check(bool(clip), f"{what} present for an off-canvas text ({report})")
plt.close(fig)

# ---------------------------------------------------------------------------
# 6. figure with no axes / no text -> nothing to report
# ---------------------------------------------------------------------------
fig = plt.figure(figsize=(2.0, 1.0), dpi=80)
report = co.check_no_overlap(fig, label="empty")
check(not any(st == "FAIL" for st, _ in report),
      "axes-less figure produces no FAIL")
plt.close(fig)

print(f"\nAll {PASS} checks passed.")