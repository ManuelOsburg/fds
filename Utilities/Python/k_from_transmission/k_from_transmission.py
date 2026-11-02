#!/usr/bin/env python
"""
k_from_transmission.py

Re-express the "Smoke Obscuration" validation data of the FDS Validation Guide in
terms of the light extinction coefficient k (1/m) and recompute the guide's model
statistics (bias factor delta and relative model standard deviation sigma_M) for k.

Pipeline (deterministic, driven by pins.json):

  1. snapshot   : extract the pinned commits of fds / exp / out from the local git
                  clones (git archive) into work/snapshots/<variant>/
  2. repro      : run the guide's own code (fdsplotlib.dataplot + scatplot of the
                  pinned fds commit) on the smoke rows -> guide statistics and
                  per-point raw scatter values (guide_repro.py, subprocess)
  3. points     : independent extraction of the same time series, conversion of every
                  sample to k, metric per column (max k, k of mean, mean of k)
  4. crosscheck : compare the independent obscuration metrics with the guide's values
  5. stats      : guide formulas (McGrattan & Toman 2011) in obscuration space and in
                  k space, per data set and pooled, for several sigma_E options and
                  for both implementations of the sigma_M lower bound
  6. report     : REPORT.md generated from the output files only (write_report.py)

Usage:
  python k_from_transmission.py run [--variant 6.11.1|master|all] [--outdir DIR]
                                    [--workdir DIR] [--skip-repro] [--skip-report]

Repository locations default to the firemodels layout (fds, exp, out side by side).
Nothing is written into the exp/out clones.
"""

import argparse
import csv
import io
import json
import math
import os
import platform
import re
import subprocess
import sys
import tarfile
from datetime import datetime, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PINS_FILE = os.path.join(HERE, "pins.json")
REFERENCE_FILE = os.path.join(HERE, "reference_table_16_1.csv")

# sigma_E options evaluated in k space. Values are relative standard deviations.
# "fixed_*"    : one value for all points, as in the guide.
# "prop_relO"  : per-point propagation of a relative uncertainty of the obscuration O
#                k = -ln(1 - O/100)  ->  sigma_k = sigma_O / (100 - O) = s*O/T
# "prop_relT"  : per-point propagation of a relative uncertainty of the transmission T
#                k = -ln(T/100)      ->  sigma_k = sigma_T / T = s  (absolute in k)
# The per-point values are pooled as sigma_E_eff^2 = mean(sigma_E_i^2) over the
# points entering the statistic (see REPORT.md).
# PRIMARY_SIGMA_E is the option chosen for the headline k statistics (decision of
# M. Osburg, 2026-11-02): 0.19 is the combined sigma_E the guide gives for Smoke
# Concentration in its table "Summary of uncertainty estimates" (Error chapter:
# 0.14 measurement, 0.13 propagated input). Smoke concentration is proportional to k.
# The other options are reported as sensitivity; "prop_relT" is kept only to document
# why a transmission-relative propagation does not fit the guide's single-sigma scheme.
PRIMARY_SIGMA_E = "fixed_0.19"
SIGMA_E_OPTIONS = [
    ("fixed_0.07", 0.07),
    ("fixed_0.08", 0.08),
    ("fixed_0.14", 0.14),
    ("fixed_0.19", 0.19),
    ("prop_relO_0.07", 0.07),
    ("prop_relT_0.07", 0.07),
]

DATASET_SHORT = {
    "NIST/NRC": "NIST_NRC",
    "FAA Cargo Compartments": "FAA_Cargo",
    "FM/FPRF Datacenter": "FM_FPRF",
}

FDS_DEFAULT_MEC = 8700.0  # m2/kg, read.f90: IF (MASS_EXTINCTION_COEFFICIENT < 0) ... = 8700


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

def log(msg):
    print("[k_from_transmission] " + msg, flush=True)


def git(repo, *args):
    out = subprocess.run(["git", "-C", repo] + list(args), check=True, capture_output=True)
    return out.stdout


def git_text(repo, *args):
    return git(repo, *args).decode("utf-8", errors="replace").strip()


def fds_branch_base(repo):
    """Commit at which the working branch left firemodels master (upstream/master or
    origin/master, whichever exists); falls back to HEAD."""
    for ref in ("upstream/master", "origin/master"):
        try:
            return git_text(repo, "merge-base", "HEAD", ref)
        except subprocess.CalledProcessError:
            continue
    return git_text(repo, "rev-parse", "HEAD")


def snapshot(repo, commit, paths, dest):
    """Extract `paths` of `commit` from the git object store of `repo` into `dest`.

    Uses `git archive` + tarfile, so nothing is checked out in the clone itself.
    A stamp file makes the step idempotent.
    """
    stamp = os.path.join(dest, ".snapshot_commit")
    if os.path.isfile(stamp) and open(stamp).read().strip() == commit:
        return
    os.makedirs(dest, exist_ok=True)
    data = git(repo, "archive", "--format=tar", commit, "--", *paths)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as tf:
        tf.extractall(dest, filter="data")
    with open(stamp, "w") as f:
        f.write(commit + "\n")


def read_table(path, header_row, data_row):
    """Read a dataplot-style CSV: header at spreadsheet row header_row, numeric data
    from data_row on. Column names are stripped like fdsplotlib does.
    Returns (names, 2-D float array with NaN for non-numeric cells)."""
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        rows = list(csv.reader(f))
    names = [c.strip() for c in rows[header_row - 1]]
    data = []
    for r in rows[data_row - 1:]:
        if not any(c.strip() for c in r):
            continue
        vals = []
        for j in range(len(names)):
            c = r[j].strip() if j < len(r) else ""
            try:
                vals.append(float(c))
            except ValueError:
                vals.append(np.nan)
        data.append(vals)
    return names, np.array(data, dtype=float)


def fnum(x):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return ""
    return repr(float(x)) if isinstance(x, (float, np.floating)) else str(x)


def k_from_T(T):
    """Extinction coefficient (1/m) from transmission in %/m: k = -ln(T/100)."""
    T = np.asarray(T, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        k = -np.log(T / 100.0)
    return k


# ----------------------------------------------------------------------------
# step 3: own extraction and conversion
# ----------------------------------------------------------------------------

def comp_mask(x, y0, c0, c1, d0, d1):
    """Comparison window as in fdsplotlib._compute_metrics_block."""
    m = np.isfinite(x)
    if np.isfinite(c0):
        m &= x >= c0
    if np.isfinite(c1):
        m &= x <= c1
    if np.isfinite(d0) or np.isfinite(d1):
        dm = np.isfinite(y0)
        if np.isfinite(d0):
            dm &= y0 >= d0
        if np.isfinite(d1):
            dm &= y0 <= d1
        m &= dm
    return m


def guide_metric(metric, y, init):
    """Scalar metric exactly as fdsplotlib._compute_metrics_block (subset)."""
    if metric == "max":
        out = np.nanmax(y) - init
    elif metric == "min":
        out = init - np.nanmin(y)
    elif metric == "mean":
        out = abs(np.nanmean(y) - init)
    else:
        raise ValueError("metric %r not supported here" % metric)
    if out == 0.0:
        out = 1e-12
    return float(out)


def extract_points(variant, pins, snap, quantities):
    """Walk the smoke rows of the pinned dataplot inputs and build one record per
    (row, column) with the guide metric (obscuration O) and the k-based metrics."""
    pydir = os.path.join(snap["fds"], "Utilities", "Python")
    dataplot_inputs = os.path.join(pydir, "FDS_validation_dataplot_inputs.csv")
    scatter_inputs = os.path.join(pydir, "FDS_validation_scatterplot_inputs.csv")

    with open(scatter_inputs, newline="") as f:
        scat = {r["Scatter_Plot_Title"]: r for r in csv.DictReader(f)}

    records = []
    with open(dataplot_inputs, newline="", encoding="utf-8", errors="replace") as f:
        for rownum, row in enumerate(csv.DictReader(f), start=2):
            q = row.get("Quantity")
            if q not in quantities or row["switch_id"] != "d":
                continue
            metric = row["Metric"].strip().lower()
            exp_names, exp_data = read_table(os.path.join(snap["exp"], row["d1_Filename"]),
                                             int(row["d1_Col_Name_Row"]), int(row["d1_Data_Row"]))
            mod_names, mod_data = read_table(os.path.join(snap["out"], row["d2_Filename"]),
                                             int(row["d2_Col_Name_Row"]), int(row["d2_Data_Row"]))
            exp_cols = [c.strip() for c in row["d1_Dep_Col_Name"].split("|")]
            mod_cols = [c.strip() for c in row["d2_Dep_Col_Name"].split("|")]
            x_e = exp_data[:, exp_names.index(row["d1_Ind_Col_Name"].strip())]
            x_m = mod_data[:, mod_names.index(row["d2_Ind_Col_Name"].strip())]
            init_e = float(row["d1_Initial_Value"] or 0.0)
            init_m = float(row["d2_Initial_Value"] or 0.0)
            win_e = [float(row[k]) if row[k] not in ("", None) else np.nan
                     for k in ("d1_Comp_Start", "d1_Comp_End", "d1_Dep_Comp_Start", "d1_Dep_Comp_End")]
            win_m = [float(row[k]) if row[k] not in ("", None) else np.nan
                     for k in ("d2_Comp_Start", "d2_Comp_End", "d2_Dep_Comp_Start", "d2_Dep_Comp_End")]
            # The exp/model quantity type follows the dataplot definition:
            # Initial_Value 100 + metric min  -> transmission T (%/m), O = 100 - min T
            # Initial_Value 0   + metric mean/max -> obscuration O (%/m)
            # (6.11.1 FM rows: mass concentration mg/m3, not convertible -> O/k left empty)
            if q == "Smoke Obscuration":
                if init_e == 100.0 and metric == "min":
                    qtype = "T"
                elif init_e == 0.0 and metric in ("mean", "max"):
                    qtype = "O"
                else:
                    raise ValueError("unexpected metric/initial value in row %d" % rownum)
            else:
                qtype = "mass"

            plot_min = float(scat[q]["Plot_Min"])
            plot_max = float(scat[q]["Plot_Max"])
            sigma_e_guide = float(scat[q]["Sigma_E"]) / 100.0

            for j, (ce, cm) in enumerate(zip(exp_cols, mod_cols)):
                ye = exp_data[:, exp_names.index(ce)]
                ym = mod_data[:, mod_names.index(cm)]
                # cull NaN pairs per series (fdsplotlib CASE 3), then comparison window
                me = np.isfinite(x_e) & np.isfinite(ye)
                mm = np.isfinite(x_m) & np.isfinite(ym)
                xe, ye = x_e[me], ye[me]
                xm, ym = x_m[mm], ym[mm]
                we = comp_mask(xe, ye, *win_e)
                wm = comp_mask(xm, ym, *win_m)
                ye_w, ym_w = ye[we], ym[wm]
                if ye_w.size == 0 or ym_w.size == 0:
                    log("row %d column %s: no samples in comparison window" % (rownum, ce))
                    continue

                rec = {
                    "variant": variant,
                    "dataset": row["Group_Key_Label"],
                    "dataplot_row": rownum,
                    "test": row["Plot_Title"],
                    "exp_file": row["d1_Filename"],
                    "exp_column": ce,
                    "model_file": row["d2_Filename"],
                    "model_column": cm,
                    "quantity": q,
                    "metric": metric,
                    "exp_type": qtype,
                    "comp_start_s": fnum(win_e[0]),
                    "comp_end_s": fnum(win_e[1]),
                    "n_samples_exp": int(ye_w.size),
                    "n_samples_model": int(ym_w.size),
                    "guide_metric_exp": guide_metric(metric, ye_w, init_e),
                    "guide_metric_model": guide_metric(metric, ym_w, init_m),
                    "guide_plot_min": plot_min,
                    "guide_plot_max": plot_max,
                    "guide_sigma_e": sigma_e_guide,
                }
                O_e = O_m = T_e = T_m = np.nan
                k_e = k_m = k_e_mok = k_m_mok = np.nan
                n_bad_e = n_bad_m = 0
                if qtype == "T":
                    T_e_series, T_m_series = ye_w, ym_w
                    O_e_series, O_m_series = 100.0 - ye_w, 100.0 - ym_w
                elif qtype == "O":
                    O_e_series, O_m_series = ye_w, ym_w
                    T_e_series, T_m_series = 100.0 - ye_w, 100.0 - ym_w
                else:
                    T_e_series = T_m_series = None
                if T_e_series is not None:
                    ke_series = k_from_T(T_e_series)
                    km_series = k_from_T(T_m_series)
                    n_bad_e = int(np.sum(~np.isfinite(ke_series)))   # T <= 0 -> k infinite / NaN
                    n_bad_m = int(np.sum(~np.isfinite(km_series)))
                    # metric values in O and T
                    O_e, O_m = rec["guide_metric_exp"], rec["guide_metric_model"]
                    if metric in ("min", "max"):
                        # min T <-> max O <-> max k: identical for every monotone conversion
                        T_e, T_m = float(np.nanmin(T_e_series)), float(np.nanmin(T_m_series))
                        k_e = float(np.nanmax(ke_series)) if n_bad_e == 0 else float("inf")
                        k_m = float(np.nanmax(km_series)) if n_bad_m == 0 else float("inf")
                    else:  # mean
                        T_e, T_m = 100.0 - O_e, 100.0 - O_m
                        k_e = float(k_from_T(T_e))            # k of the mean obscuration
                        k_m = float(k_from_T(T_m))
                        k_e_mok = float(np.mean(ke_series))   # mean of k(t)
                        k_m_mok = float(np.mean(km_series))
                rec.update({
                    "T_exp": T_e, "T_mod": T_m,
                    "O_exp": O_e, "O_mod": O_m,
                    "k_exp": k_e, "k_mod": k_m,
                    "k_exp_mean_of_k": k_e_mok, "k_mod_mean_of_k": k_m_mok,
                    "n_samples_T_le_0_exp": n_bad_e,
                    "n_samples_T_le_0_model": n_bad_m,
                })
                # guide point selection (applied in the guide's quantity space)
                ge, gm = rec["guide_metric_exp"], rec["guide_metric_model"]
                rec["in_guide_selection"] = int(plot_min <= ge <= plot_max and plot_min <= gm <= plot_max and ge > 0 and gm > 0)
                rec["k_finite_positive"] = int(np.isfinite(k_e) and np.isfinite(k_m) and k_e > 0 and k_m > 0)
                records.append(rec)
    return records


# ----------------------------------------------------------------------------
# step 4: cross-check against the guide's raw scatter values
# ----------------------------------------------------------------------------

def crosscheck(records, repro_points):
    """Pair own obscuration metrics with the guide's raw scatter values by dataplot row
    (order of columns within a row is preserved by both codes)."""
    by_row = {}
    for r in repro_points:
        by_row.setdefault((r["Quantity"], int(r["csv_rownum"])), []).append(r)
    out = []
    for rec in records:
        key = (rec["quantity"], rec["dataplot_row"])
        lst = by_row.get(key, [])
        idx = sum(1 for o in out if (o["quantity"], o["dataplot_row"]) == key)
        g = lst[idx] if idx < len(lst) else None
        ge = float(g["Measured_Values"]) if g else np.nan
        gm = float(g["Predicted_Values"]) if g else np.nan
        oe, om = rec["guide_metric_exp"], rec["guide_metric_model"]
        out.append({
            "variant": rec["variant"], "quantity": rec["quantity"], "dataplot_row": rec["dataplot_row"],
            "dataset": rec["dataset"], "exp_column": rec["exp_column"],
            "guide_measured": ge, "own_measured": oe,
            "guide_predicted": gm, "own_predicted": om,
            "rel_diff_measured": abs(oe - ge) / abs(ge) if np.isfinite(ge) and ge != 0 else np.nan,
            "rel_diff_predicted": abs(om - gm) / abs(gm) if np.isfinite(gm) and gm != 0 else np.nan,
        })
    return out


# ----------------------------------------------------------------------------
# step 5: statistics
# ----------------------------------------------------------------------------

def guide_statistics(E, M, sigma_e):
    """Bias and relative standard deviations as in fdsplotlib.scatplot (unweighted,
    Weight_Data = no). Returns both implementations of the lower bound:
      code  : sigma_M = sqrt(max(0, u^2 - sigma_E^2))            (Python fdsplotlib, 6.11.1 and master)
      floor : sigma_E := min(u/sqrt(2), sigma_E) first, hence sigma_M >= sigma_E
              (MATLAB scatplot.m up to FDS 6.9; wording of the guide, Error chapter)
    """
    E = np.asarray(E, float)
    M = np.asarray(M, float)
    n = E.size
    lnME = np.log(M) - np.log(E)
    mean_ln = float(np.mean(lnME))
    u2 = float(np.sum((lnME - mean_ln) ** 2) / (n - 1)) if n > 1 else 0.0
    u = math.sqrt(u2)
    res = {"n": n, "mean_ln_M_over_E": mean_ln, "u": u, "median_M_over_E": float(np.median(M / E))}
    sE = sigma_e
    sM = math.sqrt(max(0.0, u2 - sE ** 2))
    res.update({"sigma_E_code": sE, "sigma_M_code": sM,
                "delta_code": math.exp(mean_ln + 0.5 * sM ** 2 - 0.5 * sE ** 2)})
    sE_f = min(u / math.sqrt(2.0), sigma_e)
    sM_f = math.sqrt(max(0.0, u2 - sE_f ** 2))
    res.update({"sigma_E_floor": sE_f, "sigma_M_floor": sM_f,
                "delta_floor": math.exp(mean_ln + 0.5 * sM_f ** 2 - 0.5 * sE_f ** 2),
                "sigma_E_capped": int(sE_f < sigma_e)})
    return res


def per_point_sigma_e(option, s, recs, kcol_e):
    """Per-point relative standard deviation of k_exp for the propagation options."""
    out = []
    for r in recs:
        k = r[kcol_e]
        O = r["O_exp"] if r["metric"] != "min" else 100.0 - r["T_exp"]
        T = 100.0 - O
        if option.startswith("prop_relO"):
            out.append(s * O / (T * k))
        elif option.startswith("prop_relT"):
            out.append(s / k)
        else:
            out.append(s)
    return np.array(out, float)


def compute_stats(variant, records):
    rows = []
    obs = [r for r in records if r["quantity"] == "Smoke Obscuration"]
    groups = [("pooled", obs)] + [(d, [r for r in obs if r["dataset"] == d])
                                  for d in sorted({r["dataset"] for r in obs})]
    for gname, recs in groups:
        if not recs:
            continue
        # --- obscuration space, guide's sigma_E, guide's point selection ---
        sel = [r for r in recs if r["in_guide_selection"]]
        if sel:
            st = guide_statistics([r["guide_metric_exp"] for r in sel], [r["guide_metric_model"] for r in sel],
                                  sel[0]["guide_sigma_e"])
            rows.append(dict(variant=variant, dataset=gname, space="O", k_mean_mode="", selection="guide_O",
                             sigma_E_option="guide_%.2f" % sel[0]["guide_sigma_e"], primary=1, sigma_E_min="", sigma_E_median="",
                             sigma_E_max="", **st))
        # --- k space ---
        for selection in ("guide_O", "all_k"):
            for kmode, ke_col, km_col in (("k_of_metric", "k_exp", "k_mod"),
                                          ("mean_of_k", "k_exp_mean_of_k", "k_mod_mean_of_k")):
                # mean_of_k differs from k_of_metric only for 'mean' rows; use the
                # k_of_metric value for all other rows so that both modes cover all points
                def kval(r, col, base):
                    v = r[col]
                    return v if np.isfinite(v) else r[base]
                sub = []
                for r in recs:
                    if selection == "guide_O" and not r["in_guide_selection"]:
                        continue
                    ke, km = kval(r, ke_col, "k_exp"), kval(r, km_col, "k_mod")
                    if np.isfinite(ke) and np.isfinite(km) and ke > 0 and km > 0:
                        sub.append((r, ke, km))
                if len(sub) < 3:
                    continue
                if kmode == "mean_of_k" and not any(r["metric"] == "mean" for r, _, _ in sub):
                    continue  # identical to k_of_metric for this group
                E = [ke for _, ke, _ in sub]
                M = [km for _, _, km in sub]
                for option, s in SIGMA_E_OPTIONS:
                    sig_i = per_point_sigma_e(option, s, [dict(r, k_exp=ke) for r, ke, _ in sub], "k_exp")
                    sigma_eff = float(math.sqrt(np.mean(sig_i ** 2)))
                    st = guide_statistics(E, M, sigma_eff)
                    primary = int(option == PRIMARY_SIGMA_E and selection == "guide_O" and kmode == "k_of_metric")
                    rows.append(dict(variant=variant, dataset=gname, space="k", k_mean_mode=kmode, selection=selection,
                                     sigma_E_option=option, primary=primary, sigma_E_min=float(np.min(sig_i)),
                                     sigma_E_median=float(np.median(sig_i)), sigma_E_max=float(np.max(sig_i)), **st))
    return rows


# ----------------------------------------------------------------------------
# step 5b: units and DEVC definitions per column
# ----------------------------------------------------------------------------

def nist_exp_conversion_check(variant, records, snap, min_conc_mg=1.0):
    """The NIST/NRC column 'Trans. (%/m)' in firemodels/exp was derived from the
    reported smoke mass concentration 'Smoke Conc.' (exp commit fd70c63d, 2026-05-22).
    Recover the implied mass extinction coefficient -ln(T/100)/m_s per row (m2/kg)
    for every NIST/NRC file used, so that the origin of the "measured" transmission
    is documented. Rows with m_s < min_conc_mg (mg/m3) are skipped (noise)."""
    out = []
    for f in sorted({r["exp_file"] for r in records if r["dataset"] == "NIST/NRC"}):
        names, data = read_table(os.path.join(snap["exp"], f), 1, 2)
        if "Smoke Conc." not in names or "Trans. (%/m)" not in names:
            out.append({"variant": variant, "exp_file": f, "n_rows": 0, "coef_min_m2_per_kg": "", "coef_median_m2_per_kg": "",
                        "coef_max_m2_per_kg": "", "note": "columns not found"})
            continue
        m = data[:, names.index("Smoke Conc.")] * 1e-6          # mg/m3 -> kg/m3
        T = data[:, names.index("Trans. (%/m)")]
        ok = np.isfinite(m) & np.isfinite(T) & (m > min_conc_mg * 1e-6) & (T > 0)
        with np.errstate(divide="ignore"):
            coef = -np.log(T[ok] / 100.0) / m[ok]
        out.append({"variant": variant, "exp_file": f, "n_rows": int(ok.sum()),
                    "coef_min_m2_per_kg": float(np.min(coef)) if ok.any() else "",
                    "coef_median_m2_per_kg": float(np.median(coef)) if ok.any() else "",
                    "coef_max_m2_per_kg": float(np.max(coef)) if ok.any() else "",
                    "note": "T = 100*exp(-coef*m_s) with m_s from column 'Smoke Conc.' (mg/m3)"})
    return out


def column_provenance(variant, records, snap):
    seen = set()
    rows = []
    for r in records:
        key = (r["model_file"], r["model_column"], r["exp_file"], r["exp_column"])
        if key in seen:
            continue
        seen.add(key)
        case_dir = os.path.dirname(r["model_file"])
        chid = os.path.basename(r["model_file"]).replace("_devc.csv", "")
        fds_in = os.path.join(snap["fds"], "Validation", case_dir, "FDS_Input_Files", chid + ".fds")
        devc_line = mec = soot_yield = ""
        related = []
        if os.path.isfile(fds_in):
            txt = open(fds_in, encoding="utf-8", errors="replace").read()
            lines = txt.splitlines()
            pat = re.compile(r"ID\s*=\s*'%s'" % re.escape(r["model_column"]))
            for ln in lines:
                if "&DEVC" in ln and pat.search(ln):
                    devc_line = ln.strip()
                suffix = r["model_column"].split(" ")[-1]
                if ("&CTRL" in ln or "&DEVC" in ln) and ("'%s'" % r["model_column"]) in ln or \
                        ("&CTRL" in ln and suffix in ln and r["model_column"].startswith("OBS ")):
                    related.append(ln.strip())
            m = re.findall(r"MASS_EXTINCTION_COEFFICIENT\s*=\s*([0-9.Ee+-]+)", txt)
            mec = ";".join(sorted(set(m))) if m else "%g (FDS default, read.f90)" % FDS_DEFAULT_MEC
            m = re.findall(r"SOOT_YIELD\s*=\s*([0-9.Ee+-]+)", txt)
            soot_yield = ";".join(sorted(set(m)))
        # units from the model devc file (row 1) and the exp file (row between header and data, if any)
        mod_units = ""
        with open(os.path.join(snap["out"], r["model_file"]), newline="") as f:
            hdr = list(csv.reader(f))[:2]
        if len(hdr) == 2:
            names = [c.strip() for c in hdr[1]]
            if r["model_column"] in names:
                mod_units = hdr[0][names.index(r["model_column"])].strip()
        exp_units = ""
        with open(os.path.join(snap["exp"], r["exp_file"]), newline="", encoding="utf-8", errors="replace") as f:
            erows = list(csv.reader(f))[:3]
        # find the dataplot header/data rows for this file from the record
        rows.append({
            "variant": variant, "dataset": r["dataset"], "exp_file": r["exp_file"], "exp_column": r["exp_column"],
            "exp_units": exp_units, "model_file": r["model_file"], "model_column": r["model_column"],
            "model_units_devc_csv": mod_units, "fds_input": os.path.relpath(fds_in, snap["fds"]).replace("\\", "/") if fds_in else "",
            "devc_line": devc_line, "related_lines": " ; ".join(dict.fromkeys(related)),
            "mass_extinction_coefficient_m2_per_kg": mec, "soot_yield": soot_yield,
            "_erows": erows,
        })
    return rows


def fill_exp_units(colrows, records):
    """Experimental units: a units row exists if Data_Row - Col_Name_Row == 2 (FAA);
    otherwise the unit is part of the column name (NIST: 'Trans. (%/m)') or absent
    (FM files, whose dataplot Dep_Title is 'Obscuration (%/m)')."""
    meta = {}
    for r in records:
        meta[r["exp_file"]] = r
    for c in colrows:
        erows = c.pop("_erows")
        # recover header/data rows by searching the header row for the column
        hdr_idx = next((i for i, row in enumerate(erows) if c["exp_column"] in [x.strip() for x in row]), None)
        if hdr_idx is not None and hdr_idx + 2 < len(erows):
            cand = erows[hdr_idx + 1]
            names = [x.strip() for x in erows[hdr_idx]]
            try:
                float(cand[0])
                c["exp_units"] = "(no units row)"
            except ValueError:
                c["exp_units"] = cand[names.index(c["exp_column"])].strip()
        else:
            c["exp_units"] = "(no units row)"
    return colrows


# ----------------------------------------------------------------------------
# I/O
# ----------------------------------------------------------------------------

def write_csv(path, rows, fields=None):
    if not rows:
        return
    fields = fields or list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: fnum(v) if isinstance(v, float) else v for k, v in r.items()})


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def package_versions():
    import importlib.metadata as md
    out = {}
    for p in ("numpy", "pandas", "matplotlib", "scipy", "pytest"):
        try:
            out[p] = md.version(p)
        except md.PackageNotFoundError:
            out[p] = None
    return out


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

def run(args):
    pins = json.load(open(PINS_FILE))
    variants = list(pins["variants"]) if args.variant == "all" else [args.variant]
    quantities = pins["smoke_quantities"]
    outdir = os.path.abspath(args.outdir)
    workdir = os.path.abspath(args.workdir)
    os.makedirs(outdir, exist_ok=True)
    os.makedirs(workdir, exist_ok=True)
    repos = {"fds": os.path.abspath(args.fds_repo), "exp": os.path.abspath(args.exp_repo), "out": os.path.abspath(args.out_repo)}

    provenance = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": package_versions(),
        # paths relative to the fds clone, so that no local directory names are recorded
        "repos": {k: {"path": os.path.relpath(v, repos["fds"]).replace("\\", "/"),
                      "head": git_text(v, "rev-parse", "HEAD"),
                      "describe": git_text(v, "describe", "--tags", "--always")} for k, v in repos.items() if k != "fds"},
        # for fds the branch point from upstream master is recorded instead of HEAD,
        # because HEAD changes with every commit of this folder
        "fds_branch": git_text(repos["fds"], "rev-parse", "--abbrev-ref", "HEAD"),
        "fds_branch_base": fds_branch_base(repos["fds"]),
        "variants": {},
        "sigma_E_options": SIGMA_E_OPTIONS,
        "primary_sigma_E": PRIMARY_SIGMA_E,
    }

    all_stats = []
    for variant in variants:
        pv = pins["variants"][variant]
        log("variant %s: snapshots" % variant)
        snap = {k: os.path.join(workdir, "snapshots", variant, k) for k in ("fds", "exp", "out")}
        snapshot(repos["fds"], pv["fds"], pins["fds_paths"], snap["fds"])
        snapshot(repos["exp"], pv["exp"], pins["data_paths"], snap["exp"])
        snapshot(repos["out"], pv["out"], pins["data_paths"], snap["out"])
        vinfo = {"pins": pv,
                 "commit_dates": {k: git_text(repos[k], "log", "-1", "--format=%cs", pv[k]) for k in ("fds", "exp", "out")},
                 "fds_describe": git_text(repos["fds"], "describe", "--tags", pv["fds"]),
                 "out_git_txt": {}}
        for case, gf in (("NIST_NRC", "NIST_NRC/NIST_NRC_01_git.txt"),
                         ("FAA_Cargo_Compartments", "FAA_Cargo_Compartments/FAA_B707_Test_1_git.txt"),
                         ("FM_FPRF_Datacenter", "FM_FPRF_Datacenter/FM_Datacenter_Low_C3H6_SF_git.txt")):
            p = os.path.join(snap["out"], gf)
            vinfo["out_git_txt"][case] = open(p).read().strip() if os.path.isfile(p) else ""

        # --- step 2: guide code ---
        repro_dir = os.path.join(workdir, "repro", variant)
        if not args.skip_repro:
            log("variant %s: guide reproduction (dataplot/scatplot of pinned fdsplotlib)" % variant)
            cmd = [sys.executable, os.path.join(HERE, "guide_repro.py"),
                   "--fds-snapshot", snap["fds"], "--expdir", snap["exp"], "--cmpdir", snap["out"],
                   "--workdir", repro_dir, "--result-dir", repro_dir, "--quantities", json.dumps(quantities)]
            subprocess.run(cmd, check=True)
        repro_stats = read_csv(os.path.join(repro_dir, "guide_repro_stats.csv"))
        repro_points = read_csv(os.path.join(repro_dir, "guide_repro_points.csv"))
        for r in repro_stats:
            r["variant"] = variant
        write_csv(os.path.join(outdir, "guide_repro_%s.csv" % variant), repro_stats,
                  ["variant"] + [k for k in repro_stats[0].keys() if k != "variant"])
        for r in repro_points:
            r["variant"] = variant
        write_csv(os.path.join(outdir, "guide_repro_points_%s.csv" % variant), repro_points,
                  ["variant"] + [k for k in repro_points[0].keys() if k != "variant"])

        # --- step 3/4: own extraction and cross-check ---
        log("variant %s: time-series conversion" % variant)
        records = extract_points(variant, pins, snap, quantities)
        write_csv(os.path.join(outdir, "points_%s.csv" % variant), records)
        cc = crosscheck(records, repro_points)
        write_csv(os.path.join(outdir, "crosscheck_%s.csv" % variant), cc)
        worst = max([x for r in cc for x in (r["rel_diff_measured"], r["rel_diff_predicted"]) if np.isfinite(x)] or [np.nan])
        vinfo["crosscheck_max_rel_diff"] = worst
        vinfo["crosscheck_n_points"] = len(cc)
        vinfo["crosscheck_n_unmatched"] = sum(1 for r in cc if not np.isfinite(r["guide_measured"]))

        # --- step 5 ---
        log("variant %s: statistics" % variant)
        st = compute_stats(variant, records)
        all_stats.extend(st)
        write_csv(os.path.join(outdir, "stats_%s.csv" % variant), st)
        cols = fill_exp_units(column_provenance(variant, records, snap), records)
        write_csv(os.path.join(outdir, "columns_%s.csv" % variant), cols)
        write_csv(os.path.join(outdir, "nist_exp_conversion_check_%s.csv" % variant),
                  nist_exp_conversion_check(variant, records, snap))
        provenance["variants"][variant] = vinfo

    # combined stats over all variants present in outdir
    combined = []
    for v in pins["variants"]:
        p = os.path.join(outdir, "stats_%s.csv" % v)
        if os.path.isfile(p):
            combined.extend(read_csv(p))
    write_csv(os.path.join(outdir, "stats.csv"), combined)

    prov_path = os.path.join(outdir, "provenance.json")
    old = json.load(open(prov_path)) if os.path.isfile(prov_path) else {}
    old_variants = old.get("variants", {})
    old_variants.update(provenance["variants"])
    provenance["variants"] = old_variants
    with open(prov_path, "w", encoding="utf-8") as f:
        json.dump(provenance, f, indent=2, default=str)

    if not args.skip_report:
        import write_report
        write_report.main(outdir, REFERENCE_FILE, os.path.join(HERE, "REPORT.md"))
        log("REPORT.md written")
    log("done")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run", help="run the pipeline")
    p.add_argument("--variant", default="all", choices=["all", "6.11.1", "master"])
    p.add_argument("--outdir", default=os.path.join(HERE, "output"))
    p.add_argument("--workdir", default=os.path.join(HERE, "work"))
    p.add_argument("--fds-repo", default=os.path.join(HERE, "..", "..", ".."))
    p.add_argument("--exp-repo", default=os.path.join(HERE, "..", "..", "..", "..", "exp"))
    p.add_argument("--out-repo", default=os.path.join(HERE, "..", "..", "..", "..", "out"))
    p.add_argument("--skip-repro", action="store_true", help="reuse guide reproduction results in workdir")
    p.add_argument("--skip-report", action="store_true")
    args = ap.parse_args(argv)
    sys.path.insert(0, HERE)
    run(args)


if __name__ == "__main__":
    main()
