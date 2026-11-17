"""Formule fermée de Black-Scholes avec dividende continu q (cours, slides 43-44).

SciPy sert uniquement de référence ici (autorisé dans tests/).
"""
from __future__ import annotations

import math

import numpy as np
import pytest
from scipy import stats

from pricer.black_scholes import bs_price, norm_cdf

CASES = [  # (S0, K, sigma, r, T, q)
    (100.0, 100.0, 0.20, 0.03, 1.0, 0.01),
    (42.0, 40.0, 0.20, 0.10, 0.5, 0.0),
    (100.0, 120.0, 0.35, 0.05, 2.0, 0.04),
    (100.0, 80.0, 0.20, 0.03, 0.25, 0.01),
    (1.08, 1.10, 0.08, 0.045, 1.0, 0.03),     # ordre de grandeur EUR/USD (pas une donnée)
]


def _bs_scipy(S0, K, sigma, r, T, q, option):
    d1 = (math.log(S0 / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    N = stats.norm.cdf
    if option == "call":
        return S0 * math.exp(-q * T) * N(d1) - K * math.exp(-r * T) * N(d2)
    return K * math.exp(-r * T) * N(-d2) - S0 * math.exp(-q * T) * N(-d1)


def test_norm_cdf_matches_scipy():
    x = np.linspace(-8.0, 8.0, 3201)
    np.testing.assert_allclose(norm_cdf(x), stats.norm.cdf(x), rtol=1e-14, atol=1e-16)


def test_norm_cdf_scalar_and_symmetry():
    assert norm_cdf(0.0) == 0.5
    for x in (0.1, 1.0, 1.96, 3.5):
        assert norm_cdf(x) + norm_cdf(-x) == pytest.approx(1.0, abs=1e-15)


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("option", ["call", "put"])
def test_bs_matches_independent_scipy_formula(case, option):
    assert bs_price(*case, option=option) == pytest.approx(_bs_scipy(*case, option), rel=1e-13)


def test_bs_hull_example():
    """Hull, Options, Futures and Other Derivatives, exemple 15.6 : S0 = 42, K = 40, r = 10 %,
    σ = 20 %, T = 0,5 → call 4,76, put 0,81 (valeurs publiées arrondies à 10^-2)."""
    assert abs(bs_price(42, 40, 0.2, 0.1, 0.5, option="call") - 4.76) <= 0.005
    assert abs(bs_price(42, 40, 0.2, 0.1, 0.5, option="put") - 0.81) <= 0.005


@pytest.mark.parametrize("case", CASES)
def test_put_call_parity_exact(case):
    S0, K, sigma, r, T, q = case
    c = bs_price(S0, K, sigma, r, T, q, option="call")
    p = bs_price(S0, K, sigma, r, T, q, option="put")
    rhs = S0 * math.exp(-q * T) - K * math.exp(-r * T)
    assert c - p == pytest.approx(rhs, abs=1e-12 * max(S0, K))


def test_dividend_lowers_call_raises_put():
    c0 = bs_price(100, 100, 0.2, 0.03, 1.0, 0.0, option="call")
    c1 = bs_price(100, 100, 0.2, 0.03, 1.0, 0.02, option="call")
    p0 = bs_price(100, 100, 0.2, 0.03, 1.0, 0.0, option="put")
    put_q = bs_price(100, 100, 0.2, 0.03, 1.0, 0.02, option="put")
    assert c1 < c0 and put_q > p0


def test_zero_vol_limit_is_discounted_forward_intrinsic():
    S0, K, r, T, q = 100.0, 95.0, 0.03, 1.0, 0.01
    fwd = S0 * math.exp(-q * T) - K * math.exp(-r * T)
    assert bs_price(S0, K, 0.0, r, T, q, option="call") == pytest.approx(max(fwd, 0.0), rel=1e-15)
    assert bs_price(S0, K, 0.0, r, T, q, option="put") == pytest.approx(max(-fwd, 0.0), abs=1e-15)
    assert bs_price(S0, K, 1e-9, r, T, q, option="call") == pytest.approx(fwd, rel=1e-9)


@pytest.mark.parametrize("bad", [dict(S0=0.0), dict(K=-1.0), dict(sigma=-0.1), dict(T=0.0),
                                 dict(option="digital"), dict(r=float("nan"))])
def test_bs_invalid_inputs_raise(bad):
    kw = dict(S0=100.0, K=100.0, sigma=0.2, r=0.03, T=1.0, q=0.01, option="call")
    kw.update(bad)
    with pytest.raises(ValueError):
        bs_price(**kw)
