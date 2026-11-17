"""Asiatique à moyenne géométrique : formule fermée discrète et Monte-Carlo.

G = (Π_k S(t_k))^{1/n} est log-normale (cours PricingMonteCarlo_2026, slide 76, écrit avec q = 0) :
    ln G ~ N(μ_G, σ_G²),  μ_G = ln S0 + (r − q − σ²/2)·t̄,  t̄ = (1/n)Σ t_k,
    σ_G² = (σ²/n²)·Σ_i Σ_j min(t_i, t_j).
Tolérances statistiques = 3 écarts-types de l'estimateur ; les autres sont justifiées sur place.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from pricer.asian import price_asian
from pricer.black_scholes import bs_price
from pricer.geometric import geometric_asian_price, geometric_moments
from pricer.paths import gbm_paths

SEED = 20261117
BASE = dict(S0=100.0, K=100.0, sigma=0.20, r=0.03, T=1.0, q=0.01)

MC_CASES = [  # 3 jeux, dont q > 0 (les mêmes qu'en P2)
    dict(S0=100.0, K=100.0, sigma=0.20, r=0.03, T=1.0, q=0.01),
    dict(S0=42.0, K=40.0, sigma=0.20, r=0.10, T=0.5, q=0.0),
    dict(S0=100.0, K=120.0, sigma=0.35, r=0.05, T=2.0, q=0.04),
]


def _regular_dates(T, n):
    """t_k = k·T/n, k = 1..n, écrit ici indépendamment de pricer.paths.obs_dates."""
    return [k * T / n for k in range(1, n + 1)]


# --- moments de ln G -------------------------------------------------------------------------

@pytest.mark.parametrize("T", [0.25, 1.0, 2.0])
@pytest.mark.parametrize("n", [1, 2, 3, 12, 252])
def test_general_moments_give_regular_dates_closed_form(T, n):
    """t_k = kT/n ⇒ t̄ = T(n+1)/(2n) et σ_G² = σ²·T(n+1)(2n+1)/(6n²).
    r − q − σ²/2 ≠ 0 exprès : avec l'actif théorique (0,03 − 0,01 − 0,02 = 0) μ_G ne dépendrait
    pas de t̄ et une erreur sur t̄ passerait inaperçue."""
    S0, sigma, r, q = 100.0, 0.2, 0.05, 0.01
    mu, var = geometric_moments(S0, sigma, r, q, _regular_dates(T, n))
    assert mu == pytest.approx(math.log(S0) + (r - q - 0.5 * sigma**2) * T * (n + 1) / (2 * n),
                               rel=1e-13)
    assert var == pytest.approx(sigma**2 * T * (n + 1) * (2 * n + 1) / (6 * n**2), rel=1e-12)


def test_general_moments_on_irregular_dates_match_plain_loops():
    """Dates quelconques (dans le désordre, avec t = 0) : double somme écrite en boucles."""
    S0, sigma, r, q = 80.0, 0.3, 0.05, 0.02
    dates = [0.4, 0.0, 1.0, 0.1, 0.35]
    n = len(dates)
    tbar = sum(dates) / n
    double_sum = sum(min(a, b) for a in dates for b in dates)
    mu, var = geometric_moments(S0, sigma, r, q, dates)
    assert mu == pytest.approx(math.log(S0) + (r - q - 0.5 * sigma**2) * tbar, rel=1e-13)
    assert var == pytest.approx(sigma**2 * double_sum / n**2, rel=1e-13)


def test_variance_matches_course_slide_76_sum():
    """Slide 76 : Var(Σ_j W(t_j)) = Σ_j (2j − 1)·t_{n+1−j} pour t_1 < … < t_n."""
    sigma = 0.25
    t = [0.1, 0.35, 0.4, 1.0, 1.7]
    n = len(t)
    course_sum = sum((2 * j - 1) * t[n - j] for j in range(1, n + 1))   # t_{n+1−j} = t[n − j]
    _, var = geometric_moments(100.0, sigma, 0.03, 0.0, t)
    assert var == pytest.approx(sigma**2 * course_sum / n**2, rel=1e-13)


def test_variance_tends_to_continuous_limit_sigma2_T_over_3():
    """n → ∞ : σ_G² → σ²T/3 et t̄ → T/2 (Kemna-Vorst continu, hors cours).
    L'écart relatif vaut exactement 3/(2n) + 1/(2n²) : il est borné par 2/n."""
    S0, sigma, r, q, T = 100.0, 0.2, 0.05, 0.01, 1.0
    for n in (10, 100, 1000):
        mu, var = geometric_moments(S0, sigma, r, q, _regular_dates(T, n))
        rel = var / (sigma**2 * T / 3.0) - 1.0
        assert 0.0 < rel < 2.0 / n
        assert rel == pytest.approx(1.5 / n + 0.5 / n**2, rel=1e-9)
        tbar = (mu - math.log(S0)) / (r - q - 0.5 * sigma**2)
        assert tbar == pytest.approx(0.5 * T * (1 + 1 / n), rel=1e-12)


@pytest.mark.parametrize("option", ["call", "put"])
def test_price_converges_at_order_one_to_continuous_kemna_vorst(option):
    """Prix discret → prix continu (σ/√3, dérive sur T/2 : hors cours) ; l'erreur est en 1/n,
    donc divisée par ≈ 2 quand n double."""
    p = BASE
    mu = math.log(p["S0"]) + (p["r"] - p["q"] - 0.5 * p["sigma"]**2) * p["T"] / 2.0
    sg = p["sigma"] * math.sqrt(p["T"] / 3.0)
    d2 = (mu - math.log(p["K"])) / sg
    d1 = d2 + sg
    Phi = lambda x: 0.5 * math.erfc(-x / math.sqrt(2.0))          # noqa: E731
    disc = math.exp(-p["r"] * p["T"])
    fwd = math.exp(mu + 0.5 * sg * sg)
    cont = (disc * (fwd * Phi(d1) - p["K"] * Phi(d2)) if option == "call"
            else disc * (p["K"] * Phi(-d2) - fwd * Phi(-d1)))
    errs = [abs(geometric_asian_price(**p, option=option, obs=n) - cont)
            for n in (250, 500, 1000, 2000)]
    for e_coarse, e_fine in zip(errs, errs[1:]):
        assert 1.9 < e_coarse / e_fine < 2.1


# --- formule fermée --------------------------------------------------------------------------

@pytest.mark.parametrize("case", MC_CASES)
@pytest.mark.parametrize("option", ["call", "put"])
def test_one_observation_is_black_scholes(case, option):
    """n = 1 (t_1 = T) : G = S_T, donc le prix est celui de Black-Scholes (q > 0 inclus)."""
    assert geometric_asian_price(**case, option=option, obs=1) == pytest.approx(
        bs_price(**case, option=option), rel=1e-12)


@pytest.mark.parametrize("case", MC_CASES)
@pytest.mark.parametrize("option", ["call", "put"])
@pytest.mark.parametrize("obs,include_s0", [("monthly", False), (5, True)])
def test_price_matches_course_form_slide_76(case, option, obs, include_s0):
    """Slide 76 : G est un MBG de dérive r − δ et de volatilité σ̄ sur l'horizon T̄ = (1/n)Σ t_j,
    σ̄² = σ²/(n² T̄)·Σ_j (2j − 1)·t_{n+1−j}, δ = σ²/2 − σ̄²/2 (le slide a q = 0 ; ici q + δ).
    Le payoff est payé en T : prix = e^{−r(T − T̄)}·BS(S0, K, σ̄, r, T̄, dividende q + δ)."""
    T, sigma = case["T"], case["sigma"]
    n_reg = int(round(12 * T)) if obs == "monthly" else obs
    t = ([0.0] if include_s0 else []) + _regular_dates(T, n_reg)
    n = len(t)
    Tbar = sum(t) / n
    sbar2 = sigma**2 / (n**2 * Tbar) * sum((2 * j - 1) * t[n - j] for j in range(1, n + 1))
    delta = 0.5 * sigma**2 - 0.5 * sbar2
    ref = math.exp(-case["r"] * (T - Tbar)) * bs_price(
        case["S0"], case["K"], math.sqrt(sbar2), case["r"], Tbar, case["q"] + delta, option)
    got = geometric_asian_price(**case, option=option, obs=obs, include_s0=include_s0)
    assert got == pytest.approx(ref, rel=1e-12)


@pytest.mark.parametrize("case", MC_CASES)
def test_put_call_parity(case):
    """C − P = e^{−rT}(E[G] − K), E[G] = exp(μ_G + σ_G²/2)."""
    c = geometric_asian_price(**case, option="call", obs="weekly")
    p = geometric_asian_price(**case, option="put", obs="weekly")
    n = int(round(52 * case["T"]))
    mu, var = geometric_moments(case["S0"], case["sigma"], case["r"], case["q"],
                                _regular_dates(case["T"], n))
    rhs = math.exp(-case["r"] * case["T"]) * (math.exp(mu + 0.5 * var) - case["K"])
    assert c - p == pytest.approx(rhs, abs=1e-12 * case["S0"])


def test_explicit_dates_equal_obs_shortcut():
    p = BASE
    a = geometric_asian_price(**p, obs=4)
    b = geometric_asian_price(**p, dates=[0.25, 0.5, 0.75, 1.0])
    assert a == b
    c = geometric_asian_price(**p, obs=4, include_s0=True)
    d = geometric_asian_price(**p, dates=[0.0, 0.25, 0.5, 0.75, 1.0])
    assert c == d and c != a


@pytest.mark.parametrize("K", [90.0, 100.0, 110.0])
@pytest.mark.parametrize("sigma", [1e-8, 0.0])
def test_zero_vol_limit(K, sigma):
    """σ → 1e−8 : G ≈ S0·e^{(r−q)t̄}, prix = e^{−rT}·max(±(S0 e^{(r−q)t̄} − K), 0).
    Tolérance : la valeur temps est bornée par F·σ_G/√(2π) < S0·σ·√T (σ = 0 : limite exacte)."""
    p = dict(BASE, K=K, sigma=sigma)
    tbar = p["T"] * 13 / 24                           # mensuel sur 1 an : T(n+1)/(2n), n = 12
    fwd = p["S0"] * math.exp((p["r"] - p["q"]) * tbar)
    disc = math.exp(-p["r"] * p["T"])
    tol = p["S0"] * sigma * math.sqrt(p["T"]) + 1e-12 * p["S0"]
    assert geometric_asian_price(**p, option="call") == pytest.approx(
        disc * max(fwd - K, 0.0), abs=tol)
    assert geometric_asian_price(**p, option="put") == pytest.approx(
        disc * max(K - fwd, 0.0), abs=tol)


@pytest.mark.parametrize("bad", [dict(option="digital"), dict(K=0.0), dict(S0=-1.0),
                                 dict(sigma=-0.1), dict(T=0.0), dict(dates=[]),
                                 dict(dates=[-0.1, 0.5]), dict(dates=[0.5, 1.5]),
                                 dict(dates=[0.5, float("nan")])])
def test_invalid_inputs_raise(bad):
    kw = dict(BASE)
    kw.update(bad)
    with pytest.raises(ValueError):
        geometric_asian_price(**kw)


# --- Monte-Carlo sur G simulé (sans contrôle) --------------------------------------------------

@pytest.mark.parametrize("case", MC_CASES)
@pytest.mark.parametrize("option", ["call", "put"])
def test_geometric_mc_within_3_std_of_closed_form(case, option):
    res = price_asian(**case, option=option, average="geometric", n_paths=200_000)
    ref = geometric_asian_price(**case, option=option)
    assert res.average == "geometric"
    assert abs(res.price - ref) < 3 * res.std_error


@pytest.mark.parametrize("option", ["call", "put"])
def test_geometric_mc_with_s0_and_weekly_dates_within_3_std(option):
    kw = dict(BASE, option=option, obs="weekly", include_s0=True)
    res = price_asian(**kw, average="geometric", n_paths=100_000)
    assert abs(res.price - geometric_asian_price(**kw)) < 3 * res.std_error


def test_geometric_mc_payoff_is_on_simulated_geometric_mean():
    """Le payoff MC est e^{−rT}·max(G − K, 0) avec G = exp(moyenne des ln S(t_k))."""
    p = dict(BASE, T=0.5)
    res = price_asian(**p, obs=6, average="geometric", n_paths=5_000, batch_size=1_234)
    S = np.concatenate(list(gbm_paths(p["S0"], p["sigma"], p["r"], p["T"], p["q"], obs=6,
                                      n_paths=5_000, seed=SEED)))
    G = np.exp(np.log(S).mean(axis=1))
    pay = math.exp(-p["r"] * p["T"]) * np.maximum(G - p["K"], 0.0)
    assert res.price == pytest.approx(pay.mean(), rel=1e-12)
    assert res.std_error == pytest.approx(pay.std(ddof=1) / math.sqrt(5_000), rel=1e-10)


@pytest.mark.parametrize("case", MC_CASES)
def test_arithmetic_dominates_geometric_on_the_same_paths(case):
    """Inégalité arithmético-géométrique trajectoire par trajectoire (A ≥ G), donc, sur les
    mêmes trajectoires : call arithmétique ≥ call géométrique, put arithmétique ≤ put
    géométrique."""
    S = np.concatenate(list(gbm_paths(case["S0"], case["sigma"], case["r"], case["T"],
                                      case["q"], n_paths=20_000, seed=SEED)))
    A, G = S.mean(axis=1), np.exp(np.log(S).mean(axis=1))
    assert np.all(A >= G * (1.0 - 1e-14))          # 1e−14 : arrondi flottant de exp(mean(log))
    kw = dict(case, n_paths=20_000)
    for option, sign in (("call", 1.0), ("put", -1.0)):
        arith = price_asian(**kw, option=option)
        geo = price_asian(**kw, option=option, average="geometric")
        assert arith.average == "arithmetic"
        assert sign * (arith.price - geo.price) > 0.0


def test_unknown_average_raises():
    with pytest.raises(ValueError):
        price_asian(**BASE, n_paths=100, average="harmonic")
