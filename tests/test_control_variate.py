"""Variable de contrôle géométrique (cours PricingMonteCarlo_2026, slides 50-51 et 76-77).

    Y = e^{−rT}·payoff(A),  X = e^{−rT}·payoff(G) sur les mêmes trajectoires,  E[X] fermée,
    Ŷ_b = mean(Y) − b·(mean(X) − E[X]),  b optimal = Cov(Y, X)/Var(X)   (slide 50).
Tolérances statistiques = 3 écarts-types ; les identités algébriques sont testées à la
précision machine (tolérance relative justifiée sur place).
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from pricer.asian import price_asian, price_european_mc
from pricer.geometric import geometric_asian_price
from pricer.paths import gbm_paths

SEED = 20261117
BASE = dict(S0=100.0, K=100.0, sigma=0.20, r=0.03, T=1.0, q=0.01)

MC_CASES = [
    dict(S0=100.0, K=100.0, sigma=0.20, r=0.03, T=1.0, q=0.01),
    dict(S0=42.0, K=40.0, sigma=0.20, r=0.10, T=0.5, q=0.0),
    dict(S0=100.0, K=120.0, sigma=0.35, r=0.05, T=2.0, q=0.04),
]


def _payoffs(case, option, n_paths, obs="monthly", include_s0=False):
    """(Y, X) actualisés, recalculés ici à partir des trajectoires (oracle indépendant)."""
    S = np.concatenate(list(gbm_paths(case["S0"], case["sigma"], case["r"], case["T"],
                                      case["q"], obs=obs, n_paths=n_paths, seed=SEED,
                                      include_s0=include_s0)))
    A, G = S.mean(axis=1), np.exp(np.log(S).mean(axis=1))
    sign = 1.0 if option == "call" else -1.0
    disc = math.exp(-case["r"] * case["T"])
    return (disc * np.maximum(sign * (A - case["K"]), 0.0),
            disc * np.maximum(sign * (G - case["K"]), 0.0))


# --- cible = contrôle : estimateur exact --------------------------------------------------------

@pytest.mark.parametrize("case", MC_CASES)
@pytest.mark.parametrize("option", ["call", "put"])
@pytest.mark.parametrize("beta", [1.0, "optimal"])
def test_geometric_target_with_geometric_control_is_the_closed_form(case, option, beta):
    """Y := X et b = 1 : Ŷ = mean(X) − (mean(X) − E[X]) = E[X], résidus tous nuls.
    Le b optimal vaut alors exactement 1. Tolérance 1e−13 relative : un arrondi flottant sur
    a − (a − c)."""
    res = price_asian(**case, option=option, average="geometric", control="geometric",
                      beta=beta, n_paths=20_000)
    ref = geometric_asian_price(**case, option=option)
    assert res.price == pytest.approx(ref, rel=1e-13)
    assert res.std_error == 0.0
    assert res.beta == 1.0
    assert res.control_mean == ref
    assert res.std_error_no_control > 0.0
    assert res.variance_ratio == math.inf


# --- estimateur contre un recalcul direct ---------------------------------------------------------

@pytest.mark.parametrize("case", MC_CASES)
@pytest.mark.parametrize("option", ["call", "put"])
def test_optimal_beta_matches_direct_computation(case, option):
    """b = Cov(Y, X)/Var(X) sur l'échantillon, prix = mean(Y) − b(mean(X) − E[X]), écart-type
    sur les résidus Y − b(X − E[X]), s² en 1/(N − 1)."""
    n = 30_000
    res = price_asian(**case, option=option, control="geometric", n_paths=n, batch_size=7_001)
    Y, X = _payoffs(case, option, n)
    EX = geometric_asian_price(**case, option=option)
    cov = np.cov(Y, X, ddof=1)
    b = cov[0, 1] / cov[1, 1]
    resid = Y - b * (X - EX)
    assert res.control == "geometric" and res.beta_mode == "optimal" and res.n_pilot == 0
    assert res.control_mean == EX
    assert res.beta == pytest.approx(b, rel=1e-10)
    assert res.corr == pytest.approx(np.corrcoef(Y, X)[0, 1], rel=1e-10)
    assert res.price == pytest.approx(resid.mean(), rel=1e-11)
    # variance résiduelle = différence de sommes ≈ 10³ fois plus grandes : 1e−7 relatif suffit
    assert res.std_error == pytest.approx(resid.std(ddof=1) / math.sqrt(n), rel=1e-7)
    assert res.std_error_no_control == pytest.approx(Y.std(ddof=1) / math.sqrt(n), rel=1e-10)
    assert res.ci_low == res.price - res.z * res.std_error
    assert res.ci_high == res.price + res.z * res.std_error
    assert res.n_uniforms == n * res.n_obs                     # pas de pilote


@pytest.mark.parametrize("beta", [1.0, 0.5, -0.3])
def test_fixed_beta_matches_direct_computation(beta):
    n = 20_000
    res = price_asian(**BASE, control="geometric", beta=beta, n_paths=n)
    Y, X = _payoffs(BASE, "call", n)
    resid = Y - beta * (X - geometric_asian_price(**BASE))
    assert res.beta == beta and res.beta_mode == "fixed"
    assert res.price == pytest.approx(resid.mean(), rel=1e-11)
    assert res.std_error == pytest.approx(resid.std(ddof=1) / math.sqrt(n), rel=1e-7)


def test_beta_zero_is_the_plain_estimator():
    plain = price_asian(**BASE, n_paths=20_000)
    res = price_asian(**BASE, control="geometric", beta=0.0, n_paths=20_000)
    assert res.price == plain.price and res.std_error == plain.std_error
    assert res.variance_ratio == 1.0


def test_plain_result_has_no_control_fields():
    res = price_asian(**BASE, n_paths=1_000)
    assert res.control is None and res.beta is None and res.beta_mode is None
    assert res.corr is None and res.control_mean is None
    assert res.std_error_no_control is None and res.variance_ratio is None and res.n_pilot == 0


# --- propriétés statistiques ----------------------------------------------------------------------

@pytest.mark.parametrize("option", ["call", "put"])
def test_controlled_price_within_3_combined_std_of_plain_at_one_million(option):
    n = 1_000_000
    plain = price_asian(**BASE, option=option, n_paths=n)
    ctrl = price_asian(**BASE, option=option, n_paths=n, control="geometric")
    assert abs(ctrl.price - plain.price) < 3 * math.hypot(ctrl.std_error, plain.std_error)
    assert ctrl.std_error_no_control == pytest.approx(plain.std_error, rel=1e-12)
    assert ctrl.std_error < plain.std_error


@pytest.mark.parametrize("case", MC_CASES)
@pytest.mark.parametrize("option", ["call", "put"])
@pytest.mark.parametrize("obs,include_s0", [("monthly", False), ("weekly", True)])
def test_control_reduces_std_error_and_stays_within_3_std(case, option, obs, include_s0):
    kw = dict(case, option=option, obs=obs, include_s0=include_s0, n_paths=50_000)
    plain = price_asian(**kw)
    ctrl = price_asian(**kw, control="geometric")
    assert ctrl.std_error < ctrl.std_error_no_control
    assert ctrl.control_mean == geometric_asian_price(**case, option=option, obs=obs,
                                                      include_s0=include_s0)
    assert abs(ctrl.price - plain.price) < 3 * math.hypot(ctrl.std_error, plain.std_error)


@pytest.mark.parametrize("case", MC_CASES)
@pytest.mark.parametrize("option", ["call", "put"])
def test_variance_ratio_is_one_over_one_minus_rho_squared_for_optimal_beta(case, option):
    """Avec b = Cov/Var(X) estimé sur l'échantillon, Σ résidus² = Σ(Y − Ȳ)²·(1 − ρ̂²) est une
    identité algébrique : ratio = 1/(1 − ρ̂²). Tolérance 1e−6 relative : 1 − ρ̂² ≈ 1e−3 à 1e−4
    est une différence de nombres proches de 1 (perte d'environ 4 chiffres sur 16)."""
    res = price_asian(**case, option=option, control="geometric", n_paths=50_000)
    assert 0.0 < res.corr < 1.0
    assert res.variance_ratio == pytest.approx(1.0 / (1.0 - res.corr**2), rel=1e-6)
    assert res.variance_ratio == pytest.approx(
        (res.std_error_no_control / res.std_error) ** 2, rel=1e-9)
    assert res.variance_ratio > 1.0


@pytest.mark.parametrize("option", ["call", "put"])
def test_optimal_beta_is_at_least_as_good_as_beta_one_on_the_same_sample(option):
    """Le b optimal minimise la variance résiduelle de l'échantillon (moindres carrés)."""
    kw = dict(BASE, option=option, control="geometric", n_paths=50_000)
    opt = price_asian(**kw)
    one = price_asian(**kw, beta=1.0)
    assert opt.std_error <= one.std_error
    assert one.std_error < one.std_error_no_control
    assert one.variance_ratio <= opt.variance_ratio


# --- mode pilote ------------------------------------------------------------------------------------

@pytest.mark.parametrize("rng_method", ["inverse", "box_muller"])
def test_pilot_beta_is_estimated_on_paths_that_are_not_reused(rng_method):
    """b vient des n_pilot premières trajectoires ; l'estimation porte sur les n_paths
    suivantes du même LCG. Compteur d'uniformes : (n_pilot + n_paths)·n_obs normales tirées,
    à 1 uniforme par normale (inverse ; Box-Muller : 2 uniformes pour 2 normales)."""
    n_pilot, n, n_obs = 3_000, 20_000, 12
    res = price_asian(**BASE, control="geometric", beta="pilot", n_pilot=n_pilot, n_paths=n,
                      rng_method=rng_method, batch_size=6_000)
    S = np.concatenate(list(gbm_paths(BASE["S0"], BASE["sigma"], BASE["r"], BASE["T"],
                                      BASE["q"], n_paths=n_pilot + n, seed=SEED,
                                      rng_method=rng_method)))
    disc = math.exp(-BASE["r"] * BASE["T"])
    Y = disc * np.maximum(S.mean(axis=1) - BASE["K"], 0.0)
    X = disc * np.maximum(np.exp(np.log(S).mean(axis=1)) - BASE["K"], 0.0)
    cov = np.cov(Y[:n_pilot], X[:n_pilot], ddof=1)
    b = cov[0, 1] / cov[1, 1]
    resid = Y[n_pilot:] - b * (X[n_pilot:] - geometric_asian_price(**BASE))
    assert res.beta_mode == "pilot" and res.n_pilot == n_pilot and res.n_paths == n
    assert res.beta == pytest.approx(b, rel=1e-10)
    assert res.price == pytest.approx(resid.mean(), rel=1e-11)
    assert res.std_error == pytest.approx(resid.std(ddof=1) / math.sqrt(n), rel=1e-7)
    assert res.std_error_no_control == pytest.approx(Y[n_pilot:].std(ddof=1) / math.sqrt(n),
                                                     rel=1e-10)
    assert res.n_uniforms == (n_pilot + n) * n_obs


def test_optimal_and_fixed_modes_draw_no_pilot():
    for beta in ("optimal", 1.0):
        res = price_asian(**BASE, control="geometric", beta=beta, n_paths=4_000, n_pilot=999)
        assert res.n_uniforms == 4_000 * 12 and res.n_pilot == 0


def test_pilot_price_within_3_std_of_optimal_price_on_other_paths():
    opt = price_asian(**BASE, control="geometric", n_paths=100_000)
    pil = price_asian(**BASE, control="geometric", beta="pilot", n_paths=100_000)
    assert abs(pil.price - opt.price) < 3 * math.hypot(pil.std_error, opt.std_error)
    assert pil.std_error < pil.std_error_no_control


# --- reproductibilité, blocs, cas limites -------------------------------------------------------------

@pytest.mark.parametrize("beta", ["optimal", 1.0, "pilot"])
def test_reproducible_bitwise(beta):
    kw = dict(BASE, control="geometric", beta=beta, n_paths=20_000)
    a, b = price_asian(**kw), price_asian(**kw)
    assert (a.price, a.std_error, a.beta, a.corr, a.variance_ratio) == \
           (b.price, b.std_error, b.beta, b.corr, b.variance_ratio)


def test_batch_size_changes_only_summation_order():
    kw = dict(BASE, control="geometric", n_paths=30_000)
    a = price_asian(**kw, batch_size=50_000)
    b = price_asian(**kw, batch_size=777)
    assert a.price == pytest.approx(b.price, rel=1e-11)
    assert a.beta == pytest.approx(b.beta, rel=1e-10)
    assert a.std_error == pytest.approx(b.std_error, rel=1e-7)


def test_control_with_constant_payoffs_falls_back_to_beta_zero():
    """Très hors de la monnaie : tous les payoffs sont nuls, Var(X) = 0, b optimal indéfini → 0."""
    res = price_asian(**dict(BASE, K=1000.0), control="geometric", n_paths=1_000)
    assert res.price == 0.0 and res.std_error == 0.0
    assert res.beta == 0.0 and res.corr == 0.0 and res.variance_ratio == 1.0


@pytest.mark.parametrize("bad", [dict(control="forward"), dict(control="geometric", beta="best"),
                                 dict(control="geometric", beta=float("nan")),
                                 dict(control="geometric", beta=True),
                                 dict(control="geometric", beta="pilot", n_pilot=1),
                                 dict(control="geometric", beta="pilot", n_pilot=2.5),
                                 dict(beta=1.0), dict(beta="pilot")])
def test_invalid_control_inputs_raise(bad):
    with pytest.raises((ValueError, TypeError)):
        price_asian(**BASE, n_paths=100, **bad)


def test_geometric_control_is_not_available_for_the_european():
    """Le contrôle géométrique porte sur la moyenne : sans objet pour le payoff sur S_T."""
    with pytest.raises(NotImplementedError):
        price_european_mc(**BASE, n_paths=100, control="geometric")
