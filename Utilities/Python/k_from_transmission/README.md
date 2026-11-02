# k_from_transmission

Re-expresses the *Smoke Obscuration* validation data of the FDS Validation Guide in
terms of the light extinction coefficient k (1/m) and recomputes the guide's model
statistics (bias factor δ, relative model standard deviation σ̃_M) for k, using the
guide's own formulas and data. The guide itself is not modified.

## Requirements

* Local clones of `firemodels/fds` (this fork), `firemodels/exp` and `firemodels/out`
  side by side (`../exp`, `../out` relative to the fds clone). Partial/sparse clones
  are sufficient as long as the pinned commits (`pins.json`) are reachable; only the
  folders `NIST_NRC`, `FAA_Cargo_Compartments`, `FM_FPRF_Datacenter` are read.
* Python ≥ 3.10 with `numpy<2`, `pandas<3`, `matplotlib`, `scipy`, `pytest`
  (see `output/provenance.json` for the versions used).

## Usage

```
python k_from_transmission.py run                 # both variants, writes output/ and REPORT.md
python k_from_transmission.py run --variant 6.11.1
python -m pytest -q test_reproduction.py          # checks the reproduction of Table 16.1 (6.11.1)
```

Snapshots of the pinned commits are extracted with `git archive` into `work/`
(ignored by git); the clones of exp/out are never modified.

## Files

| file | content |
|---|---|
| `pins.json` | pinned commits of fds/exp/out for the variants `6.11.1` and `master` |
| `k_from_transmission.py` | pipeline (snapshot, guide reproduction, conversion, statistics, report) |
| `guide_repro.py` | runs `fdsplotlib.dataplot`/`scatplot` of the pinned fds commit (subprocess) |
| `write_report.py` | generates `REPORT.md` from the output files |
| `reference_table_16_1.csv` | Table 16.1 values of the guide 6.11.1 (transcribed) |
| `test_reproduction.py` | pytest |
| `k_scatter.py` | guide-style scatter plots (obscuration and k) with the pinned `fdsplotlib.scatplot`, separate output directory; writes `output/figures/` and `output/k_scatter_stats_<variant>.csv` |
| `check_baseline_floor.py` | lists guide categories with σ̃_M < σ̃_E in the baseline statistics file; writes `output/baseline_sigma_check.csv` |
| `output/` | CSV results, `provenance.json`, scatter plots in `output/figures/` |
| `REPORT.md` | report (German) |
