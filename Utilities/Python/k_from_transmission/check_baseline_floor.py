#!/usr/bin/env python
"""
check_baseline_floor.py

List the validation categories in the guide's baseline statistics file
(Manuals/FDS_Validation_Guide/SCRIPT_FIGURES/Scatterplots/validation_scatterplot_output_baseline.csv)
for which Sigma_Model < Sigma_Experiment, i.e. where the constraint stated in the
Validation Guide (Error chapter: sigma_M cannot be less than sigma_E) is violated.
Writes output/baseline_sigma_check.csv (all categories, with a flag) and prints the
violating rows.
"""

import csv
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
FDS = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BASELINE = os.path.join(FDS, "Manuals", "FDS_Validation_Guide", "SCRIPT_FIGURES", "Scatterplots",
                        "validation_scatterplot_output_baseline.csv")


def main():
    head = subprocess.run(["git", "-C", FDS, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    log = subprocess.run(["git", "-C", FDS, "log", "-1", "--format=%h %cs", "--", BASELINE], capture_output=True, text=True).stdout.strip()
    rows = []
    with open(BASELINE, newline="") as f:
        for r in csv.DictReader(f):
            try:
                se, sm = float(r["Sigma_Experiment"]), float(r["Sigma_Model"])
            except (TypeError, ValueError):
                continue
            rows.append({"Quantity": r["Quantity"], "Number of Points": r["Number of Points"],
                         "Sigma_Experiment": r["Sigma_Experiment"], "Sigma_Model": r["Sigma_Model"], "Bias": r["Bias"],
                         "sigma_M_lt_sigma_E": int(sm < se), "fds_head": head, "baseline_last_commit": log})
    out = os.path.join(HERE, "output", "baseline_sigma_check.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    bad = [r for r in rows if r["sigma_M_lt_sigma_E"]]
    print("%d categories, %d with Sigma_Model < Sigma_Experiment (baseline %s):" % (len(rows), len(bad), log))
    for r in bad:
        print("  %-45s n=%4s  sigma_E=%s  sigma_M=%s  bias=%s" % (r["Quantity"], r["Number of Points"], r["Sigma_Experiment"], r["Sigma_Model"], r["Bias"]))


if __name__ == "__main__":
    main()
