#!/usr/bin/env python3
"""Regression tests for layout-draft.py.

These tests exercise the geometry engine (compute_geometry / placement /
run_checks / validate) and assert the invariants that the panel-first workflow
relies on. They cover the two historical placement bugs (region boxes shifted
down, and positions not scaled) plus span handling and the protrusion check.

Run:  python panels/test_layout_draft.py        (or `python -m pytest`)
No matplotlib render is required; the engine is pure arithmetic.
"""

import importlib.util
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ld = load_module("layout_draft", HERE / "layout-draft.py")

PASS = 0


def check(cond, msg):
    global PASS
    if not cond:
        sys.exit(f"FAIL: {msg}")
    PASS += 1
    print(f"ok  {msg}")


def boxes_inside(g, boxes):
    """Every panel box must lie inside the figure canvas."""
    W, H = g["target_w"], g["scaled_total_h"]
    eps = 1e-6
    for p in boxes:
        x0, y0, x1, y1 = p["panel"]
        if not (-eps <= x0 and x1 <= W + eps and -eps <= y0 and y1 <= H + eps):
            return False, f"panel {p['label']} box ({x0:.3f}..{x1:.3f}, {y0:.3f}..{y1:.3f}) outside {W:.2f}x{H:.2f}"
    return True, ""


def boxes_disjoint(boxes):
    """No two panel boxes may overlap."""
    items = sorted(boxes, key=lambda p: p["label"])
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            if (a["panel"][0] < b["panel"][2] and a["panel"][2] > b["panel"][0] and
                    a["panel"][1] < b["panel"][3] and a["panel"][3] > b["panel"][1]):
                return False, f"panels {a['label']} and {b['label']} overlap"
    return True, ""


def no_fail(checks):
    return all(st != "FAIL" for st, _ in checks), [m for st, m in checks if st == "FAIL"]


# ---------------------------------------------------------------------------
# 1. simple non-spanning example (the bundled example-plan.json)
# ---------------------------------------------------------------------------
plan = json.loads((HERE / "example-plan.json").read_text())
g = ld.compute_geometry(plan)
boxes = ld.placement(g)
checks = ld.run_checks(g, boxes)
ok, fails = no_fail(checks)
check(ok, f"example-plan has 0 FAIL ({len(fails)} fail)")
ok, m = boxes_inside(g, boxes)
check(ok, "example-plan boxes inside canvas" + ("" if ok else " — " + m))
ok, m = boxes_disjoint(boxes)
check(ok, "example-plan boxes disjoint" + ("" if ok else " — " + m))
check(len(boxes) == len(plan["panels"]), "example-plan has one box per panel")

# ---------------------------------------------------------------------------
# 2. asymmetric span layout (method strip + hero + spanning panel)
# ---------------------------------------------------------------------------
plan2 = {
    "title": "span regression",
    "target_width_in": 7.16, "target_height_in": 5.0,
    "gutter_in": 0.14, "edge_in": 0.05, "tolerance": 0.15,
    "panels": {
        "a": {"w": 1.00, "h": 4.64, "span": [2, 1]},
        "b": {"w": 2.00, "h": 2.50},
        "c": {"w": 1.875, "h": 2.50},
        "d": {"w": 1.875, "h": 2.50},
        "e": {"w": 2.00, "h": 2.00},
        "f": {"w": 3.89, "h": 2.00, "span": [1, 2]},
    },
    "grid": [["a", "b", "c", "d"], ["a", "e", "f", "f"]],
}
g2 = ld.compute_geometry(plan2)
boxes2 = ld.placement(g2)
checks2 = ld.run_checks(g2, boxes2)
ok, fails = no_fail(checks2)
check(ok, "span layout has 0 FAIL" + ("" if ok else f" ({fails})"))
ok, m = boxes_inside(g2, boxes2)
check(ok, "span layout boxes inside canvas" + ("" if ok else " — " + m))
ok, m = boxes_disjoint(boxes2)
check(ok, "span layout boxes disjoint" + ("" if ok else " — " + m))
# spanning panel a must span the full height of the body rows
a = next(p for p in boxes2 if p["label"] == "a")
check(abs(a["panel"][3] - a["panel"][1] - 4.64 * g2["scale"]) < 1e-6,
      "spanning panel 'a' keeps its natural height after scaling")
# no overlap specifically between a (left strip) and b (hero) or e
check(a["panel"][2] <= next(p for p in boxes2 if p["label"] == "b")["panel"][0] + 1e-9,
      "strip 'a' does not overlap hero 'b'")

# ---------------------------------------------------------------------------
# 3. protrusion check: a panel larger than its region must FAIL
# ---------------------------------------------------------------------------
plan3 = dict(plan2)
plan3["panels"] = dict(plan2["panels"])
plan3["panels"]["f"] = {"w": 5.0, "h": 2.0, "span": [1, 2]}  # wider than cols 2+3
g3 = ld.compute_geometry(plan3)
checks3 = ld.run_checks(g3, ld.placement(g3))
check(any(st == "FAIL" and "protrudes" in m for st, m in checks3),
      "protrusion check catches a panel wider than its region")

# ---------------------------------------------------------------------------
# 4. height cap: a too-tall layout must FAIL
# ---------------------------------------------------------------------------
plan4 = dict(plan2)
plan4["target_height_in"] = 1.0
g4 = ld.compute_geometry(plan4)
checks4 = ld.run_checks(g4, ld.placement(g4))
check(any(st == "FAIL" and "cap" in m for st, m in checks4),
      "height-cap check FAILs an over-tall layout")

# ---------------------------------------------------------------------------
# 5. plan validation errors
# ---------------------------------------------------------------------------
bad = dict(plan2)
bad["panels"] = dict(plan2["panels"])
del bad["panels"]["b"]
errs = ld.validate(bad)
check(any("never placed" in e or "no such key" in e for e in errs),
      "validate catches a panel missing from 'panels' but referenced in 'grid'")
bad2 = dict(plan2)
bad2["panels"] = dict(plan2["panels"])
bad2["grid"] = [["a", "b", "c", "d"], ["a", "f", "e", "f"]]  # f appears twice, not adjacent
errs2 = ld.validate(bad2)
check(any("rectangle" in e or "needs" in e or "appears" in e for e in errs2),
      "validate catches a non-contiguous span placement")

# ---------------------------------------------------------------------------
# 6. scale-invariance: rendering positions must be exactly scaled geometry
# ---------------------------------------------------------------------------
# A scale far from 1 must still keep every box inside the canvas (this is the
# regression that previously let panels drift out of the figure when scale != 1).
for tf in (0.8, 1.4):
    plan5 = dict(plan2)
    plan5["target_width_in"] = round(7.16 * tf, 3)
    g5 = ld.compute_geometry(plan5)
    ok, m = boxes_inside(g5, ld.placement(g5))
    check(ok, f"scale-invariance at target {plan5['target_width_in']:.2f} in"
              + ("" if ok else " — " + m))

print(f"\nAll {PASS} checks passed.")
