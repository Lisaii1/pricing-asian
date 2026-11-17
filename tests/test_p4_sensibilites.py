"""Sensibilités de l'estimateur (P4, étape 3) : biais de β, méthode d'aléa, fréquence
d'observation, grille K × T avec contrôle.

Ajouts testés dans src/ :
  - rng_method = "inverse_hastings" : transformée inverse avec Φ^{-1} de Hastings (slide 24),
    accessible au pricer (jusqu'ici seulement via normals(..., precision="hastings")).
  - geometric_asian_continuous_price : limite n → ∞ de la formule discrète (σ_G² → σ²T/3,
    t̄ → T/2 ; Kemna-Vorst, hors cours).
Puis cohérence des CSV versionnés de results/ produits par scripts/p4_sensibilites.py.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np
import pytest

from pricer.asian import price_asian
from pricer.black_scholes import bs_price
from pricer.geometric import geometric_asian_continuous_price, geometric_asian_price
from pricer.normals import normals
from pricer.paths import RNG_METHODS, NormalStream

SEED = 20261117
BASE = dict(S0=100.0, K=100.0, sigma=0.20, r=0.03, T=1.0, q=0.01)
MODEL = dict(S0=100.0, sigma=0.25, r=0.05, T=1.5, q=0.02)
RESULTS = Path(__file__).resolve().parents[1] / "results"


def _rows(name):
    with (RESULTS / name).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


# --- Hastings dans le flux du pricer --------------------------------------------------------------

def test_rng_methods_include_hastings():
    assert RNG_METHODS == ("inverse", "box_muller", "polar", "acceptance_rejection",
                           "inverse_hastings")


def test_hastings_stream_matches_normals_with_hastings_precision():
    s = NormalStream(SEED, "inverse_hastings")
    z = np.concatenate([s.take(7), s.take(1_000), s.take(3)])
    ref = normals(1_010, "inverse", seed=SEED, precision="hastings").z
    assert np.array_equal(z, ref)
    assert s.n_uniforms == 1_010


def test_hastings_and_as241_use_same_uniforms_and_differ_by_less_than_1e_3():
    za = NormalStream(SEED, "inverse").take(50_000)
    zh = NormalStream(SEED, "inverse_hastings").take(50_000)
    assert 0.0 < np.max(np.abs(za - zh)) < 1e-3          # cours : erreur de Hastings 4,5e−4


def test_price_asian_with_hastings():
    res = price_asian(**BASE, n_paths=20_000, rng_method="inverse_hastings", control="geometric")
    ref = price_asian(**BASE, n_paths=20_000, control="geometric")
    assert res.rng_method == "inverse_hastings" and res.n_uniforms == 20_000 * 12
    assert res.price != ref.price
    assert abs(res.price - ref.price) < 3 * ref.std_error + 1e-3


def test_unknown_rng_method_still_rejected():
    with pytest.raises(ValueError):
        NormalStream(SEED, "hastings")


# --- limite continue de l'asiatique géométrique ---------------------------------------------------

@pytest.mark.parametrize("option", ["call", "put"])
def test_continuous_geometric_is_limit_of_discrete(option):
    cont = geometric_asian_continuous_price(**MODEL, K=105.0, option=option)
    errs = [abs(geometric_asian_price(**MODEL, K=105.0, option=option, obs=n) - cont)
            for n in (250, 500, 1_000, 2_000)]
    assert errs[-1] < 5e-3            # erreur ≈ 6/n ici (mesuré : 3,0e−3 à n = 2 000)
    for a, b in zip(errs, errs[1:]):                        # erreur en O(1/n)
        assert a / b == pytest.approx(2.0, rel=0.05)


def test_continuous_geometric_closed_form_by_hand():
    S0, K, s, r, T, q = 100.0, 95.0, 0.3, 0.04, 2.0, 0.01
    mu = math.log(S0) + (r - q - 0.5 * s * s) * T / 2
    v = s * s * T / 3
    d2 = (mu - math.log(K)) / math.sqrt(v)
    d1 = d2 + math.sqrt(v)

    def Phi(x):
        return 0.5 * math.erfc(-x / math.sqrt(2))

    call = math.exp(-r * T) * (math.exp(mu + v / 2) * Phi(d1) - K * Phi(d2))
    assert geometric_asian_continuous_price(S0, K, s, r, T, q, "call") == pytest.approx(
        call, rel=1e-13)


def test_continuous_geometric_put_call_parity():
    c = geometric_asian_continuous_price(**MODEL, K=100.0, option="call")
    p = geometric_asian_continuous_price(**MODEL, K=100.0, option="put")
    S0, s, r, T, q = MODEL["S0"], MODEL["sigma"], MODEL["r"], MODEL["T"], MODEL["q"]
    fwd = S0 * math.exp((r - q - 0.5 * s * s) * T / 2 + s * s * T / 6)
    assert c - p == pytest.approx(math.exp(-r * T) * (fwd - 100.0), rel=1e-12)


# --- CSV -----------------------------------------------------------------------------------------

def test_beta_bias_csv():
    rows = _rows("p4_beta_bias.csv")
    assert {r["beta_mode"] for r in rows} == {"optimal", "pilot"}
    runs = _rows("p4_beta_bias_runs.csv")
    for r in rows:
        assert int(r["n_seeds"]) == 500 and int(r["n_paths"]) == 1_000
        prices = np.array([float(x["price"]) for x in runs if x["beta_mode"] == r["beta_mode"]])
        assert prices.size == 500
        assert float(r["mean_price"]) == pytest.approx(prices.mean(), rel=1e-12)
        sd_mean = prices.std(ddof=1) / math.sqrt(500)
        assert float(r["sd_of_mean"]) == pytest.approx(sd_mean, rel=1e-10)
        assert float(r["bias"]) == pytest.approx(prices.mean() - float(r["ref_price"]), abs=1e-14)
    # seeds : saut exact sur un flux unique (P5a, étape 0), voir
    # test_beta_bias_runs_use_disjoint_jumped_streams


def test_p4_csv_values_have_no_numpy_repr():
    """repr(np.float64) écrit « np.float64(…) » (NumPy 2) : aucune cellule ne doit en contenir."""
    bad = [(p.name, k) for p in sorted(RESULTS.glob("p4_*.csv"))
           for r in _rows(p.name) for k, v in r.items() if v and v.startswith("np.")]
    assert bad == []


def test_beta_bias_ratios_are_bias_over_spreads():
    for r in _rows("p4_beta_bias.csv"):
        sd, ref_se = float(r["sd_of_mean"]), float(r["ref_std_error"])
        assert float(r["bias_in_sd_of_mean"]) == pytest.approx(float(r["bias"]) / sd, rel=1e-12)
        assert float(r["bias_in_combined_se"]) == pytest.approx(
            float(r["bias"]) / math.hypot(sd, ref_se), rel=1e-12)


def test_rng_methods_csv():
    rows = _rows("p4_rng_methods.csv")
    assert {r["rng_method"] for r in rows} == set(RNG_METHODS)
    assert {r["control"] for r in rows} == {"", "geometric"}
    for r in rows:
        assert int(r["n_paths"]) == 200_000


def test_frequency_csv():
    rows = _rows("p4_frequency.csv")
    assert {int(r["n_obs"]) for r in rows} == {1, 4, 12, 52, 252}
    for r in rows:
        K, opt = float(r["K"]), r["option"]
        assert float(r["geometric_exact"]) == pytest.approx(
            geometric_asian_price(100.0, K, 0.20, 0.03, 1.0, 0.01, opt, obs=int(r["n_obs"])),
            rel=1e-14)
        assert float(r["geometric_continuous"]) == pytest.approx(
            geometric_asian_continuous_price(100.0, K, 0.20, 0.03, 1.0, 0.01, opt), rel=1e-14)
        if int(r["n_obs"]) == 1:      # une seule date : A = G = S_T, l'asiatique est l'européen
            bs = bs_price(100.0, K, 0.20, 0.03, 1.0, 0.01, opt)
            assert float(r["geometric_exact"]) == pytest.approx(bs, rel=1e-12)
            assert float(r["price"]) == pytest.approx(bs, rel=1e-12)


def test_grid_cv_csv():
    rows = _rows("p4_grid_cv.csv")
    assert len(rows) == 5 * 4 * 2
    for r in rows:
        bs = float(r["euro_bs_price"])
        assert bs == bs_price(100.0, float(r["K"]), 0.20, 0.03, float(r["T"]), 0.01, r["option"])
        assert float(r["ratio"]) == pytest.approx(float(r["price"]) / bs, rel=1e-12)
        assert float(r["ratio_ci_low"]) == pytest.approx(float(r["ci_low"]) / bs, rel=1e-12)
        assert float(r["ratio_ci_high"]) == pytest.approx(float(r["ci_high"]) / bs, rel=1e-12)


# --- P5a étape 0 : 500 runs sur flux LCG disjoints (saut exact) -----------------------------------

def test_beta_bias_runs_use_disjoint_jumped_streams():
    """Run i démarre à l'état a^(i·M)·x0 mod m, M = uniformes consommées par run ; la référence
    démarre après tous les runs des deux modes ; aucun état n'est réutilisé (balayage vérifié)."""
    from pricer.rng import state_after
    rows = {r["beta_mode"]: r for r in _rows("p4_beta_bias.csv")}
    runs = _rows("p4_beta_bias_runs.csv")
    m_max = max(int(r["n_uniforms_per_run"]) for r in rows.values())
    for mode, r in rows.items():
        M = int(r["n_uniforms_per_run"])
        assert M == 12 * (1_000 + int(r["n_pilot"]))          # 1 uniforme par normale (AS241)
        seeds = [int(x["seed"]) for x in runs if x["beta_mode"] == mode]
        assert seeds == [state_after(SEED, i * M) for i in range(500)]
        assert int(r["stream_x0"]) == SEED
        assert int(r["n_seed_pairs_overlapping"]) == 0
        assert int(r["n_seeds_overlapping_ref"]) == 0
        assert int(r["ref_offset_uniforms"]) == 500 * m_max
        assert int(r["ref_seed"]) == state_after(SEED, 500 * m_max)
        total = 500 * m_max + int(r["ref_n_paths"]) * 12
        assert int(r["stream_states_scanned"]) == total
        assert r["first_return_of_x0"] == ""                   # x0 ne revient pas : pas de cycle
