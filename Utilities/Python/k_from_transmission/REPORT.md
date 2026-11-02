# Extinktionskoeffizient k aus den Rauch-Validierungsdaten des FDS Validation Guide

Erzeugt am 2026-11-02T12:48:21+00:00 (UTC) von `k_from_transmission.py`; alle Zahlen stammen aus den Dateien in `output/`.

Varianten: **6.11.1** = Stand des Validation Guide 6.11.1 (Tabelle 16.1), **master** = firemodels master zum Zeitpunkt des Klonens.

## 1. Datenstand und Umgebung

| Variante | fds | exp | out |
|---|---|---|---|
| 6.11.1 | `ff928dbf6` (FDS-6.11.1, 2026-07-09) | `39d8b7358` (2026-06-30) | `d4c34a675` (2026-06-29) |
| master | `76170f30b` (FDS-6.11.1-407-g76170f30b, 2026-10-31) | `704e0d91f` (2026-10-21) | `4885e605b` (2026-10-30) |


FDS-Version, mit der die Ergebnisse in `out` gerechnet wurden (Datei `*_git.txt`):

| Variante | NIST_NRC | FAA_Cargo_Compartments | FM_FPRF_Datacenter |
|---|---|---|---|
| 6.11.1 | FDS-6.11.0-14-g86de436-master | FDS-6.10.1-1912-gf88650b-master | FDS-6.10.1-1773-g20dc4c7-master |
| master | FDS-6.11.1-77-gc444053-master | FDS-6.11.1-77-gc444053-master | FDS-6.11.1-171-g2c63c6e-master |


Wahl der Commits für 6.11.1: fds = Release-Tag; exp und out = letzter master-Commit vor dem Tag-Datum. Die Versionsstrings der Guide-Abbildungen (FDS-6.11.0-14-g86de436 für NIST/NRC, FDS-6.10.1-1912-gf88650b für FAA) stimmen mit den `_git.txt`-Dateien dieses out-Standes überein.


Umgebung: Python 3.12.11, Windows-11-10.0.22631-SP0; Pakete: numpy 1.26.4, pandas 2.3.3, matplotlib 3.11.2, scipy 1.17.1, pytest 9.2.0. Arbeitskopie fds auf Branch `k-from-transmission`, abgezweigt von firemodels master bei `76170f30b`.


## 2. Reproduktion der Guide-Statistik mit dem Guide-Code

Lauf von `fdsplotlib.dataplot` und `fdsplotlib.scatplot` des jeweils gepinnten fds-Commits über alle Zeilen der `FDS_validation_dataplot_inputs.csv` mit Quantity *Smoke Obscuration* bzw. *Smoke Concentration*; Statistik aus `validation_scatterplot_output.csv`.

| Variante | Quantity | Datensätze | Punkte | σ̃_E | σ̃_M | δ | Tabelle 16.1 (Datens./Punkte/σ̃_E/σ̃_M/δ) | übereinstimmend |
|---|---|---|---|---|---|---|---|---|
| 6.11.1 | Smoke Concentration | 1 | 10 | 0.19 | 0.63 | 0.83 | 1 / 10 / 0.19 / 0.63 / 0.83 | ja |
| 6.11.1 | Smoke Obscuration | 2 | 33 | 0.07 | 0.26 | 1.24 | 2 / 33 / 0.07 / 0.26 / 1.24 | ja |
| master | Smoke Obscuration | 3 | 44 | 0.07 | 0.71 | 1.27 | – | – |


Die Referenzwerte stammen aus `reference_table_16_1.csv` (Transkription der Tabelle 16.1 aus der Aufgabenstellung). Ergebnis des Abgleichs: alle Kennzahlen reproduziert.


Punkte, die der Guide-Code vor der Statistik verwirft (außerhalb `Plot_Min`…`Plot_Max` der Scatterplot-Definition oder nicht positiv):

| Variante | Quantity | Datensatz | dataplot-Zeile | Messung | Modell | zulässiger Bereich |
|---|---|---|---|---|---|---|
| 6.11.1 | Smoke Concentration | FM/FPRF Datacenter | 4333 | 0.35 | 1.563 | 1 … 600 |
| 6.11.1 | Smoke Concentration | FM/FPRF Datacenter | 4334 | 0.41 | 0.0003332 | 1 … 600 |
| 6.11.1 | Smoke Concentration | FM/FPRF Datacenter | 4335 | 2.3 | 0.04641 | 1 … 600 |
| 6.11.1 | Smoke Concentration | FM/FPRF Datacenter | 4337 | 1.25 | 0.5949 | 1 … 600 |
| master | Smoke Obscuration | FM/FPRF Datacenter | 4507 | 0.2046 | 2.596e-05 | 0.1 … 100 |


Unabhängige Nachrechnung der Kennwerte (eigene Extraktion in `points_<variante>.csv`) gegen die vom Guide-Code geschriebenen Rohwerte (`guide_repro_points_<variante>.csv`, dort auf 4 signifikante Stellen gerundet):

| Variante | Punkte | nicht zuordenbar | max. relative Abweichung |
|---|---|---|---|
| 6.11.1 | 47 | 0 | 3.52e-04 |
| master | 45 | 0 | 1.94e-04 |


Unterschiede zwischen den Varianten (aus den Git-Historien, siehe Abschnitt 1): In master sind NIST/NRC und FAA mit einer neueren FDS-Version neu gerechnet, FM/FPRF ist von Rauchkonzentration (mg/m³, Metrik mean) auf Obscuration (%/m, Metrik mean bzw. max) umgestellt, und die Scatterplot-Definition *Smoke Obscuration* wurde von linear, Bereich 1…100, auf loglog, Bereich 0.1…100 geändert. Am Statistikcode (`scatplot`) hat sich zwischen den beiden fds-Ständen nichts geändert; die einzige Änderung an `fdsplotlib.py` betrifft das spaltenweise Einlesen der CSV-Dateien.


## 3. Umrechnung der Zeitreihen auf k

Definitionen (Guide, Kapitel Species, FAA-Abschnitt): Transmission T = 100 (I/I₀)^(1/L) in %/m, Obscuration O = 100 − T in %/m, Extinktionskoeffizient k = −ln(T/100) = −ln(1 − O/100) in 1/m. Die Umrechnung erfolgt je Abtastwert innerhalb des Vergleichsfensters der dataplot-Zeile, erst danach wird die Metrik gebildet:

- Metrik *min* auf T (NIST/NRC, FAA; `Initial_Value` 100): Guide-Kennwert O = 100 − min T; in k: max k = −ln(min T/100). Monotone Umrechnung, daher ist k des Kennwerts gleich dem Kennwert der k-Reihe.
- Metrik *max* auf O (FM Cable): Guide-Kennwert max O; in k: max k. Ebenfalls eindeutig.
- Metrik *mean* auf O (FM C3H6, Fenster 200…1000 s): Guide-Kennwert |mean O|; in k zwei Varianten: `k_of_metric` = −ln(1 − mean O/100) und `mean_of_k` = mean(−ln(1 − O(t)/100)). Beide werden ausgewiesen.


Abtastwerte mit T ≤ 0 (k nicht definiert): 6.11.1: 0, master: 0.


Herkunft der NIST/NRC-Messspalte `Trans. (%/m)`: Sie wurde in firemodels/exp (Commit fd70c63d, 2026-05-22) aus der zuvor verwendeten Spalte `Smoke Conc.` (mg/m³) berechnet. Der je Zeile zurückgerechnete Koeffizient −ln(T/100)/m_s (`nist_exp_conversion_check_<variante>.csv`, Zeilen mit m_s ≥ 1 mg/m³):

| Variante | Datei | Zeilen | min (m²/kg) | Median (m²/kg) | max (m²/kg) |
|---|---|---|---|---|---|
| 6.11.1 | NIST_NRC_Test_01_file_1.csv | 289 | 8678 | 8700 | 8717 |
| 6.11.1 | NIST_NRC_Test_02_file_1.csv | 117 | 8689 | 8700 | 8704 |
| 6.11.1 | NIST_NRC_Test_03_file_1.csv | 204 | 8696 | 8700 | 8702 |
| 6.11.1 | NIST_NRC_Test_04_file_1.csv | 129 | 8688 | 8700 | 8705 |
| 6.11.1 | NIST_NRC_Test_05_file_1.csv | 202 | 8682 | 8700 | 8729 |
| 6.11.1 | NIST_NRC_Test_07_file_1.csv | 215 | 8676 | 8700 | 8712 |
| 6.11.1 | NIST_NRC_Test_08_file_1.csv | 123 | 8685 | 8700 | 8739 |
| 6.11.1 | NIST_NRC_Test_09_file_1.csv | 275 | 8675 | 8700 | 8731 |
| 6.11.1 | NIST_NRC_Test_10_file_1.csv | 281 | 8664 | 8700 | 8726 |
| 6.11.1 | NIST_NRC_Test_13_file_1.csv | 166 | 8699 | 8700 | 8703 |
| 6.11.1 | NIST_NRC_Test_14_file_1.csv | 227 | 8681 | 8700 | 8702 |
| 6.11.1 | NIST_NRC_Test_15_file_1.csv | 299 | 8696 | 8700 | 8711 |
| 6.11.1 | NIST_NRC_Test_16_file_1.csv | 177 | 8686 | 8700 | 8712 |
| 6.11.1 | NIST_NRC_Test_17_file_1.csv | 85 | 8698 | 8700 | 8702 |
| 6.11.1 | NIST_NRC_Test_18_file_1.csv | 298 | 8692 | 8700 | 8714 |
| master | NIST_NRC_Test_01_file_1.csv | 289 | 8678 | 8700 | 8717 |
| master | NIST_NRC_Test_02_file_1.csv | 117 | 8689 | 8700 | 8704 |
| master | NIST_NRC_Test_03_file_1.csv | 204 | 8696 | 8700 | 8702 |
| master | NIST_NRC_Test_04_file_1.csv | 129 | 8688 | 8700 | 8705 |
| master | NIST_NRC_Test_05_file_1.csv | 202 | 8682 | 8700 | 8729 |
| master | NIST_NRC_Test_07_file_1.csv | 215 | 8676 | 8700 | 8712 |
| master | NIST_NRC_Test_08_file_1.csv | 123 | 8685 | 8700 | 8739 |
| master | NIST_NRC_Test_09_file_1.csv | 275 | 8675 | 8700 | 8731 |
| master | NIST_NRC_Test_10_file_1.csv | 281 | 8664 | 8700 | 8726 |
| master | NIST_NRC_Test_13_file_1.csv | 166 | 8699 | 8700 | 8703 |
| master | NIST_NRC_Test_14_file_1.csv | 227 | 8681 | 8700 | 8702 |
| master | NIST_NRC_Test_15_file_1.csv | 299 | 8696 | 8700 | 8711 |
| master | NIST_NRC_Test_16_file_1.csv | 177 | 8686 | 8700 | 8712 |
| master | NIST_NRC_Test_17_file_1.csv | 85 | 8698 | 8700 | 8702 |
| master | NIST_NRC_Test_18_file_1.csv | 298 | 8692 | 8700 | 8714 |


Damit ist k_exp = φ_s·m_s mit demselben φ_s, mit dem NIST m_s = ln(I₀/I)/(φ_s L) aus der Lasermessung bestimmt hat (Error-Kapitel: 8,7 m²/g). k_exp ist also die ursprünglich gemessene Größe ln(I₀/I)/L, unabhängig vom Wert von φ_s. Eine Pfadlänge geht in die Umrechnung nicht ein.


Einheiten und Modellgrößen je Datensatz (aus `columns_<variante>.csv`; DEVC-Zeilen aus den FDS-Inputs des gepinnten fds-Standes, Einheiten aus Zeile 1 der `_devc.csv` bzw. aus der Messdatei):

| Variante | Datensatz | Messspalte (Beispiel) | Einheit Messdatei | Modellspalte (Beispiel) | Einheit devc | DEVC QUANTITY | MASS_EXTINCTION_COEFFICIENT (m²/kg) | SOOT_YIELD |
|---|---|---|---|---|---|---|---|---|
| 6.11.1 | NIST/NRC | Trans. (%/m) | (no units row) | Trans | %/m | 'TRANSMISSION' | 8700 (FDS default, read.f90) |  |
| 6.11.1 | FM/FPRF Datacenter | fm… / C3H6 SF Low SF | (no units row) | FM SF3S | mg/m3 | 'DENSITY' | 8700 (FDS default, read.f90) | 0.095 |
| 6.11.1 | FM/FPRF Datacenter | fm… / Cable SF Low SF | (no units row) | FM SF3S | mg/m3 | 'DENSITY' | 8700 (FDS default, read.f90) |  |
| 6.11.1 | FAA Cargo Compartments | TestCase1… / LT_Fwd | %/m | LT_Fwd | %/m | 'TRANSMISSION' | 8700 (FDS default, read.f90) | 0.125 |
| master | NIST/NRC | Trans. (%/m) | (no units row) | Trans | %/m | 'TRANSMISSION' | 8700 (FDS default, read.f90) |  |
| master | FM/FPRF Datacenter | c3h6… / Subfloor | (no units row) | OBS FM SF3S | %/m | 'CONTROL VALUE' | 9190 | 0.095 |
| master | FM/FPRF Datacenter | cable… / Subfloor | (no units row) | OBS FM SF3S | %/m | 'CONTROL VALUE' | 4670 |  |
| master | FAA Cargo Compartments | TestCase1… / LT_Fwd | %/m | LT_Fwd | %/m | 'TRANSMISSION' | 8700 (FDS default, read.f90) | 0.126 |


FM/FPRF (master): `OBS …` ist ein CONTROL-VALUE-Device; Kette im FDS-Input: EXTINCTION COEFFICIENT → ×(−1) → EXP → 1 − … → ×100, also O = 100 (1 − e^(−K)) mit dem lokalen Extinktionskoeffizienten K am Punkt. Die Rückrechnung k = −ln(1 − O/100) ist damit exakt. Zeilen aus `Validation/FM_FPRF_Datacenter/FDS_Input_Files/FM_Datacenter_Low_C3H6_SF.fds`:


    &CTRL ID='cOBS FM SF3S',FUNCTION_TYPE='MULTIPLY',INPUT_ID='CONSTANT','om exp SF3S',CONSTANT=100/

    &CTRL ID='om exp SF3S',FUNCTION_TYPE='SUBTRACT',INPUT_ID='CONSTANT','exp SF3S',CONSTANT=1/

    &CTRL ID='exp SF3S',FUNCTION_TYPE='EXP',INPUT_ID='neg SF3S'/

    &CTRL ID='neg SF3S',FUNCTION_TYPE='MULTIPLY',INPUT_ID='CONSTANT','EC_FM SF3S',CONSTANT=-1/

    &DEVC XYZ=1.5240, 6.4008, 0.8001, QUANTITY='CONTROL VALUE',CTRL_ID='cOBS FM SF3S', ID='OBS FM SF3S',UNITS='%/m'/


Die FM-Messdateien (`c3h6_*.csv`, `cable_sf_low.csv`) haben keine Einheitenzeile; die Einheit %/m folgt aus `Dep_Title` der dataplot-Zeile (*Obscuration (%/m)*) und dem Guide-Text. Das ist eine Annahme, die im Fork nicht weiter belegbar ist.


FM-Zeilen mit Metrik *mean*: k des Mittelwerts gegenüber Mittelwert von k (1/m):

| Variante | Fall | Spalte | O_exp | O_mod | k_exp (k of mean) | k_mod (k of mean) | k_exp (mean of k) | k_mod (mean of k) | im Guide-Punktsatz |
|---|---|---|---|---|---|---|---|---|---|
| master | C3H6; Low Flow; Sub-floor | Subfloor | 57.32 | 59.46 | 0.8515 | 0.9028 | 0.8522 | 0.9731 | ja |
| master | C3H6; Low Flow; Sub-floor | HotAisle | 1.812 | 1.443 | 0.01828 | 0.01454 | 0.01839 | 0.01463 | ja |
| master | C3H6; Low Flow; Sub-floor | Ceiling | 24.15 | 7.021 | 0.2765 | 0.07279 | 0.2771 | 0.07291 | ja |
| master | C3H6; High Flow; Sub-floor | Subfloor | 71.29 | 82.69 | 1.248 | 1.754 | 1.25 | 1.929 | ja |
| master | C3H6; High Flow; Sub-floor | HotAisle | 0.4812 | 2.237 | 0.004824 | 0.02262 | 0.004839 | 0.02279 | ja |
| master | C3H6; High Flow; Sub-floor | Ceiling | 6.566 | 3.395 | 0.06791 | 0.03454 | 0.06798 | 0.0346 | ja |
| master | C3H6; Low Flow; Hot Aisle | HotAisle | 0.2046 | 2.596e-05 | 0.002048 | 2.596e-07 | 0.002049 | 2.596e-07 | nein |
| master | C3H6; Low Flow; Hot Aisle | Ceiling | 3.756 | 6.585 | 0.03828 | 0.06812 | 0.03829 | 0.06834 | ja |
| master | C3H6; High Flow; Hot Aisle | HotAisle | 1.281 | 0.1089 | 0.01289 | 0.00109 | 0.01291 | 0.001091 | ja |
| master | C3H6; High Flow; Hot Aisle | Ceiling | 2.016 | 2.294 | 0.02037 | 0.02321 | 0.02037 | 0.02325 | ja |


## 4. Statistik und Untergrenze von σ̃_M

Formeln wie im Guide (Error chapter, Gl. stdev und delta): u² = Var(ln(M/E)) mit n−1, σ̃_M² = u² − σ̃_E², δ = exp(mean ln(M/E) + σ̃_M²/2 − σ̃_E²/2), ungewichtet (`Weight_Data` = no für *Smoke Obscuration*). Untergrenze im Code:

- Python `fdsplotlib.scatplot` (6.11.1 und master, identisch): `Sigma_M = sqrt(max(0, u² − Sigma_E²))`. Es gibt **keine** Untergrenze σ̃_M ≥ σ̃_E; σ̃_E wird unverändert übernommen, σ̃_M kann bis 0 fallen. Spalten `*_code`.
- MATLAB `scatplot.m` (bis FDS 6.9, z. B. Tag FDS-6.9.1): `Sigma_E = min(u/sqrt(2), Sigma_E)` vor der Differenz, wodurch σ̃_M ≥ σ̃_E gilt; das entspricht dem Guide-Text ("σ̃_M cannot be less than σ̃_E"). Spalten `*_floor`; `sigma_E_capped` = 1 markiert Fälle, in denen die Kappung greift.

Für die Fehlerfortpflanzung je Punkt wird σ̃_E,eff² = mean(σ̃_E,i²) über die verwendeten Punkte in die Guide-Formeln eingesetzt (Erwartungswert der Varianz von ln(M/E) bei punktweise verschiedenem σ̃_E,i). Mit s = 0,07: relativ auf O: σ̃_k,i = s·O/(T·k); relativ auf T: σ̃_k,i = s/k, jeweils am Messwert.


## 5. Ergebnisse

### 5.1 Hauptergebnis: k des Kennwerts, Punktsatz des Guide, σ̃_E = fest 0,19 (Guide-Tabelle Smoke Concentration, kombiniert; gewählt) (Spalte `primary` = 1 in `stats.csv`), Code-Konvention

Die Wahl σ̃_E = 0,19 für k wurde am 2026-11-02 von M. Osburg getroffen. Es ist der kombinierte Wert, den der Guide in der Tabelle "Summary of uncertainty estimates" (Error chapter) für Smoke Concentration angibt: Messunsicherheit 0,14 und fortgepflanzte Eingangsunsicherheit (Wärmefreisetzung, Rußausbeute) 0,13. Nach der Definition des Guide ist σ̃_E dieser kombinierte Wert. Die Rauchkonzentration ist proportional zu k, und die NIST/NRC-Transmission in exp ist aus ihr berechnet (Abschnitt 3). Eine erste Wahl von 0,14 am selben Tag berücksichtigte nur die Messunsicherheit und wurde korrigiert. Die 7 % der Obscuration-Kategorie sind im Guide nicht hergeleitet; die Tabelle hat keine Zeile für Obscuration. Die übrigen Optionen in 5.2 dienen als Sensitivität.

| Variante | Datensatz | n | u (O) | σ̃_E (O) | σ̃_M (O) | δ (O) | u (k) | σ̃_E (k) | σ̃_M (k) | δ (k) | σ̃_M (k, floor) | δ (k, floor) | gekappt |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 6.11.1 | gepoolt | 33 | 0.273 | 0.07 | 0.26 | 1.24 | 0.518 | 0.19 | 0.48 | 1.70 | 0.48 | 1.70 | 0 |
| 6.11.1 | NIST/NRC | 15 | 0.286 | 0.07 | 0.28 | 1.50 | 0.519 | 0.19 | 0.48 | 2.50 | 0.48 | 2.50 | 0 |
| 6.11.1 | FAA Cargo Compartments | 18 | 0.143 | 0.07 | 0.12 | 1.04 | 0.208 | 0.19 | 0.08 | 1.10 | 0.15 | 1.12 | 1 |
| master | gepoolt | 44 | 0.710 | 0.07 | 0.71 | 1.27 | 0.870 | 0.19 | 0.85 | 1.69 | 0.85 | 1.69 | 0 |
| master | NIST/NRC | 15 | 0.287 | 0.07 | 0.28 | 1.49 | 0.523 | 0.19 | 0.49 | 2.49 | 0.49 | 2.49 | 0 |
| master | FAA Cargo Compartments | 18 | 0.546 | 0.07 | 0.54 | 1.04 | 0.614 | 0.19 | 0.58 | 1.15 | 0.58 | 1.15 | 0 |
| master | FM/FPRF Datacenter | 11 | 1.088 | 0.07 | 1.09 | 1.26 | 1.113 | 0.19 | 1.10 | 1.24 | 1.10 | 1.24 | 0 |


### 5.2 Einfluss von σ̃_E (gepoolt, k des Kennwerts, Punktsatz des Guide)

| Variante | σ̃_E-Option | n | σ̃_E,i min/median/max | σ̃_E,eff | σ̃_M (code) | δ (code) | σ̃_E (floor) | σ̃_M (floor) | δ (floor) | gekappt |
|---|---|---|---|---|---|---|---|---|---|---|
| 6.11.1 | fest 0,07 (wie Obscuration) | 33 | – | 0.07 | 0.51 | 1.75 | 0.07 | 0.51 | 1.75 | 0 |
| 6.11.1 | fest 0,08 | 33 | – | 0.08 | 0.51 | 1.75 | 0.08 | 0.51 | 1.75 | 0 |
| 6.11.1 | fest 0,14 (nur Messunsicherheit NIST/NRC) | 33 | – | 0.14 | 0.50 | 1.73 | 0.14 | 0.50 | 1.73 | 0 |
| 6.11.1 | fest 0,19 (Guide-Tabelle Smoke Concentration, kombiniert; gewählt) | 33 | – | 0.19 | 0.48 | 1.70 | 0.19 | 0.48 | 1.70 | 0 |
| 6.11.1 | Fortpflanzung je Punkt, 7 % relativ auf O | 33 | 0.07 / 0.13 / 0.47 | 0.16 | 0.49 | 1.72 | 0.16 | 0.49 | 1.72 | 0 |
| 6.11.1 | Fortpflanzung je Punkt, 7 % relativ auf T (nicht empfohlen) | 33 | 0.02 / 0.06 / 1.63 | 0.39 | 0.35 | 1.52 | 0.37 | 0.37 | 1.54 | 1 |
| master | fest 0,07 (wie Obscuration) | 44 | – | 0.07 | 0.87 | 1.74 | 0.07 | 0.87 | 1.74 | 0 |
| master | fest 0,08 | 44 | – | 0.08 | 0.87 | 1.74 | 0.08 | 0.87 | 1.74 | 0 |
| master | fest 0,14 (nur Messunsicherheit NIST/NRC) | 44 | – | 0.14 | 0.86 | 1.71 | 0.14 | 0.86 | 1.71 | 0 |
| master | fest 0,19 (Guide-Tabelle Smoke Concentration, kombiniert; gewählt) | 44 | – | 0.19 | 0.85 | 1.69 | 0.19 | 0.85 | 1.69 | 0 |
| master | Fortpflanzung je Punkt, 7 % relativ auf O | 44 | 0.07 / 0.12 / 0.47 | 0.15 | 0.86 | 1.71 | 0.15 | 0.86 | 1.71 | 0 |
| master | Fortpflanzung je Punkt, 7 % relativ auf T (nicht empfohlen) | 44 | 0.02 / 0.07 / 14.51 | 2.52 | 0.00 | 0.05 | 0.62 | 0.62 | 1.20 | 1 |


### 5.3 Alle Kombinationen je Datensatz (k, Punktsatz des Guide)

| Variante | Datensatz | k-Mittelung | σ̃_E-Option | n | u | σ̃_E,eff | σ̃_M (code) | δ (code) | σ̃_M (floor) | δ (floor) | gekappt |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 6.11.1 | gepoolt | k_of_metric | fixed_0.07 | 33 | 0.518 | 0.07 | 0.51 | 1.75 | 0.51 | 1.75 | 0 |
| 6.11.1 | gepoolt | k_of_metric | fixed_0.08 | 33 | 0.518 | 0.08 | 0.51 | 1.75 | 0.51 | 1.75 | 0 |
| 6.11.1 | gepoolt | k_of_metric | fixed_0.14 | 33 | 0.518 | 0.14 | 0.50 | 1.73 | 0.50 | 1.73 | 0 |
| 6.11.1 | gepoolt | k_of_metric | fixed_0.19 | 33 | 0.518 | 0.19 | 0.48 | 1.70 | 0.48 | 1.70 | 0 |
| 6.11.1 | gepoolt | k_of_metric | prop_relO_0.07 | 33 | 0.518 | 0.16 | 0.49 | 1.72 | 0.49 | 1.72 | 0 |
| 6.11.1 | gepoolt | k_of_metric | prop_relT_0.07 | 33 | 0.518 | 0.39 | 0.35 | 1.52 | 0.37 | 1.54 | 1 |
| 6.11.1 | NIST/NRC | k_of_metric | fixed_0.07 | 15 | 0.519 | 0.07 | 0.51 | 2.58 | 0.51 | 2.58 | 0 |
| 6.11.1 | NIST/NRC | k_of_metric | fixed_0.08 | 15 | 0.519 | 0.08 | 0.51 | 2.57 | 0.51 | 2.57 | 0 |
| 6.11.1 | NIST/NRC | k_of_metric | fixed_0.14 | 15 | 0.519 | 0.14 | 0.50 | 2.54 | 0.50 | 2.54 | 0 |
| 6.11.1 | NIST/NRC | k_of_metric | fixed_0.19 | 15 | 0.519 | 0.19 | 0.48 | 2.50 | 0.48 | 2.50 | 0 |
| 6.11.1 | NIST/NRC | k_of_metric | prop_relO_0.07 | 15 | 0.519 | 0.17 | 0.49 | 2.52 | 0.49 | 2.52 | 0 |
| 6.11.1 | NIST/NRC | k_of_metric | prop_relT_0.07 | 15 | 0.519 | 0.09 | 0.51 | 2.57 | 0.51 | 2.57 | 0 |
| 6.11.1 | FAA Cargo Compartments | k_of_metric | fixed_0.07 | 18 | 0.208 | 0.07 | 0.20 | 1.14 | 0.20 | 1.14 | 0 |
| 6.11.1 | FAA Cargo Compartments | k_of_metric | fixed_0.08 | 18 | 0.208 | 0.08 | 0.19 | 1.14 | 0.19 | 1.14 | 0 |
| 6.11.1 | FAA Cargo Compartments | k_of_metric | fixed_0.14 | 18 | 0.208 | 0.14 | 0.15 | 1.12 | 0.15 | 1.12 | 0 |
| 6.11.1 | FAA Cargo Compartments | k_of_metric | fixed_0.19 | 18 | 0.208 | 0.19 | 0.08 | 1.10 | 0.15 | 1.12 | 1 |
| 6.11.1 | FAA Cargo Compartments | k_of_metric | prop_relO_0.07 | 18 | 0.208 | 0.15 | 0.14 | 1.12 | 0.15 | 1.12 | 1 |
| 6.11.1 | FAA Cargo Compartments | k_of_metric | prop_relT_0.07 | 18 | 0.208 | 0.51 | 0.00 | 0.98 | 0.15 | 1.12 | 1 |
| master | gepoolt | k_of_metric | fixed_0.07 | 44 | 0.870 | 0.07 | 0.87 | 1.74 | 0.87 | 1.74 | 0 |
| master | gepoolt | k_of_metric | fixed_0.08 | 44 | 0.870 | 0.08 | 0.87 | 1.74 | 0.87 | 1.74 | 0 |
| master | gepoolt | k_of_metric | fixed_0.14 | 44 | 0.870 | 0.14 | 0.86 | 1.71 | 0.86 | 1.71 | 0 |
| master | gepoolt | k_of_metric | fixed_0.19 | 44 | 0.870 | 0.19 | 0.85 | 1.69 | 0.85 | 1.69 | 0 |
| master | gepoolt | k_of_metric | prop_relO_0.07 | 44 | 0.870 | 0.15 | 0.86 | 1.71 | 0.86 | 1.71 | 0 |
| master | gepoolt | k_of_metric | prop_relT_0.07 | 44 | 0.870 | 2.52 | 0.00 | 0.05 | 0.62 | 1.20 | 1 |
| master | gepoolt | mean_of_k | fixed_0.07 | 44 | 0.870 | 0.07 | 0.87 | 1.75 | 0.87 | 1.75 | 0 |
| master | gepoolt | mean_of_k | fixed_0.08 | 44 | 0.870 | 0.08 | 0.87 | 1.75 | 0.87 | 1.75 | 0 |
| master | gepoolt | mean_of_k | fixed_0.14 | 44 | 0.870 | 0.14 | 0.86 | 1.72 | 0.86 | 1.72 | 0 |
| master | gepoolt | mean_of_k | fixed_0.19 | 44 | 0.870 | 0.19 | 0.85 | 1.69 | 0.85 | 1.69 | 0 |
| master | gepoolt | mean_of_k | prop_relO_0.07 | 44 | 0.870 | 0.15 | 0.86 | 1.72 | 0.86 | 1.72 | 0 |
| master | gepoolt | mean_of_k | prop_relT_0.07 | 44 | 0.870 | 2.51 | 0.00 | 0.05 | 0.62 | 1.20 | 1 |
| master | NIST/NRC | k_of_metric | fixed_0.07 | 15 | 0.523 | 0.07 | 0.52 | 2.57 | 0.52 | 2.57 | 0 |
| master | NIST/NRC | k_of_metric | fixed_0.08 | 15 | 0.523 | 0.08 | 0.52 | 2.57 | 0.52 | 2.57 | 0 |
| master | NIST/NRC | k_of_metric | fixed_0.14 | 15 | 0.523 | 0.14 | 0.50 | 2.53 | 0.50 | 2.53 | 0 |
| master | NIST/NRC | k_of_metric | fixed_0.19 | 15 | 0.523 | 0.19 | 0.49 | 2.49 | 0.49 | 2.49 | 0 |
| master | NIST/NRC | k_of_metric | prop_relO_0.07 | 15 | 0.523 | 0.17 | 0.50 | 2.51 | 0.50 | 2.51 | 0 |
| master | NIST/NRC | k_of_metric | prop_relT_0.07 | 15 | 0.523 | 0.09 | 0.51 | 2.56 | 0.51 | 2.56 | 0 |
| master | FAA Cargo Compartments | k_of_metric | fixed_0.07 | 18 | 0.614 | 0.07 | 0.61 | 1.19 | 0.61 | 1.19 | 0 |
| master | FAA Cargo Compartments | k_of_metric | fixed_0.08 | 18 | 0.614 | 0.08 | 0.61 | 1.19 | 0.61 | 1.19 | 0 |
| master | FAA Cargo Compartments | k_of_metric | fixed_0.14 | 18 | 0.614 | 0.14 | 0.60 | 1.17 | 0.60 | 1.17 | 0 |
| master | FAA Cargo Compartments | k_of_metric | fixed_0.19 | 18 | 0.614 | 0.19 | 0.58 | 1.15 | 0.58 | 1.15 | 0 |
| master | FAA Cargo Compartments | k_of_metric | prop_relO_0.07 | 18 | 0.614 | 0.15 | 0.60 | 1.17 | 0.60 | 1.17 | 0 |
| master | FAA Cargo Compartments | k_of_metric | prop_relT_0.07 | 18 | 0.614 | 0.51 | 0.34 | 0.92 | 0.43 | 0.99 | 1 |
| master | FM/FPRF Datacenter | k_of_metric | fixed_0.07 | 11 | 1.113 | 0.07 | 1.11 | 1.28 | 1.11 | 1.28 | 0 |
| master | FM/FPRF Datacenter | k_of_metric | fixed_0.08 | 11 | 1.113 | 0.08 | 1.11 | 1.28 | 1.11 | 1.28 | 0 |
| master | FM/FPRF Datacenter | k_of_metric | fixed_0.14 | 11 | 1.113 | 0.14 | 1.10 | 1.26 | 1.10 | 1.26 | 0 |
| master | FM/FPRF Datacenter | k_of_metric | fixed_0.19 | 11 | 1.113 | 0.19 | 1.10 | 1.24 | 1.10 | 1.24 | 0 |
| master | FM/FPRF Datacenter | k_of_metric | prop_relO_0.07 | 11 | 1.113 | 0.10 | 1.11 | 1.28 | 1.11 | 1.28 | 0 |
| master | FM/FPRF Datacenter | k_of_metric | prop_relT_0.07 | 11 | 1.113 | 4.99 | 0.00 | 0.00 | 0.79 | 0.69 | 1 |
| master | FM/FPRF Datacenter | mean_of_k | fixed_0.07 | 11 | 1.123 | 0.07 | 1.12 | 1.32 | 1.12 | 1.32 | 0 |
| master | FM/FPRF Datacenter | mean_of_k | fixed_0.08 | 11 | 1.123 | 0.08 | 1.12 | 1.32 | 1.12 | 1.32 | 0 |
| master | FM/FPRF Datacenter | mean_of_k | fixed_0.14 | 11 | 1.123 | 0.14 | 1.11 | 1.30 | 1.11 | 1.30 | 0 |
| master | FM/FPRF Datacenter | mean_of_k | fixed_0.19 | 11 | 1.123 | 0.19 | 1.11 | 1.28 | 1.11 | 1.28 | 0 |
| master | FM/FPRF Datacenter | mean_of_k | prop_relO_0.07 | 11 | 1.123 | 0.10 | 1.12 | 1.31 | 1.12 | 1.31 | 0 |
| master | FM/FPRF Datacenter | mean_of_k | prop_relT_0.07 | 11 | 1.123 | 4.97 | 0.00 | 0.00 | 0.79 | 0.71 | 1 |


### 5.4 Punktauswahl: Guide-Punktsatz gegenüber allen Punkten mit endlichem positivem k (gepoolt, σ̃_E 0,07)

| Variante | k-Mittelung | Punktsatz | n | u | σ̃_M (code) | δ (code) |
|---|---|---|---|---|---|---|
| 6.11.1 | k_of_metric | guide_O | 33 | 0.518 | 0.51 | 1.75 |
| 6.11.1 | k_of_metric | all_k | 33 | 0.518 | 0.51 | 1.75 |
| master | k_of_metric | guide_O | 44 | 0.870 | 0.87 | 1.74 |
| master | k_of_metric | all_k | 45 | 1.613 | 1.61 | 3.57 |
| master | mean_of_k | guide_O | 44 | 0.870 | 0.87 | 1.75 |
| master | mean_of_k | all_k | 45 | 1.614 | 1.61 | 3.59 |


Punkte, die nur im Punktsatz `all_k` enthalten sind:

| Variante | Datensatz | Fall | Spalte | O_exp | O_mod | k_exp | k_mod |
|---|---|---|---|---|---|---|---|
| master | FM/FPRF Datacenter | C3H6; Low Flow; Hot Aisle | HotAisle | 0.2046 | 2.596e-05 | 0.002048 | 2.596e-07 |


## 6. Offene Entscheidungen

1. **σ̃_E in k**: entschieden am 2026-11-02: fest 0,19 (Begründung in 5.1; erste Wahl 0,14 korrigiert); Sensitivität 0,07 bis 0,19 und Fortpflanzung auf O in 5.2. Die Fortpflanzung relativ auf T liefert bei kleinem k sehr große σ̃_E,i und kippt ohne Untergrenze in σ̃_M = 0; sie wird nicht verwendet.
2. **Untergrenze**: Code-Konvention (keine) oder Guide-Text/MATLAB-Konvention (σ̃_M ≥ σ̃_E); unterscheidet sich nur in den mit `gekappt` = 1 markierten Zeilen.
3. **Zeitmittel (FM, master)**: k des Mittelwerts oder Mittelwert von k; Abschnitt 3 und 5.3.
4. **Punktsatz**: Punktsatz des Guide (Filter in O: Bereich `Plot_Min`…`Plot_Max`) oder alle Punkte mit endlichem k; Abschnitt 5.4.
5. **Datenstand** für das Paper: 6.11.1 (veröffentlichte Tabelle, 2 Datensätze) oder master (3 Datensätze, laufend veränderlich; hier gepinnt).
6. **Gewichtung**: ungewichtet wie im Guide für *Smoke Obscuration*; eine Bin-Gewichtung in k wäre eine neue Entscheidung.
7. **Herkunft der 7 %**: Die Unsicherheitstabelle des Error-Kapitels hat keine Zeile für Obscuration; Smoke Concentration hat 0,14 Messung, 0,13 fortgepflanzte Eingangsgrößen, 0,19 kombiniert. Die 7 % der Scatterplot-Definition (bis 6.11.0: 20 %) sind im Guide nicht hergeleitet.


## 7. Dateien

- `output/points_<variante>.csv`: alle Punkte (Datensatz, Fall, Messstelle, Metrik, T_exp, T_mod, O_exp, O_mod, k_exp, k_mod, mean-of-k, Flags).
- `output/stats.csv`, `output/stats_<variante>.csv`: Kennzahlen aller Varianten.
- `output/guide_repro_<variante>.csv`, `output/guide_repro_points_<variante>.csv`: Ausgabe des Guide-Codes.
- `output/crosscheck_<variante>.csv`: eigene Kennwerte gegen Guide-Rohwerte.
- `output/columns_<variante>.csv`: Einheiten und DEVC-Definitionen je Spalte.
- `output/provenance.json`: Commits, Daten, Paketversionen.
- `reference_table_16_1.csv`: Referenzwerte der Tabelle 16.1 (Transkription).
- `test_reproduction.py`: pytest-Prüfung der Reproduktion von 6.11.1.
