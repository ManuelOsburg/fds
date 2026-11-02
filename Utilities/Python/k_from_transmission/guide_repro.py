#!/usr/bin/env python
"""
guide_repro.py

Run the FDS Validation Guide plotting/statistics code (fdsplotlib.dataplot and
fdsplotlib.scatplot of a pinned fds commit) on pinned exp/out snapshots, restricted
to the rows of FDS_validation_dataplot_inputs.csv whose Quantity is a smoke
quantity. The script is executed as a subprocess by k_from_transmission.py so
that each variant imports its own copy of fdsplotlib.

Writes
  <result_dir>/guide_repro_stats.csv   : the smoke rows of validation_scatterplot_output.csv
  <result_dir>/guide_repro_points.csv  : per-point raw scatter values written by scatplot
  <result_dir>/guide_repro_log.txt     : captured stdout of dataplot/scatplot
"""

import argparse
import csv
import glob
import io
import json
import os
import shutil
import sys
from contextlib import redirect_stdout


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fds-snapshot", required=True, help="directory holding Utilities/Python of the pinned fds commit")
    ap.add_argument("--expdir", required=True, help="snapshot of firemodels/exp")
    ap.add_argument("--cmpdir", required=True, help="snapshot of firemodels/out")
    ap.add_argument("--workdir", required=True, help="scratch directory for figures and intermediate files")
    ap.add_argument("--result-dir", required=True)
    ap.add_argument("--quantities", required=True, help="JSON list of Quantity values to select")
    args = ap.parse_args()

    quantities = json.loads(args.quantities)
    pydir = os.path.join(args.fds_snapshot, "Utilities", "Python")
    dataplot_inputs = os.path.join(pydir, "FDS_validation_dataplot_inputs.csv")
    scatter_inputs = os.path.join(pydir, "FDS_validation_scatterplot_inputs.csv")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sys.path.insert(0, pydir)
    import fdsplotlib  # noqa: E402  (the pinned copy)

    # --- select rows by Quantity (spreadsheet row numbers, header = row 1) ---
    rows = []
    plot_dirs = set()
    with open(dataplot_inputs, newline="", encoding="utf-8", errors="replace") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            if row.get("Quantity") in quantities:
                rows.append(i)
                plot_dirs.add(os.path.dirname(row["Plot_Filename"]))
    if not rows:
        raise SystemExit("no dataplot rows with Quantity in %s" % quantities)

    # --- directories the guide code expects to exist ---
    figdir = os.path.join(args.workdir, "figures") + os.sep
    scatdir = os.path.join(args.workdir, "figures", "FDS_Validation_Guide", "SCRIPT_FIGURES", "Scatterplots") + os.sep
    if os.path.isdir(figdir):
        shutil.rmtree(figdir)
    for d in plot_dirs:
        os.makedirs(os.path.join(figdir, d), exist_ok=True)
    os.makedirs(scatdir, exist_ok=True)
    os.makedirs(args.result_dir, exist_ok=True)

    expdir = args.expdir.rstrip("/\\") + os.sep
    cmpdir = args.cmpdir.rstrip("/\\") + os.sep

    log = io.StringIO()
    with redirect_stdout(log):
        saved_data, drange = fdsplotlib.dataplot(
            config_filename=dataplot_inputs,
            expdir=expdir,
            cmpdir=cmpdir,
            pltdir=figdir,
            close_figs=True,
            verbose=True,
            plot_range=rows,
        )
        plt.close("all")
        fdsplotlib.scatplot(
            saved_data, drange,
            Manuals_Dir=figdir,
            Scatterplot_Inputs_File=scatter_inputs,
            Stats_Output="Validation",
            Scatterplot_Dir=scatdir,
            verbose=True,
        )
        plt.close("all")

    with open(os.path.join(args.result_dir, "guide_repro_log.txt"), "w", encoding="utf-8") as f:
        f.write(log.getvalue())

    # --- collect statistics rows ---
    stats_file = os.path.join(scatdir, "validation_scatterplot_output.csv")
    with open(stats_file, newline="") as f:
        stats_rows = [r for r in csv.DictReader(f) if r["Quantity"] in quantities]
    with open(os.path.join(args.result_dir, "guide_repro_stats.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(stats_rows[0].keys()) if stats_rows else ["Quantity"])
        w.writeheader()
        w.writerows(stats_rows)

    # --- collect raw per-point scatter values ---
    # scatplot names the raw file after the basename of Plot_Filename in the scatterplot inputs
    with open(scatter_inputs, newline="") as f:
        plot_files = {r["Scatter_Plot_Title"]: os.path.basename(r["Plot_Filename"]) for r in csv.DictReader(f)}
    point_rows = []
    for q in quantities:
        if q not in plot_files:
            continue
        for path in glob.glob(os.path.join(scatdir, plot_files[q] + "_raw_scatter_values.csv")):
            with open(path, newline="") as f:
                for r in csv.DictReader(f):
                    r = dict(r)
                    r["Quantity"] = q
                    point_rows.append(r)
    if point_rows:
        fields = ["Quantity"] + [k for k in point_rows[0].keys() if k != "Quantity"]
        with open(os.path.join(args.result_dir, "guide_repro_points.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(point_rows)

    print("guide_repro: %d dataplot rows, %d statistics rows, %d points" % (len(rows), len(stats_rows), len(point_rows)))


if __name__ == "__main__":
    main()
