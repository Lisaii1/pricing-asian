"""Cas réel EUR/USD (P5a, étape 3) : cohérence de results/p5_eurusd.csv et p5_eurusd_sensitivity.csv.

Paramètres repris de results/p5_market.csv ; call et put asiatiques, K = S0 et K = forward 1 an,
T = 1, mensuel, N = 200 000, seed 20261117, contrôle géométrique (β optimal) + antithétique ;
européen BS fermé et MC sur les mêmes trajectoires ; coût de couverture d'un exportateur.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

import pytest

from pricer.black_scholes import bs_price

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
SEED = 20261117


def _rows(name):
    with (RESULTS / name).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _market():
    return {r["name"]: float(r["value"]) for r in _rows("p5_market.csv")}


def test_main_table_grid_and_parameters():
    m = _market()
    rows = _rows("p5_eurusd.csv")
    assert {(r["strike_type"], r["option"]) for r in rows} == {
        (k, o) for k in ("spot", "forward") for o in ("call", "put")}
    for r in rows:
        assert float(r["S0"]) == m["S0"]
        assert float(r["sigma"]) == m["sigma_ecb"]
        assert float(r["r"]) == m["r_usd"] and float(r["q"]) == m["q_eur"]
        assert float(r["K"]) == (m["S0"] if r["strike_type"] == "spot" else m["forward_1y"])
        assert (float(r["T"]), int(r["n_obs"]), int(r["n_paths"]), int(r["seed"])) == (
            1.0, 12, 200_000, SEED)
        assert (r["control"], r["beta_mode"], r["antithetic"]) == ("geometric", "optimal", "True")


def test_main_table_european_and_ratios():
    for r in _rows("p5_eurusd.csv"):
        bs = bs_price(float(r["S0"]), float(r["K"]), float(r["sigma"]), float(r["r"]),
                      float(r["T"]), float(r["q"]), r["option"])
        assert float(r["euro_bs_price"]) == pytest.approx(bs, rel=1e-14)
        se = float(r["euro_mc_std_error"])
        assert abs(float(r["euro_mc_price"]) - bs) < 4 * se          # MC européen vs fermé
        assert float(r["ratio_asian_euro_bs"]) == pytest.approx(
            float(r["asian_price"]) / bs, rel=1e-12)
        assert float(r["asian_pct_S0"]) == pytest.approx(
            100 * float(r["asian_price"]) / float(r["S0"]), rel=1e-12)
        assert float(r["asian_price"]) < bs                         # moyenne moins volatile


def test_asian_put_call_parity_within_error():
    """C − P = e^{−rT}(E[A] − K), E[A] = (1/n) Σ_k S0·e^{(r−q)t_k}, t_k = k/12."""
    rows = {(r["strike_type"], r["option"]): r for r in _rows("p5_eurusd.csv")}
    for k in ("spot", "forward"):
        c, p = rows[(k, "call")], rows[(k, "put")]
        S0, K, r, q = (float(c[x]) for x in ("S0", "K", "r", "q"))
        ea = sum(S0 * math.exp((r - q) * j / 12) for j in range(1, 13)) / 12
        rhs = math.exp(-r) * (ea - K)
        lhs = float(c["asian_price"]) - float(p["asian_price"])
        tol = 4 * math.hypot(float(c["asian_std_error"]), float(p["asian_std_error"]))
        assert abs(lhs - rhs) < tol


def test_hedge_cost_formula_for_exporter_calls():
    for r in _rows("p5_eurusd.csv"):
        if r["option"] != "call":
            assert r["hedge_cost_eur"] == ""
            continue
        notional_eur = 12 * 1_000_000 / float(r["K"])
        assert float(r["notional_eur"]) == pytest.approx(notional_eur, rel=1e-14)
        usd = float(r["asian_price"]) * notional_eur
        assert float(r["hedge_cost_usd"]) == pytest.approx(usd, rel=1e-12)
        assert float(r["hedge_cost_eur"]) == pytest.approx(usd / float(r["S0"]), rel=1e-12)
        assert "illustrati" in r["notional_note"]
        assert r["hedge_cost_formula"]


def test_sensitivity_sigmas_and_ratios():
    m = _market()
    rows = _rows("p5_eurusd_sensitivity.csv")
    sigmas = sorted({float(r["sigma"]) for r in rows})
    assert sigmas == sorted([0.04, 0.05, m["sigma_ecb"], 0.06, 0.07, 0.08])
    assert {r["sigma_label"] for r in rows if float(r["sigma"]) == m["sigma_ecb"]} == {"mesuré"}
    assert len(rows) == 6 * 2 * 2
    for r in rows:
        bs = bs_price(m["S0"], float(r["K"]), float(r["sigma"]), m["r_usd"], 1.0, m["q_eur"],
                      r["option"])
        assert float(r["euro_bs_price"]) == pytest.approx(bs, rel=1e-14)
        assert float(r["ratio_asian_euro_bs"]) == pytest.approx(float(r["asian_price"]) / bs,
                                                               rel=1e-12)
    for k in ("spot", "forward"):                   # prix croissant en σ (vega > 0)
        for o in ("call", "put"):
            prices = [float(r["asian_price"]) for r in sorted(
                (r for r in rows if r["strike_type"] == k and r["option"] == o),
                key=lambda r: float(r["sigma"]))]
            assert prices == sorted(prices)


def test_measured_sigma_rows_match_main_table():
    main = {(r["strike_type"], r["option"]): r for r in _rows("p5_eurusd.csv")}
    for r in _rows("p5_eurusd_sensitivity.csv"):
        if r["sigma_label"] == "mesuré":
            assert float(r["asian_price"]) == float(main[(r["strike_type"], r["option"])][
                "asian_price"])
