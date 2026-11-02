#!/usr/bin/env python
"""
k_scatter.py

Produce the guide-style scatter plots for Smoke Obscuration (as in the guide) and
for the extinction coefficient k, using the guide's own plotting and statistics
code (fdsplotlib.scatplot of the pinned fds commit) with a separate Scatterplot_Dir,
so that the guide's validation_statistics.tex is not involved. This is the mechanism
proposed in drafts/discussion_k_scatter.md.

Input : output/points_<variant>.csv (written by k_from_transmission.py),
        work/snapshots/<variant>/fds/Utilities/Python/ (fdsplotlib + inputs)
Output: output/figures/<variant>/Scatterplots/FDS_Smoke_Obscuration.{pdf,png}
        output/figures/<variant>/Scatterplots/FDS_Smoke_Extinction_Coefficient.{pdf,png}
        output/figures/scatter_<variant>.png   (both side by side)
        output/k_scatter_stats_<variant>.csv   (statistics written by scatplot)

Usage: python k_scatter.py [--variant 6.11.1|master|all] [--sigma-e-k 19]
"""

import argparse
import csv
import json
import os
import shutil
import sys
from collections import OrderedDict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
K_TITLE = "Smoke Extinction Coefficient"
O_TITLE = "Smoke Obscuration"


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_saved_data(points, quantity, col_e, col_m, group_style):
    """Assemble the saved_data tuple that fdsplotlib.scatplot expects, one entry per
    dataplot row, with the metric values of its columns."""
    rows = OrderedDict()
    for p in points:
        if p["quantity"] != O_TITLE or p["in_guide_selection"] != "1":
            continue
        ke, km = float(p[col_e]), float(p[col_m])
        rows.setdefault(int(p["dataplot_row"]), {"ds": p["dataset"], "test": p["test"], "E": [], "M": []})
        rows[int(p["dataplot_row"])]["E"].append(ke)
        rows[int(p["dataplot_row"])]["M"].append(km)
    S = {k: [] for k in ("Quantity", "Group_Style", "Fill_Color", "Group_Key_Label", "Measured", "Predicted", "Dataname",
                         "Plot_Filename", "Dep_Title", "Error_Tolerance", "Metric_Type", "Measured_Quantity",
                         "Predicted_Quantity", "csv_rownum")}
    drange = []
    for rownum, r in rows.items():
        style, fill = group_style[r["ds"]]
        S["Quantity"].append(quantity)
        S["Group_Style"].append(style)
        S["Fill_Color"].append(fill)
        S["Group_Key_Label"].append(r["ds"])
        S["Measured"].append(np.array(r["E"], float))
        S["Predicted"].append(np.array(r["M"], float))
        S["Dataname"].append(r["ds"])
        S["Plot_Filename"].append("")
        S["Dep_Title"].append("")
        S["Error_Tolerance"].append(0.0)
        S["Metric_Type"].append("")
        S["Measured_Quantity"].append(np.array([""], dtype=object))
        S["Predicted_Quantity"].append(np.array([""], dtype=object))
        S["csv_rownum"].append(rownum)
        drange.append(rownum)
    return tuple(S[k] for k in ("Quantity", "Group_Style", "Fill_Color", "Group_Key_Label", "Measured", "Predicted",
                                "Dataname", "Plot_Filename", "Dep_Title", "Error_Tolerance", "Metric_Type",
                                "Measured_Quantity", "Predicted_Quantity", "csv_rownum")), drange


def run_variant(variant, sigma_e_k, workdir, outdir):
    snap_py = os.path.join(workdir, "snapshots", variant, "fds", "Utilities", "Python")
    points = read_csv(os.path.join(outdir, "points_%s.csv" % variant))

    # marker styles per data set and the guide's obscuration scatter definition
    group_style = {}
    for r in read_csv(os.path.join(snap_py, "FDS_validation_dataplot_inputs.csv")):
        if r["Quantity"] == O_TITLE and r["Group_Key_Label"] not in group_style:
            group_style[r["Group_Key_Label"]] = (r["Group_Style"], r["Fill_Color"])
    scat_rows = read_csv(os.path.join(snap_py, "FDS_validation_scatterplot_inputs.csv"))
    o_row = dict(next(r for r in scat_rows if r["Scatter_Plot_Title"] == O_TITLE))

    figdir = os.path.join(outdir, "figures", variant) + os.sep
    scatdir = os.path.join(figdir, "Scatterplots") + os.sep
    if os.path.isdir(figdir):
        shutil.rmtree(figdir)
    os.makedirs(scatdir)

    o_row["Plot_Filename"] = "Scatterplots/FDS_Smoke_Obscuration"
    k_row = dict(o_row)
    k_row.update({"Scatter_Plot_Title": K_TITLE,
                  "Ind_Title": "Measured Extinction Coefficient (1/m)",
                  "Dep_Title": "Predicted Extinction Coefficient (1/m)",
                  "Plot_Min": "0.001", "Plot_Max": "100", "Sigma_E": str(sigma_e_k), "Weight_Data": "no",
                  "Plot_Type": "loglog", "Plot_Filename": "Scatterplots/FDS_Smoke_Extinction_Coefficient"})
    inputs = os.path.join(figdir, "scatterplot_inputs_k.csv")
    with open(inputs, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(o_row.keys()))
        w.writeheader()
        w.writerows([o_row, k_row])

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.figure
    # also save a PNG next to every PDF the guide code writes
    _savefig = matplotlib.figure.Figure.savefig

    def savefig_both(self, fname, *a, **kw):
        _savefig(self, fname, *a, **kw)
        if str(fname).lower().endswith(".pdf"):
            _savefig(self, str(fname)[:-4] + ".png", dpi=200)
    matplotlib.figure.Figure.savefig = savefig_both

    sys.path.insert(0, snap_py)
    import fdsplotlib
    sd_o, dr_o = build_saved_data(points, O_TITLE, "guide_metric_exp", "guide_metric_model", group_style)
    sd_k, dr_k = build_saved_data(points, K_TITLE, "k_exp", "k_mod", group_style)
    saved = tuple(list(a) + list(b) for a, b in zip(sd_o, sd_k))
    fdsplotlib.scatplot(saved, dr_o + dr_k, Manuals_Dir=figdir, Scatterplot_Inputs_File=inputs,
                        Stats_Output="Validation", Scatterplot_Dir=scatdir, verbose=False)
    # NOTE: scatplot reads Sigma_E from the inputs file only for Stats_Output == "Validation";
    # any other name silently falls back to sigma_E = u/sqrt(2). A separate Scatterplot_Dir
    # keeps the guide's own validation_statistics.tex untouched.
    matplotlib.figure.Figure.savefig = _savefig

    stats = read_csv(os.path.join(scatdir, "validation_scatterplot_output.csv"))
    for r in stats:
        r["variant"] = variant
    with open(os.path.join(outdir, "k_scatter_stats_%s.csv" % variant), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["variant"] + [k for k in stats[0].keys() if k != "variant"])
        w.writeheader()
        w.writerows(stats)

    # side-by-side PNG
    from PIL import Image
    ims = [Image.open(os.path.join(scatdir, n + ".png")) for n in ("FDS_Smoke_Obscuration", "FDS_Smoke_Extinction_Coefficient")]
    h = max(i.height for i in ims)
    canvas = Image.new("RGB", (sum(i.width for i in ims), h), "white")
    x = 0
    for i in ims:
        canvas.paste(i, (x, 0))
        x += i.width
    combined = os.path.join(outdir, "figures", "scatter_%s.png" % variant)
    canvas.save(combined)
    print("%s: %s" % (variant, combined))
    for r in stats:
        print("   %-28s n=%s sigma_E=%s sigma_M=%s bias=%s" % (r["Quantity"], r["Number of Points"], r["Sigma_Experiment"], r["Sigma_Model"], r["Bias"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variant", default="all", choices=["all", "6.11.1", "master"])
    ap.add_argument("--sigma-e-k", type=float, default=19.0, help="sigma_E in percent for the k scatter")
    ap.add_argument("--workdir", default=os.path.join(HERE, "work"))
    ap.add_argument("--outdir", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    variants = ["6.11.1", "master"] if args.variant == "all" else [args.variant]
    for v in variants:
        run_variant(v, args.sigma_e_k, args.workdir, args.outdir)


if __name__ == "__main__":
    main()
