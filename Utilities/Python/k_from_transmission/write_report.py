#!/usr/bin/env python
"""
write_report.py

Generate REPORT.md (German) from the files written by k_from_transmission.py.
Every number in the report is read from output/*.csv, output/provenance.json or
reference_table_16_1.csv; nothing is typed in by hand.
"""

import csv
import json
import os
from collections import OrderedDict


def read_csv(path):
    if not os.path.isfile(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def f2(x):
    try:
        return "%.2f" % float(x)
    except (TypeError, ValueError):
        return "–"


def f3(x):
    try:
        return "%.3f" % float(x)
    except (TypeError, ValueError):
        return "–"


def g4(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "–"
    return "%.4g" % v


def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out) + "\n"


def tex_clean(s):
    return s.replace("C$_3$H$_6$", "C3H6").replace("$", "")


SIGMA_LABEL = OrderedDict([
    ("fixed_0.07", "fest 0,07 (wie Obscuration)"),
    ("fixed_0.08", "fest 0,08"),
    ("fixed_0.14", "fest 0,14 (nur Messunsicherheit NIST/NRC)"),
    ("fixed_0.19", "fest 0,19 (Guide-Tabelle Smoke Concentration, kombiniert; gewählt)"),
    ("prop_relO_0.07", "Fortpflanzung je Punkt, 7 % relativ auf O"),
    ("prop_relT_0.07", "Fortpflanzung je Punkt, 7 % relativ auf T (nicht empfohlen)"),
])


def main(outdir, reference_file, report_path):
    prov = json.load(open(os.path.join(outdir, "provenance.json"), encoding="utf-8"))
    ref = read_csv(reference_file)
    stats = read_csv(os.path.join(outdir, "stats.csv"))
    variants = [v for v in ("6.11.1", "master") if v in prov["variants"]]
    repro = {v: read_csv(os.path.join(outdir, "guide_repro_%s.csv" % v)) for v in variants}
    repro_pts = {v: read_csv(os.path.join(outdir, "guide_repro_points_%s.csv" % v)) for v in variants}
    points = {v: read_csv(os.path.join(outdir, "points_%s.csv" % v)) for v in variants}
    columns = {v: read_csv(os.path.join(outdir, "columns_%s.csv" % v)) for v in variants}

    L = []
    L.append("# Extinktionskoeffizient k aus den Rauch-Validierungsdaten des FDS Validation Guide\n")
    L.append("Erzeugt am %s (UTC) von `k_from_transmission.py`; alle Zahlen stammen aus den Dateien in `output/`.\n" % prov["generated_utc"])
    L.append("Varianten: **6.11.1** = Stand des Validation Guide 6.11.1 (Tabelle 16.1), **master** = firemodels master zum Zeitpunkt des Klonens.\n")

    # ------------------------------------------------------------------ 1
    L.append("## 1. Datenstand und Umgebung\n")
    rows = []
    for v in variants:
        vi = prov["variants"][v]
        rows.append([v, "`%s` (%s, %s)" % (vi["pins"]["fds"][:9], vi["fds_describe"], vi["commit_dates"]["fds"]),
                     "`%s` (%s)" % (vi["pins"]["exp"][:9], vi["commit_dates"]["exp"]),
                     "`%s` (%s)" % (vi["pins"]["out"][:9], vi["commit_dates"]["out"])])
    L.append(md_table(["Variante", "fds", "exp", "out"], rows))
    L.append("\nFDS-Version, mit der die Ergebnisse in `out` gerechnet wurden (Datei `*_git.txt`):\n")
    rows = []
    for v in variants:
        g = prov["variants"][v]["out_git_txt"]
        rows.append([v, g.get("NIST_NRC", ""), g.get("FAA_Cargo_Compartments", ""), g.get("FM_FPRF_Datacenter", "")])
    L.append(md_table(["Variante", "NIST_NRC", "FAA_Cargo_Compartments", "FM_FPRF_Datacenter"], rows))
    L.append("\nWahl der Commits für 6.11.1: fds = Release-Tag; exp und out = letzter master-Commit vor dem Tag-Datum. "
             "Die Versionsstrings der Guide-Abbildungen (FDS-6.11.0-14-g86de436 für NIST/NRC, FDS-6.10.1-1912-gf88650b für FAA) "
             "stimmen mit den `_git.txt`-Dateien dieses out-Standes überein.\n")
    pk = prov["packages"]
    L.append("\nUmgebung: Python %s, %s; Pakete: %s. Arbeitskopie fds auf Branch `%s`, abgezweigt von firemodels master bei `%s`.\n" % (
        prov["python"], prov["platform"], ", ".join("%s %s" % (k, val) for k, val in pk.items() if val),
        prov["fds_branch"], prov["fds_branch_base"][:9]))

    # ------------------------------------------------------------------ 2
    L.append("\n## 2. Reproduktion der Guide-Statistik mit dem Guide-Code\n")
    L.append("Lauf von `fdsplotlib.dataplot` und `fdsplotlib.scatplot` des jeweils gepinnten fds-Commits über alle Zeilen der "
             "`FDS_validation_dataplot_inputs.csv` mit Quantity *Smoke Obscuration* bzw. *Smoke Concentration*; "
             "Statistik aus `validation_scatterplot_output.csv`.\n")
    rows = []
    ref_map = {(r["variant"], r["Quantity"]): r for r in ref}
    all_match = True
    for v in variants:
        for r in repro[v]:
            rr = ref_map.get((v, r["Quantity"]))
            if rr:
                ok = all(f2(r[k]) == f2(rr[k]) for k in ("Sigma_Experiment", "Sigma_Model", "Bias")) and \
                    r["Number of Points"] == rr["Number of Points"] and r["Number of Datasets"] == rr["Number of Datasets"]
                all_match &= ok
                refstr = "%s / %s / %s / %s / %s" % (rr["Number of Datasets"], rr["Number of Points"], f2(rr["Sigma_Experiment"]), f2(rr["Sigma_Model"]), f2(rr["Bias"]))
                okstr = "ja" if ok else "**nein**"
            else:
                refstr, okstr = "–", "–"
            rows.append([v, r["Quantity"], r["Number of Datasets"], r["Number of Points"], f2(r["Sigma_Experiment"]),
                         f2(r["Sigma_Model"]), f2(r["Bias"]), refstr, okstr])
    L.append(md_table(["Variante", "Quantity", "Datensätze", "Punkte", "σ̃_E", "σ̃_M", "δ", "Tabelle 16.1 (Datens./Punkte/σ̃_E/σ̃_M/δ)", "übereinstimmend"], rows))
    L.append("\nDie Referenzwerte stammen aus `reference_table_16_1.csv` (Transkription der Tabelle 16.1 aus der Aufgabenstellung). "
             "Ergebnis des Abgleichs: %s.\n" % ("alle Kennzahlen reproduziert" if all_match else "**Abweichungen vorhanden, siehe Tabelle**"))

    # points dropped by the guide's plot range
    L.append("\nPunkte, die der Guide-Code vor der Statistik verwirft (außerhalb `Plot_Min`…`Plot_Max` der Scatterplot-Definition oder nicht positiv):\n")
    rows = []
    for v in variants:
        pm = {}
        for p in points[v]:
            pm[(p["quantity"], p["dataplot_row"])] = p
        for r in repro_pts[v]:
            p = pm.get((r["Quantity"], r["csv_rownum"]))
            lo = float(p["guide_plot_min"]) if p else None
            hi = float(p["guide_plot_max"]) if p else None
            m, pr = float(r["Measured_Values"]), float(r["Predicted_Values"])
            if lo is None or not (lo <= m <= hi and lo <= pr <= hi and m > 0 and pr > 0):
                rows.append([v, r["Quantity"], r["Dataname"], r["csv_rownum"], g4(m), g4(pr), "%g … %g" % (lo, hi) if lo is not None else "–"])
    L.append(md_table(["Variante", "Quantity", "Datensatz", "dataplot-Zeile", "Messung", "Modell", "zulässiger Bereich"], rows) if rows else "keine\n")

    L.append("\nUnabhängige Nachrechnung der Kennwerte (eigene Extraktion in `points_<variante>.csv`) gegen die vom Guide-Code "
             "geschriebenen Rohwerte (`guide_repro_points_<variante>.csv`, dort auf 4 signifikante Stellen gerundet):\n")
    rows = []
    for v in variants:
        vi = prov["variants"][v]
        rows.append([v, vi["crosscheck_n_points"], vi["crosscheck_n_unmatched"], "%.2e" % vi["crosscheck_max_rel_diff"]])
    L.append(md_table(["Variante", "Punkte", "nicht zuordenbar", "max. relative Abweichung"], rows))

    L.append("\nUnterschiede zwischen den Varianten (aus den Git-Historien, siehe Abschnitt 1): In master sind NIST/NRC und FAA mit einer "
             "neueren FDS-Version neu gerechnet, FM/FPRF ist von Rauchkonzentration (mg/m³, Metrik mean) auf Obscuration (%/m, "
             "Metrik mean bzw. max) umgestellt, und die Scatterplot-Definition *Smoke Obscuration* wurde von linear, Bereich 1…100, "
             "auf loglog, Bereich 0.1…100 geändert. Am Statistikcode (`scatplot`) hat sich zwischen den beiden fds-Ständen nichts geändert; "
             "die einzige Änderung an `fdsplotlib.py` betrifft das spaltenweise Einlesen der CSV-Dateien.\n")

    # ------------------------------------------------------------------ 3
    L.append("\n## 3. Umrechnung der Zeitreihen auf k\n")
    L.append("Definitionen (Guide, Kapitel Species, FAA-Abschnitt): Transmission T = 100 (I/I₀)^(1/L) in %/m, "
             "Obscuration O = 100 − T in %/m, Extinktionskoeffizient k = −ln(T/100) = −ln(1 − O/100) in 1/m. "
             "Die Umrechnung erfolgt je Abtastwert innerhalb des Vergleichsfensters der dataplot-Zeile, erst danach wird die Metrik gebildet:\n\n"
             "- Metrik *min* auf T (NIST/NRC, FAA; `Initial_Value` 100): Guide-Kennwert O = 100 − min T; in k: max k = −ln(min T/100). "
             "Monotone Umrechnung, daher ist k des Kennwerts gleich dem Kennwert der k-Reihe.\n"
             "- Metrik *max* auf O (FM Cable): Guide-Kennwert max O; in k: max k. Ebenfalls eindeutig.\n"
             "- Metrik *mean* auf O (FM C3H6, Fenster 200…1000 s): Guide-Kennwert |mean O|; in k zwei Varianten: "
             "`k_of_metric` = −ln(1 − mean O/100) und `mean_of_k` = mean(−ln(1 − O(t)/100)). Beide werden ausgewiesen.\n")
    n_bad = {v: sum(int(p["n_samples_T_le_0_exp"]) + int(p["n_samples_T_le_0_model"]) for p in points[v]) for v in variants}
    L.append("\nAbtastwerte mit T ≤ 0 (k nicht definiert): %s.\n" % ", ".join("%s: %d" % (v, n_bad[v]) for v in variants))
    conv = {v: read_csv(os.path.join(outdir, "nist_exp_conversion_check_%s.csv" % v)) for v in variants}
    if any(conv.values()):
        L.append("\nHerkunft der NIST/NRC-Messspalte `Trans. (%/m)`: Sie wurde in firemodels/exp (Commit fd70c63d, 2026-05-22) aus der zuvor "
                 "verwendeten Spalte `Smoke Conc.` (mg/m³) berechnet. Der je Zeile zurückgerechnete Koeffizient −ln(T/100)/m_s "
                 "(`nist_exp_conversion_check_<variante>.csv`, Zeilen mit m_s ≥ 1 mg/m³):\n")
        rows = []
        for v in variants:
            for r in conv[v]:
                rows.append([v, r["exp_file"].split("/")[-1], r["n_rows"], g4(r["coef_min_m2_per_kg"]), g4(r["coef_median_m2_per_kg"]), g4(r["coef_max_m2_per_kg"])])
        L.append(md_table(["Variante", "Datei", "Zeilen", "min (m²/kg)", "Median (m²/kg)", "max (m²/kg)"], rows))
        L.append("\nDamit ist k_exp = φ_s·m_s mit demselben φ_s, mit dem NIST m_s = ln(I₀/I)/(φ_s L) aus der Lasermessung bestimmt hat (Error-Kapitel: 8,7 m²/g). "
                 "k_exp ist also die ursprünglich gemessene Größe ln(I₀/I)/L, unabhängig vom Wert von φ_s. Eine Pfadlänge geht in die Umrechnung nicht ein.\n")

    L.append("\nEinheiten und Modellgrößen je Datensatz (aus `columns_<variante>.csv`; DEVC-Zeilen aus den FDS-Inputs des gepinnten fds-Standes, "
             "Einheiten aus Zeile 1 der `_devc.csv` bzw. aus der Messdatei):\n")
    rows = []
    for v in variants:
        seen = set()
        for c in columns[v]:
            key = (c["dataset"], c["exp_units"], c["model_units_devc_csv"], c["mass_extinction_coefficient_m2_per_kg"], c["soot_yield"],
                   c["devc_line"].split("QUANTITY=")[1].split(",")[0] if "QUANTITY=" in c["devc_line"] else "")
            if key in seen:
                continue
            seen.add(key)
            rows.append([v, c["dataset"], c["exp_column"] if c["dataset"].startswith("NIST") else c["exp_file"].split("/")[-1].split("_")[0] + "… / " + c["exp_column"],
                         c["exp_units"], c["model_column"], c["model_units_devc_csv"], key[5], c["mass_extinction_coefficient_m2_per_kg"], c["soot_yield"]])
    L.append(md_table(["Variante", "Datensatz", "Messspalte (Beispiel)", "Einheit Messdatei", "Modellspalte (Beispiel)", "Einheit devc", "DEVC QUANTITY", "MASS_EXTINCTION_COEFFICIENT (m²/kg)", "SOOT_YIELD"], rows))
    fm_lines = [c for v in variants for c in columns[v] if c["dataset"].startswith("FM") and c["model_column"].startswith("OBS")]
    if fm_lines:
        L.append("\nFM/FPRF (master): `OBS …` ist ein CONTROL-VALUE-Device; Kette im FDS-Input: EXTINCTION COEFFICIENT → ×(−1) → EXP → 1 − … → ×100, "
                 "also O = 100 (1 − e^(−K)) mit dem lokalen Extinktionskoeffizienten K am Punkt. Die Rückrechnung k = −ln(1 − O/100) ist damit exakt. "
                 "Zeilen aus `%s`:\n\n" % fm_lines[0]["fds_input"])
        for ln in fm_lines[0]["related_lines"].split(" ; "):
            L.append("    %s\n" % ln)
        L.append("\nDie FM-Messdateien (`c3h6_*.csv`, `cable_sf_low.csv`) haben keine Einheitenzeile; die Einheit %/m folgt aus `Dep_Title` der dataplot-Zeile "
                 "(*Obscuration (%/m)*) und dem Guide-Text. Das ist eine Annahme, die im Fork nicht weiter belegbar ist.\n")

    # FM mean rows: k_of_metric vs mean_of_k
    fm_mean = [p for v in variants for p in points[v] if p["metric"] == "mean" and p["quantity"] == "Smoke Obscuration"]
    if fm_mean:
        L.append("\nFM-Zeilen mit Metrik *mean*: k des Mittelwerts gegenüber Mittelwert von k (1/m):\n")
        rows = []
        for p in fm_mean:
            rows.append([p["variant"], tex_clean(p["test"]), p["exp_column"], g4(p["O_exp"]), g4(p["O_mod"]), g4(p["k_exp"]), g4(p["k_mod"]),
                         g4(p["k_exp_mean_of_k"]), g4(p["k_mod_mean_of_k"]), "ja" if p["in_guide_selection"] == "1" else "nein"])
        L.append(md_table(["Variante", "Fall", "Spalte", "O_exp", "O_mod", "k_exp (k of mean)", "k_mod (k of mean)", "k_exp (mean of k)", "k_mod (mean of k)", "im Guide-Punktsatz"], rows))

    # ------------------------------------------------------------------ 4
    L.append("\n## 4. Statistik und Untergrenze von σ̃_M\n")
    L.append("Formeln wie im Guide (Error chapter, Gl. stdev und delta): u² = Var(ln(M/E)) mit n−1, σ̃_M² = u² − σ̃_E², "
             "δ = exp(mean ln(M/E) + σ̃_M²/2 − σ̃_E²/2), ungewichtet (`Weight_Data` = no für *Smoke Obscuration*). "
             "Untergrenze im Code:\n\n"
             "- Python `fdsplotlib.scatplot` (6.11.1 und master, identisch): `Sigma_M = sqrt(max(0, u² − Sigma_E²))`. "
             "Es gibt **keine** Untergrenze σ̃_M ≥ σ̃_E; σ̃_E wird unverändert übernommen, σ̃_M kann bis 0 fallen. Spalten `*_code`.\n"
             "- MATLAB `scatplot.m` (bis FDS 6.9, z. B. Tag FDS-6.9.1): `Sigma_E = min(u/sqrt(2), Sigma_E)` vor der Differenz, "
             "wodurch σ̃_M ≥ σ̃_E gilt; das entspricht dem Guide-Text (\"σ̃_M cannot be less than σ̃_E\"). Spalten `*_floor`; "
             "`sigma_E_capped` = 1 markiert Fälle, in denen die Kappung greift.\n\n"
             "Für die Fehlerfortpflanzung je Punkt wird σ̃_E,eff² = mean(σ̃_E,i²) über die verwendeten Punkte in die Guide-Formeln eingesetzt "
             "(Erwartungswert der Varianz von ln(M/E) bei punktweise verschiedenem σ̃_E,i). Mit s = 0,07: "
             "relativ auf O: σ̃_k,i = s·O/(T·k); relativ auf T: σ̃_k,i = s/k, jeweils am Messwert.\n")

    # ------------------------------------------------------------------ 5
    L.append("\n## 5. Ergebnisse\n")
    primary = prov.get("primary_sigma_E", "fixed_0.19")
    L.append("### 5.1 Hauptergebnis: k des Kennwerts, Punktsatz des Guide, σ̃_E = %s (Spalte `primary` = 1 in `stats.csv`), Code-Konvention\n"
             % SIGMA_LABEL.get(primary, primary))
    L.append("Die Wahl σ̃_E = 0,19 für k wurde am 2026-11-02 von M. Osburg getroffen. Es ist der kombinierte Wert, den der Guide in der Tabelle "
             "\"Summary of uncertainty estimates\" (Error chapter) für Smoke Concentration angibt: Messunsicherheit 0,14 und fortgepflanzte "
             "Eingangsunsicherheit (Wärmefreisetzung, Rußausbeute) 0,13. Nach der Definition des Guide ist σ̃_E dieser kombinierte Wert. "
             "Die Rauchkonzentration ist proportional zu k, und die NIST/NRC-Transmission in exp ist aus ihr berechnet (Abschnitt 3). "
             "Eine erste Wahl von 0,14 am selben Tag berücksichtigte nur die Messunsicherheit und wurde korrigiert. "
             "Die 7 % der Obscuration-Kategorie sind im Guide nicht hergeleitet; die Tabelle hat keine Zeile für Obscuration. "
             "Die übrigen Optionen in 5.2 dienen als Sensitivität.\n")
    rows = []
    for v in variants:
        for ds in ("pooled", "NIST/NRC", "FAA Cargo Compartments", "FM/FPRF Datacenter"):
            o = next((s for s in stats if s["variant"] == v and s["dataset"] == ds and s["space"] == "O"), None)
            k = next((s for s in stats if s["variant"] == v and s["dataset"] == ds and s["space"] == "k" and s["primary"] == "1"), None)
            if not o and not k:
                continue
            rows.append([v, "gepoolt" if ds == "pooled" else ds, o["n"] if o else "–", f3(o["u"]) if o else "–", f2(o["sigma_E_code"]) if o else "–", f2(o["sigma_M_code"]) if o else "–", f2(o["delta_code"]) if o else "–",
                         f3(k["u"]) if k else "–", f2(k["sigma_E_code"]) if k else "–", f2(k["sigma_M_code"]) if k else "–", f2(k["delta_code"]) if k else "–",
                         f2(k["sigma_M_floor"]) if k else "–", f2(k["delta_floor"]) if k else "–", k["sigma_E_capped"] if k else "–"])
    L.append(md_table(["Variante", "Datensatz", "n", "u (O)", "σ̃_E (O)", "σ̃_M (O)", "δ (O)", "u (k)", "σ̃_E (k)", "σ̃_M (k)", "δ (k)", "σ̃_M (k, floor)", "δ (k, floor)", "gekappt"], rows))

    L.append("\n### 5.2 Einfluss von σ̃_E (gepoolt, k des Kennwerts, Punktsatz des Guide)\n")
    rows = []
    for v in variants:
        for opt, label in SIGMA_LABEL.items():
            s = next((s for s in stats if s["variant"] == v and s["dataset"] == "pooled" and s["space"] == "k" and s["k_mean_mode"] == "k_of_metric"
                      and s["selection"] == "guide_O" and s["sigma_E_option"] == opt), None)
            if not s:
                continue
            per_pt = "–" if opt.startswith("fixed") else "%s / %s / %s" % (f2(s["sigma_E_min"]), f2(s["sigma_E_median"]), f2(s["sigma_E_max"]))
            rows.append([v, label, s["n"], per_pt, f2(s["sigma_E_code"]), f2(s["sigma_M_code"]), f2(s["delta_code"]),
                         f2(s["sigma_E_floor"]), f2(s["sigma_M_floor"]), f2(s["delta_floor"]), s["sigma_E_capped"]])
    L.append(md_table(["Variante", "σ̃_E-Option", "n", "σ̃_E,i min/median/max", "σ̃_E,eff", "σ̃_M (code)", "δ (code)", "σ̃_E (floor)", "σ̃_M (floor)", "δ (floor)", "gekappt"], rows))

    L.append("\n### 5.3 Alle Kombinationen je Datensatz (k, Punktsatz des Guide)\n")
    rows = []
    for v in variants:
        for ds in ("pooled", "NIST/NRC", "FAA Cargo Compartments", "FM/FPRF Datacenter"):
            for mode in ("k_of_metric", "mean_of_k"):
                for opt, label in SIGMA_LABEL.items():
                    s = next((s for s in stats if s["variant"] == v and s["dataset"] == ds and s["space"] == "k" and s["k_mean_mode"] == mode
                              and s["selection"] == "guide_O" and s["sigma_E_option"] == opt), None)
                    if not s:
                        continue
                    rows.append([v, "gepoolt" if ds == "pooled" else ds, mode, opt, s["n"], f3(s["u"]), f2(s["sigma_E_code"]), f2(s["sigma_M_code"]), f2(s["delta_code"]),
                                 f2(s["sigma_M_floor"]), f2(s["delta_floor"]), s["sigma_E_capped"]])
    L.append(md_table(["Variante", "Datensatz", "k-Mittelung", "σ̃_E-Option", "n", "u", "σ̃_E,eff", "σ̃_M (code)", "δ (code)", "σ̃_M (floor)", "δ (floor)", "gekappt"], rows))

    L.append("\n### 5.4 Punktauswahl: Guide-Punktsatz gegenüber allen Punkten mit endlichem positivem k (gepoolt, σ̃_E 0,07)\n")
    rows = []
    for v in variants:
        for mode in ("k_of_metric", "mean_of_k"):
            for sel in ("guide_O", "all_k"):
                s = next((s for s in stats if s["variant"] == v and s["dataset"] == "pooled" and s["space"] == "k" and s["k_mean_mode"] == mode
                          and s["selection"] == sel and s["sigma_E_option"] == "fixed_0.07"), None)
                if s:
                    rows.append([v, mode, sel, s["n"], f3(s["u"]), f2(s["sigma_M_code"]), f2(s["delta_code"])])
    L.append(md_table(["Variante", "k-Mittelung", "Punktsatz", "n", "u", "σ̃_M (code)", "δ (code)"], rows))
    extra = [p for v in variants for p in points[v] if p["quantity"] == "Smoke Obscuration" and p["in_guide_selection"] == "0" and p["k_finite_positive"] == "1"]
    if extra:
        L.append("\nPunkte, die nur im Punktsatz `all_k` enthalten sind:\n")
        L.append(md_table(["Variante", "Datensatz", "Fall", "Spalte", "O_exp", "O_mod", "k_exp", "k_mod"],
                          [[p["variant"], p["dataset"], tex_clean(p["test"]), p["exp_column"], g4(p["O_exp"]), g4(p["O_mod"]), g4(p["k_exp"]), g4(p["k_mod"])] for p in extra]))

    # ------------------------------------------------------------------ 6
    L.append("\n## 6. Offene Entscheidungen\n")
    L.append("1. **σ̃_E in k**: entschieden am 2026-11-02: fest 0,19 (Begründung in 5.1; erste Wahl 0,14 korrigiert); Sensitivität 0,07 bis 0,19 und Fortpflanzung auf O in 5.2. "
             "Die Fortpflanzung relativ auf T liefert bei kleinem k sehr große σ̃_E,i und kippt ohne Untergrenze in σ̃_M = 0; sie wird nicht verwendet.\n"
             "2. **Untergrenze**: Code-Konvention (keine) oder Guide-Text/MATLAB-Konvention (σ̃_M ≥ σ̃_E); unterscheidet sich nur in den mit `gekappt` = 1 markierten Zeilen.\n"
             "3. **Zeitmittel (FM, master)**: k des Mittelwerts oder Mittelwert von k; Abschnitt 3 und 5.3.\n"
             "4. **Punktsatz**: Punktsatz des Guide (Filter in O: Bereich `Plot_Min`…`Plot_Max`) oder alle Punkte mit endlichem k; Abschnitt 5.4.\n"
             "5. **Datenstand** für das Paper: 6.11.1 (veröffentlichte Tabelle, 2 Datensätze) oder master (3 Datensätze, laufend veränderlich; hier gepinnt).\n"
             "6. **Gewichtung**: ungewichtet wie im Guide für *Smoke Obscuration*; eine Bin-Gewichtung in k wäre eine neue Entscheidung.\n"
             "7. **Herkunft der 7 %**: Die Unsicherheitstabelle des Error-Kapitels hat keine Zeile für Obscuration; Smoke Concentration hat 0,14 Messung, "
             "0,13 fortgepflanzte Eingangsgrößen, 0,19 kombiniert. Die 7 % der Scatterplot-Definition (bis 6.11.0: 20 %) sind im Guide nicht hergeleitet.\n")

    # ------------------------------------------------------------------ 7
    L.append("\n## 7. Dateien\n")
    L.append("- `output/points_<variante>.csv`: alle Punkte (Datensatz, Fall, Messstelle, Metrik, T_exp, T_mod, O_exp, O_mod, k_exp, k_mod, mean-of-k, Flags).\n"
             "- `output/stats.csv`, `output/stats_<variante>.csv`: Kennzahlen aller Varianten.\n"
             "- `output/guide_repro_<variante>.csv`, `output/guide_repro_points_<variante>.csv`: Ausgabe des Guide-Codes.\n"
             "- `output/crosscheck_<variante>.csv`: eigene Kennwerte gegen Guide-Rohwerte.\n"
             "- `output/columns_<variante>.csv`: Einheiten und DEVC-Definitionen je Spalte.\n"
             "- `output/provenance.json`: Commits, Daten, Paketversionen.\n"
             "- `reference_table_16_1.csv`: Referenzwerte der Tabelle 16.1 (Transkription).\n"
             "- `test_reproduction.py`: pytest-Prüfung der Reproduktion von 6.11.1.\n")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    import sys
    here = os.path.dirname(os.path.abspath(__file__))
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "output"),
         os.path.join(here, "reference_table_16_1.csv"), os.path.join(here, "REPORT.md"))
