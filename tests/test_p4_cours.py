"""Exercices du cours reproduits (P4, étape 1) : slides 77 (asiatique, contrôle géométrique) et 78
(européen, antithétique). Les tests portent sur les CSV versionnés de results/ produits par
scripts/p4_cours.py : cohérence avec les formules fermées, reproductibilité d'une ligne, couverture
des IC à 99 %.

Couverture (prompt P4) : la référence (prix exact BS pour le slide 78, contrôle à N = 4 000 000 pour
le slide 77) doit tomber dans l'IC à 99 % de l'estimateur dans au moins 97 % des cases. Si ce n'est
pas le cas, on le rapporte ; on n'ajuste rien.
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from pricer.asian import price_asian, price_european_mc, z_value
from pricer.black_scholes import bs_price
from pricer.geometric import geometric_asian_price

RESULTS = Path(__file__).resolve().parents[1] / "results"
EX77 = RESULTS / "p4_ex77.csv"
EX78 = RESULTS / "p4_ex78.csv"


def _rows(path):
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _f(row, key):
    return float(row[key])


@pytest.fixture(scope="module")
def ex77():
    return _rows(EX77)


@pytest.fixture(scope="module")
def ex78():
    return _rows(EX78)


# --- slide 77 ------------------------------------------------------------------------------------

def test_ex77_grid_and_parameters(ex77):
    assert len(ex77) == 10
    assert {(r["option"], _f(r, "K")) for r in ex77} == {
        (o, k) for o in ("call", "put") for k in (30.0, 40.0, 50.0, 60.0, 70.0)}
    for r in ex77:
        assert (_f(r, "S0"), _f(r, "T"), _f(r, "sigma"), _f(r, "r"), _f(r, "q")) == (
            50.0, 0.25, 0.20, 0.03, 0.0)
        assert int(r["obs_per_year"]) == 252 and int(r["n_obs"]) == 63
        assert int(r["n_paths"]) == 100_000 and int(r["seed"]) == 20261117
        assert int(r["ref_n_paths"]) == 4_000_000
        assert _f(r, "confidence") == 0.99 and _f(r, "z") == z_value(0.99)


def test_ex77_geometric_exact_is_closed_form(ex77):
    for r in ex77:
        expected = geometric_asian_price(50.0, _f(r, "K"), 0.20, 0.03, 0.25, 0.0, r["option"],
                                         obs=63)
        assert _f(r, "geometric_exact") == pytest.approx(expected, rel=1e-14, abs=1e-300)


def test_ex77_ci99_columns_are_price_pm_z_se(ex77):
    z = z_value(0.99)
    for r in ex77:
        for p in ("mc", "cv", "ref"):
            assert _f(r, f"{p}_ci99_low") == pytest.approx(
                _f(r, f"{p}_price") - z * _f(r, f"{p}_std_error"), abs=1e-12)
            assert _f(r, f"{p}_ci99_high") == pytest.approx(
                _f(r, f"{p}_price") + z * _f(r, f"{p}_std_error"), abs=1e-12)


def test_ex77_row_is_reproducible():
    """La ligne call K = 50 se recalcule au bit près (N = 100 000, seed de référence)."""
    row = next(r for r in _rows(EX77) if r["option"] == "call" and _f(r, "K") == 50.0)
    kw = dict(S0=50.0, K=50.0, sigma=0.20, r=0.03, T=0.25, q=0.0, option="call", obs="daily",
              n_paths=100_000, seed=20261117, confidence=0.99)
    mc = price_asian(**kw)
    cv = price_asian(**kw, control="geometric")
    assert repr(mc.price) == row["mc_price"] and repr(cv.price) == row["cv_price"]
    assert repr(cv.corr) == row["corr"] and repr(cv.beta) == row["cv_beta"]


# --- slide 78 ------------------------------------------------------------------------------------

def test_ex78_grid_and_parameters(ex78):
    assert len(ex78) == 18
    assert {(r["option"], _f(r, "K"), int(r["n_paths"])) for r in ex78} == {
        (o, k, n) for o in ("call", "put") for k in (90.0, 100.0, 110.0)
        for n in (1_000, 10_000, 100_000)}
    for r in ex78:
        assert (_f(r, "S0"), _f(r, "T"), _f(r, "sigma"), _f(r, "r"), _f(r, "q")) == (
            100.0, 1.0, 0.30, 0.05, 0.07)
        assert int(r["n_obs"]) == 1 and int(r["seed"]) == 20261117


def test_ex78_exact_is_black_scholes(ex78):
    for r in ex78:
        assert _f(r, "price_exact") == bs_price(100.0, _f(r, "K"), 0.30, 0.05, 1.0, 0.07,
                                                r["option"])


def test_ex78_variances_are_consistent(ex78):
    for r in ex78:
        n = int(r["n_paths"])
        assert _f(r, "mc_variance") == pytest.approx(_f(r, "mc_std_error") ** 2 * n, rel=1e-12)
        assert _f(r, "anti_variance") == pytest.approx(
            _f(r, "anti_std_error") ** 2 * (n // 2), rel=1e-12)
        assert -1.0 <= _f(r, "antithetic_corr") < 0.0


def test_ex78_row_is_reproducible_with_same_seed():
    row = next(r for r in _rows(EX78)
               if r["option"] == "put" and _f(r, "K") == 100.0 and int(r["n_paths"]) == 1_000)
    kw = dict(S0=100.0, K=100.0, sigma=0.30, r=0.05, T=1.0, q=0.07, option="put", obs=1,
              n_paths=1_000, seed=20261117, confidence=0.99)
    mc = price_european_mc(**kw)
    anti = price_european_mc(**kw, antithetic=True)
    assert repr(mc.price) == row["mc_price"] and repr(anti.price) == row["anti_price"]
    assert repr(anti.antithetic_corr) == row["antithetic_corr"]


# --- couverture des IC à 99 % --------------------------------------------------------------------

def test_reference_in_ci99_in_at_least_97_percent_of_cases(ex77, ex78):
    cases = []
    for r in ex77:
        ref = _f(r, "ref_price")
        for p in ("mc", "cv"):
            cases.append(_f(r, f"{p}_ci99_low") <= ref <= _f(r, f"{p}_ci99_high"))
    for r in ex78:
        ref = _f(r, "price_exact")
        for p in ("mc", "anti"):
            cases.append(_f(r, f"{p}_ci99_low") <= ref <= _f(r, f"{p}_ci99_high"))
    assert len(cases) == 56
    assert sum(cases) / len(cases) >= 0.97, f"{len(cases) - sum(cases)} cases hors IC 99 %"
