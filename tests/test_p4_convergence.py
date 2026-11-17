"""Convergence, nombre de simulations nécessaire, comparaison à temps égal (P4, étape 2).

Fonctions d'analyse de scripts/p4_convergence.py testées sur des cas synthétiques exacts, puis
cohérence des CSV versionnés (results/p4_convergence.csv, p4_convergence_slopes.csv,
p4_n_required.csv, p4_equal_time.csv).
"""
from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from p4_convergence import (ESTIMATORS, largest_n_within_budget, log_grid,  # noqa: E402
                            loglog_slope, n_required)
from pricer.asian import z_value  # noqa: E402

RESULTS = ROOT / "results"


def _rows(name):
    with (RESULTS / name).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


# --- fonctions -----------------------------------------------------------------------------------

def test_log_grid_has_13_even_points_from_1e3_to_1e6():
    g = log_grid(1_000, 1_000_000, 13)
    assert len(g) == 13 and g[0] == 1_000 and g[-1] == 1_000_000
    assert all(n % 2 == 0 for n in g)                      # antithétique : N pair
    assert all(b > a for a, b in zip(g, g[1:]))
    ratios = np.diff(np.log10(g))
    assert np.allclose(ratios, 0.25, atol=1e-3)             # pas de 10^0,25


@pytest.mark.parametrize("p", [-0.5, -1.0, 0.3])
def test_loglog_slope_recovers_power_law(p):
    n = np.array([1e3, 1e4, 1e5, 1e6])
    slope, intercept = loglog_slope(n, 3.7 * n**p)
    assert slope == pytest.approx(p, abs=1e-12)
    assert intercept == pytest.approx(math.log(3.7), abs=1e-12)


def test_n_required_formula():
    z = z_value(0.95)
    assert n_required(2.0, 0.01, z) == math.ceil((z * 2.0 / 0.01) ** 2)


def test_n_required_answers_ds_question():
    """DS 2024-2025 : marge ±0,1 à 95 % avec 1 000 simulations → ±0,01 demande 100 000."""
    z = z_value(0.95)
    sigma = 0.1 * math.sqrt(1_000) / z
    assert n_required(sigma, 0.01, z) == 100_000


def test_largest_n_within_budget_with_deterministic_timer():
    def run(n):                       # temps simulé : 2 µs par trajectoire + 0,01 s fixe
        return n, 0.01 + 2e-6 * n
    best = largest_n_within_budget(run, budget=2.0, n_start=10_000, even=True)
    n, elapsed = best["n_paths"], best["time_s"]
    assert elapsed <= 2.0 and n % 2 == 0
    assert n >= 0.97 * (2.0 - 0.01) / 2e-6                   # à 3 % du maximum exact


# --- CSV -----------------------------------------------------------------------------------------

def test_convergence_csv():
    rows = _rows("p4_convergence.csv")
    assert len(rows) == 13 * len(ESTIMATORS)
    z = z_value(0.95)
    for r in rows:
        assert float(r["half_width_95"]) == pytest.approx(z * float(r["std_error"]), rel=1e-12)
        assert (float(r["K"]), float(r["T"]), r["option"]) == (100.0, 1.0, "call")
    for est in ESTIMATORS:
        hw = [float(r["half_width_95"]) for r in rows if r["estimator"] == est]
        assert hw[0] > hw[-1]                                 # la marge diminue avec N


def test_slopes_csv_matches_convergence_points():
    conv = _rows("p4_convergence.csv")
    for s in _rows("p4_convergence_slopes.csv"):
        pts = [r for r in conv if r["estimator"] == s["estimator"]]
        slope, _ = loglog_slope(np.array([float(r["n_paths"]) for r in pts]),
                                np.array([float(r["half_width_95"]) for r in pts]))
        assert float(s["slope"]) == pytest.approx(slope, rel=1e-12)
        assert float(s["slope_minus_expected"]) == pytest.approx(slope + 0.5, abs=1e-12)


def test_n_required_csv():
    rows = _rows("p4_n_required.csv")
    assert len(rows) == 2 * len(ESTIMATORS)
    for r in rows:
        assert int(r["sigma_hat_n_paths"]) == 100_000
        n = n_required(float(r["sigma_hat"]), float(r["epsilon"]), float(r["z"]))
        if r["estimator"] in ("antithetic", "antithetic_control"):
            n += n % 2
        assert int(r["n_required"]) == n


def test_equal_time_csv():
    rows = _rows("p4_equal_time.csv")
    assert len(rows) == 3 * len(ESTIMATORS)
    for r in rows:
        assert float(r["time_s"]) <= float(r["budget_s"])
