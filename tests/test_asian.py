"""Pricer Monte-Carlo : asiatique arithmétique (slide 39) et européen (slides 43-44).

Tolérances statistiques = 3 écarts-types de l'estimateur (jamais une tolérance absolue
arbitraire). Seeds fixées : les tests sont déterministes.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from pricer.asian import MCResult, Z_95, price_asian, price_european_mc
from pricer.black_scholes import bs_price
from pricer.paths import gbm_paths, n_obs_from

SEED = 20261117
BASE = dict(S0=100.0, K=100.0, sigma=0.20, r=0.03, T=1.0, q=0.01)

MC_CASES = [  # 3 jeux, dont q > 0
    dict(S0=100.0, K=100.0, sigma=0.20, r=0.03, T=1.0, q=0.01),
    dict(S0=42.0, K=40.0, sigma=0.20, r=0.10, T=0.5, q=0.0),
    dict(S0=100.0, K=120.0, sigma=0.35, r=0.05, T=2.0, q=0.04),
]


def _expected_average(S0, r, q, T, obs, include_s0=False):
    """E[A] = (1/n)Σ S0 e^{(r−q)t_k}, t_k = k·T/n écrit ici indépendamment de obs_dates."""
    n = n_obs_from(obs, T)
    k = np.arange(0 if include_s0 else 1, n + 1)
    return float(np.mean(S0 * np.exp((r - q) * k * T / n)))


# --- objet résultat -------------------------------------------------------------------------

def test_result_fields_and_ci():
    res = price_asian(**BASE, n_paths=10_000)
    assert isinstance(res, MCResult)
    assert res.n_paths == 10_000 and res.seed == SEED and res.rng_method == "inverse"
    assert res.n_obs == 12 and res.option == "call" and res.kind == "asian"
    assert res.elapsed > 0.0
    assert res.std_error > 0.0
    assert res.ci_low == res.price - Z_95 * res.std_error
    assert res.ci_high == res.price + Z_95 * res.std_error
    assert Z_95 == 1.96
    assert res.n_uniforms == 10_000 * 12      # inverse : 1 uniforme par normale


def test_std_error_is_sample_std_over_sqrt_n():
    """Écart-type de l'estimateur = s/√N avec s² en 1/(N − 1) (slide 49)."""
    p = dict(BASE, T=0.5)
    res = price_asian(**p, obs=6, n_paths=5_000, batch_size=1_234)
    S = np.concatenate(list(gbm_paths(p["S0"], p["sigma"], p["r"], p["T"], p["q"], obs=6,
                                      n_paths=5_000, seed=SEED)))
    pay = math.exp(-p["r"] * p["T"]) * np.maximum(S.mean(axis=1) - p["K"], 0.0)
    assert res.price == pytest.approx(pay.mean(), rel=1e-13)
    assert res.std_error == pytest.approx(pay.std(ddof=1) / math.sqrt(5_000), rel=1e-11)


def test_control_reserved_for_p3():
    with pytest.raises(NotImplementedError):
        price_asian(**BASE, n_paths=100, control="geometric")
    with pytest.raises(NotImplementedError):
        price_european_mc(**BASE, n_paths=100, control="geometric")


@pytest.mark.parametrize("bad", [dict(option="digital"), dict(K=0.0), dict(n_paths=1),
                                 dict(seed=None), dict(rng_method="mersenne")])
def test_invalid_inputs_raise(bad):
    kw = dict(BASE, n_paths=100)
    kw.update(bad)
    with pytest.raises((ValueError, TypeError)):
        price_asian(**kw)


# --- européen MC contre la formule fermée ------------------------------------------------------

@pytest.mark.parametrize("case", MC_CASES)
@pytest.mark.parametrize("option", ["call", "put"])
def test_european_mc_within_3_std_of_bs(case, option):
    res = price_european_mc(**case, option=option, n_paths=200_000)
    ref = bs_price(**case, option=option)
    assert abs(res.price - ref) < 3 * res.std_error
    assert res.kind == "european"


# --- asiatique ---------------------------------------------------------------------------------

@pytest.mark.parametrize("option", ["call", "put"])
def test_asian_one_observation_equals_european_bitwise(option):
    a = price_asian(**BASE, option=option, obs=1, n_paths=20_000, batch_size=7_000)
    e = price_european_mc(**BASE, option=option, obs=1, n_paths=20_000, batch_size=7_000)
    assert a.price == e.price
    assert a.std_error == e.std_error


@pytest.mark.parametrize("obs,include_s0", [("monthly", False), ("weekly", False),
                                            (4, True), ("quarterly", False)])
@pytest.mark.parametrize("case", MC_CASES)
def test_asian_put_call_parity(case, obs, include_s0):
    """C − P = e^{−rT}·(Ā − K) trajectoire par trajectoire, donc avec la même seed
    C_MC − P_MC = e^{−rT}(moyenne des A − K) ; et E[A] = (1/n)Σ S0 e^{(r−q)t_k}."""
    kw = dict(case, obs=obs, include_s0=include_s0, n_paths=50_000)
    c = price_asian(**kw, option="call")
    p = price_asian(**kw, option="put")
    S = np.concatenate(list(gbm_paths(case["S0"], case["sigma"], case["r"], case["T"],
                                      case["q"], obs=obs, n_paths=50_000, seed=SEED,
                                      include_s0=include_s0)))
    A = S.mean(axis=1)
    disc = math.exp(-case["r"] * case["T"])
    # identité algébrique (même tirage) : à la précision machine près
    assert c.price - p.price == pytest.approx(disc * (A.mean() - case["K"]), abs=1e-10 * case["S0"])
    # espérance : à 3 écarts-types de l'estimateur de e^{−rT}·Ā
    EA = _expected_average(case["S0"], case["r"], case["q"], case["T"], obs, include_s0)
    se = disc * A.std(ddof=1) / math.sqrt(A.size)
    assert abs((c.price - p.price) - disc * (EA - case["K"])) < 3 * se


@pytest.mark.parametrize("K", [90.0, 100.0, 110.0])
def test_asian_zero_vol_limit(K):
    """σ → 1e−8 : A ≈ E[A], donc prix = e^{−rT}·max(E[A] − K, 0) (et put symétrique)."""
    p = dict(BASE, K=K, sigma=1e-8)
    EA = _expected_average(p["S0"], p["r"], p["q"], p["T"], "monthly")
    disc = math.exp(-p["r"] * p["T"])
    c = price_asian(**p, option="call", n_paths=10_000)
    pu = price_asian(**p, option="put", n_paths=10_000)
    assert abs(c.price - disc * max(EA - K, 0.0)) <= 3 * c.std_error + 1e-12 * p["S0"]
    assert abs(pu.price - disc * max(K - EA, 0.0)) <= 3 * pu.std_error + 1e-12 * p["S0"]


def test_asian_cheaper_than_european_atm():
    """Moyenne arithmétique : variance plus faible que S_T, call asiatique < call européen ATM."""
    a = price_asian(**BASE, n_paths=50_000)
    assert a.price + 3 * a.std_error < bs_price(**BASE)


def test_reproducible_same_seed_bitwise():
    a = price_asian(**BASE, n_paths=30_000)
    b = price_asian(**BASE, n_paths=30_000)
    assert a.price == b.price and a.std_error == b.std_error


def test_batch_size_changes_only_summation_order():
    """Mêmes trajectoires quel que soit batch_size ; seul l'ordre de sommation change."""
    a = price_asian(**BASE, n_paths=30_000, batch_size=50_000)
    b = price_asian(**BASE, n_paths=30_000, batch_size=777)
    assert a.price == pytest.approx(b.price, rel=1e-12)
    assert a.std_error == pytest.approx(b.std_error, rel=1e-10)


def test_other_seed_changes_price():
    a = price_asian(**BASE, n_paths=5_000, seed=SEED)
    b = price_asian(**BASE, n_paths=5_000, seed=SEED + 1)
    assert a.price != b.price


@pytest.mark.parametrize("method", ["box_muller", "polar", "acceptance_rejection"])
def test_other_rng_methods_agree_within_3_std(method):
    ref = price_asian(**BASE, n_paths=100_000)
    res = price_asian(**BASE, n_paths=100_000, rng_method=method)
    assert res.rng_method == method
    assert abs(res.price - ref.price) < 3 * math.hypot(res.std_error, ref.std_error)
