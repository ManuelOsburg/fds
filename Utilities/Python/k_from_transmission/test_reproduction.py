"""
test_reproduction.py

pytest check that the pipeline reproduces Table 16.1 of the FDS Validation Guide
6.11.1 for the smoke quantities, and that the independent metric extraction agrees
with the guide code per point.

Run from this directory with the project venv:
    python -m pytest -q test_reproduction.py

The test runs the full pipeline for variant 6.11.1 into a temporary output
directory (snapshots are cached in ./work, the guide code needs about 20 s).
"""

import csv
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))


def _read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="module")
def outdir(tmp_path_factory):
    d = str(tmp_path_factory.mktemp("k_from_transmission"))
    cmd = [sys.executable, os.path.join(HERE, "k_from_transmission.py"), "run",
           "--variant", "6.11.1", "--outdir", d, "--skip-report"]
    subprocess.run(cmd, check=True, cwd=HERE)
    return d


def test_table_16_1_reproduced(outdir):
    ref = {r["Quantity"]: r for r in _read(os.path.join(HERE, "reference_table_16_1.csv")) if r["variant"] == "6.11.1"}
    got = {r["Quantity"]: r for r in _read(os.path.join(outdir, "guide_repro_6.11.1.csv"))}
    assert set(ref) <= set(got), "missing quantities: %s" % (set(ref) - set(got))
    for q, r in ref.items():
        g = got[q]
        assert int(g["Number of Datasets"]) == int(r["Number of Datasets"]), q
        assert int(g["Number of Points"]) == int(r["Number of Points"]), q
        for key in ("Sigma_Experiment", "Sigma_Model", "Bias"):
            assert "%.2f" % float(g[key]) == "%.2f" % float(r[key]), "%s %s" % (q, key)


def test_own_metrics_match_guide_points(outdir):
    rows = _read(os.path.join(outdir, "crosscheck_6.11.1.csv"))
    assert len(rows) == 47  # 15 NIST/NRC + 18 FAA + 14 FM (6.11.1 smoke concentration)
    for r in rows:
        assert r["guide_measured"] != "", r
        # guide raw values are rounded to 4 significant figures
        assert float(r["rel_diff_measured"]) < 1e-3, r
        assert float(r["rel_diff_predicted"]) < 1e-3, r


def test_k_statistics_use_guide_point_set(outdir):
    stats = _read(os.path.join(outdir, "stats_6.11.1.csv"))
    pooled_O = [s for s in stats if s["dataset"] == "pooled" and s["space"] == "O"]
    pooled_k = [s for s in stats if s["dataset"] == "pooled" and s["space"] == "k" and s["selection"] == "guide_O"]
    assert len(pooled_O) == 1 and int(pooled_O[0]["n"]) == 33
    assert pooled_k and all(int(s["n"]) == 33 for s in pooled_k)
    assert "%.2f" % float(pooled_O[0]["sigma_M_code"]) == "0.26"
    assert "%.2f" % float(pooled_O[0]["delta_code"]) == "1.24"
