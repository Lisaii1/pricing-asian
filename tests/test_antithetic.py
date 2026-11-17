"""Variables antithétiques et combinaison avec le contrôle géométrique.

Cours PricingMonteCarlo_2026, slide 52 : Ĥ_anti = (1/2M)[Σ h(X_i) + Σ h(Y_i)], avec
Y_i = F^{-1}(1 − U) quand X_i = F^{-1}(U), ou Y_i = 2·X̄ − X_i pour une loi symétrique
(N(0, 1) : Y = −X). Polycopié Haqueberge p. 13-14 : T(X) = −X dans le cas gaussien, estimateur
(f(X) + f(T(X)))/2. Chaque trajectoire Z est donc jumelée avec −Z ; l'écart-type se calcule sur
les moyennes de paires (les deux trajectoires d'une paire ne sont pas indépendantes).
Tolérances statistiques = 3 écarts-types ; les autres sont justifiées sur place.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from pricer.asian import price_asian, price_european_mc
from pricer.black_scholes import bs_price
from pricer.geometric import geometric_asian_price
from pricer.normals import normals, ppnd16
from pricer.paths import gbm_paths, obs_dates
from pricer.rng import LCG

SEED = 20261117
BASE = dict(S0=100.0, K=100.0, sigma=0.20, r=0.03, T=1.0, q=0.01)
# r − q − σ²/2 ≠ 0 exprès : l'actif théorique a une dérive logarithmique nulle, qui masquerait
# une erreur de signe sur la dérive de la trajectoire jumelle.
MODEL = dict(S0=100.0, sigma=0.20, r=0.05, T=1.0, q=0.01)

MC_CASES = [
    dict(S0=100.0, K=100.0, sigma=0.20, r=0.03, T=1.0, q=0.01),
    dict(S0=42.0, K=40.0, sigma=0.20, r=0.10, T=0.5, q=0.0),
    dict(S0=100.0, K=120.0, sigma=0.35, r=0.05, T=2.0, q=0.04),
]


def _all_paths(**kw) -> np.ndarray:
    return np.concatenate(list(gbm_paths(**kw)), axis=0)


def _paths_from_normals(z, S0, sigma, r, T, q):
    """Schéma exact écrit ici (oracle indépendant) : z de forme (trajectoires, dates)."""
    n = z.shape[1]
    dt = T / n
    return S0 * np.exp(np.cumsum((r - q - 0.5 * sigma**2) * dt + sigma * math.sqrt(dt) * z,
                                 axis=1))


def _pair_payoffs(case, option, n_paths, obs="monthly"):
    """Payoffs actualisés (Y arithmétique, X géométrique) par trajectoire, paires entrelacées."""
    S = _all_paths(S0=case["S0"], sigma=case["sigma"], r=case["r"], T=case["T"], q=case["q"],
                   obs=obs, n_paths=n_paths, seed=SEED, antithetic=True)
    sign = 1.0 if option == "call" else -1.0
    disc = math.exp(-case["r"] * case["T"])
    Y = disc * np.maximum(sign * (S.mean(axis=1) - case["K"]), 0.0)
    X = disc * np.maximum(sign * (np.exp(np.log(S).mean(axis=1)) - case["K"]), 0.0)
    return Y, X


# --- trajectoires -----------------------------------------------------------------------------

def test_antithetic_paths_pair_z_with_minus_z():
    """Lignes paires : trajectoires de Z (les n_paths/2 premières du flux, au bit près) ;
    lignes impaires : mêmes normales changées de signe."""
    n_pairs, n_obs = 500, 6
    S = _all_paths(**MODEL, obs=n_obs, n_paths=2 * n_pairs, seed=SEED, antithetic=True)
    assert S.shape == (2 * n_pairs, n_obs)
    plain = _all_paths(**MODEL, obs=n_obs, n_paths=n_pairs, seed=SEED)
    np.testing.assert_array_equal(S[0::2], plain)
    z = normals(n_pairs * n_obs, "inverse", seed=SEED).z.reshape(n_pairs, n_obs)
    np.testing.assert_allclose(S[1::2], _paths_from_normals(-z, **MODEL), rtol=1e-13)
    # produit des deux trajectoires d'une paire : l'aléa s'annule, il reste la dérive
    t = obs_dates(MODEL["T"], n_obs)
    drift = (MODEL["r"] - MODEL["q"] - 0.5 * MODEL["sigma"]**2) * t
    np.testing.assert_allclose(np.log(S[0::2] * S[1::2]),
                               np.broadcast_to(2 * math.log(MODEL["S0"]) + 2 * drift,
                                               (n_pairs, n_obs)), atol=1e-12)


def test_antithetic_paths_include_s0_first_column():
    kw = dict(MODEL, obs=4, n_paths=20, seed=SEED, antithetic=True)
    S = _all_paths(**kw, include_s0=True)
    assert S.shape == (20, 5)
    assert (S[:, 0] == MODEL["S0"]).all()
    np.testing.assert_array_equal(S[:, 1:], _all_paths(**kw))


@pytest.mark.parametrize("option", ["call", "put"])
def test_antithetic_control_with_s0_in_the_average_matches_direct_computation(option):
    n = 10_000
    kw = dict(BASE, option=option, obs="weekly", include_s0=True)
    res = price_asian(**kw, n_paths=n, antithetic=True, control="geometric", beta=1.0)
    S = _all_paths(**{k: BASE[k] for k in ("S0", "sigma", "r", "T", "q")}, obs="weekly",
                   n_paths=n, seed=SEED, antithetic=True, include_s0=True)
    sign = 1.0 if option == "call" else -1.0
    disc = math.exp(-BASE["r"] * BASE["T"])
    Y = disc * np.maximum(sign * (S.mean(axis=1) - BASE["K"]), 0.0)
    X = disc * np.maximum(sign * (np.exp(np.log(S).mean(axis=1)) - BASE["K"]), 0.0)
    resid = 0.5 * (Y[0::2] + Y[1::2]) - (0.5 * (X[0::2] + X[1::2])
                                         - geometric_asian_price(**kw))
    assert res.n_obs == 52 and res.include_s0 is True
    assert res.price == pytest.approx(resid.mean(), rel=1e-11)
    assert res.std_error == pytest.approx(resid.std(ddof=1) / math.sqrt(n / 2), rel=1e-7)


def test_antithetic_paths_use_half_the_normals():
    stream_paths = 3_000
    res = price_asian(**BASE, n_paths=stream_paths, antithetic=True)
    assert res.n_uniforms == stream_paths // 2 * 12
    assert res.antithetic is True and res.n_paths == stream_paths
    assert price_asian(**BASE, n_paths=stream_paths).antithetic is False


@pytest.mark.parametrize("method", ["inverse", "box_muller"])
def test_antithetic_paths_do_not_depend_on_batch_size(method):
    kw = dict(MODEL, obs=7, n_paths=2_346, seed=SEED, rng_method=method, antithetic=True)
    a = _all_paths(batch_size=50_000, **kw)
    for batch in (334, 333, 2, 1):                   # pair, impair, une paire par bloc
        np.testing.assert_array_equal(a, _all_paths(batch_size=batch, **kw))


def test_antithetic_blocks_hold_whole_pairs():
    sizes = [blk.shape[0] for blk in gbm_paths(**MODEL, obs=3, n_paths=1_050, seed=SEED,
                                               batch_size=401, antithetic=True)]
    assert sizes == [400, 400, 250]


@pytest.mark.parametrize("n_paths", [1_001, 3])
def test_odd_number_of_paths_raises(n_paths):
    with pytest.raises(ValueError):
        _all_paths(**MODEL, obs=3, n_paths=n_paths, seed=SEED, antithetic=True)
    with pytest.raises(ValueError):
        price_asian(**BASE, n_paths=n_paths, antithetic=True)
    with pytest.raises(ValueError):
        price_european_mc(**BASE, n_paths=n_paths, antithetic=True)


def test_two_paths_is_one_pair_and_cannot_give_a_variance():
    with pytest.raises(ValueError):
        price_asian(**BASE, n_paths=2, antithetic=True)


# --- forme du cours : U ↔ 1 − U avec la transformée inverse ---------------------------------------

def test_course_form_one_minus_u_is_minus_z_for_the_inverse_method():
    """Slide 52 : Y = F^{-1}(1 − U). Pour N(0, 1), Φ^{-1}(1 − U) = −Φ^{-1}(U).
    Tolérance 1e−9 : arrondi de 1 − U (≤ 1,1e−16) amplifié par 1/φ(z) (φ(5) ≈ 1,5e−6 ⇒ 7e−11),
    plus l'imparité d'AS241 à 1e−11 près (mesurée en P1)."""
    u = LCG(SEED).uniforms(120_000)
    z, z_anti = ppnd16(u), ppnd16(1.0 - u)
    assert np.max(np.abs(z_anti + z)) < 1e-9
    np.testing.assert_array_equal(z, normals(120_000, "inverse", seed=SEED).z)


@pytest.mark.parametrize("option", ["call", "put"])
def test_course_form_gives_the_same_price_as_minus_z(option):
    """Prix antithétique construit à la main avec U et 1 − U (forme du slide 52) = prix du
    pricer (Z et −Z), à l'arrondi flottant près."""
    n_pairs, n_obs = 10_000, 12
    u = LCG(SEED).uniforms(n_pairs * n_obs).reshape(n_pairs, n_obs)
    p = BASE
    model = {k: p[k] for k in ("S0", "sigma", "r", "T", "q")}
    sign = 1.0 if option == "call" else -1.0
    disc = math.exp(-p["r"] * p["T"])
    h = [disc * np.maximum(sign * (_paths_from_normals(ppnd16(v), **model).mean(axis=1)
                                   - p["K"]), 0.0) for v in (u, 1.0 - u)]
    pair_means = 0.5 * (h[0] + h[1])
    res = price_asian(**p, option=option, n_paths=2 * n_pairs, antithetic=True)
    assert res.price == pytest.approx(pair_means.mean(), rel=1e-9)
    assert res.std_error == pytest.approx(pair_means.std(ddof=1) / math.sqrt(n_pairs), rel=1e-9)


# --- estimateur antithétique ------------------------------------------------------------------------

@pytest.mark.parametrize("case", MC_CASES)
@pytest.mark.parametrize("option", ["call", "put"])
def test_std_error_is_computed_on_pair_means(case, option):
    """prix = moyenne des n_paths payoffs ; écart-type = s(moyennes de paires)/√(n_paths/2)."""
    n = 20_000
    res = price_asian(**case, option=option, n_paths=n, antithetic=True, batch_size=6_001)
    Y, _ = _pair_payoffs(case, option, n)
    pm = 0.5 * (Y[0::2] + Y[1::2])
    assert res.price == pytest.approx(Y.mean(), rel=1e-12)
    assert res.std_error == pytest.approx(pm.std(ddof=1) / math.sqrt(n / 2), rel=1e-10)
    assert res.ci_low == res.price - 1.96 * res.std_error
    assert res.ci_high == res.price + 1.96 * res.std_error


@pytest.mark.parametrize("case", MC_CASES)
@pytest.mark.parametrize("option", ["call", "put"])
@pytest.mark.parametrize("obs", ["monthly", 1])
def test_european_antithetic_within_3_std_of_black_scholes(case, option, obs):
    res = price_european_mc(**case, option=option, obs=obs, n_paths=200_000, antithetic=True)
    assert res.antithetic is True and res.kind == "european"
    assert abs(res.price - bs_price(**case, option=option)) < 3 * res.std_error


@pytest.mark.parametrize("case", MC_CASES)
@pytest.mark.parametrize("option", ["call", "put"])
def test_asian_antithetic_within_3_std_of_plain_and_less_noisy(case, option):
    kw = dict(case, option=option, n_paths=200_000)
    plain = price_asian(**kw)
    anti = price_asian(**kw, antithetic=True)
    assert abs(anti.price - plain.price) < 3 * math.hypot(anti.std_error, plain.std_error)
    assert anti.std_error < plain.std_error               # à n_paths égal


@pytest.mark.parametrize("option", ["call", "put"])
def test_european_antithetic_less_noisy_than_plain(option):
    kw = dict(BASE, option=option, obs=1, n_paths=100_000)
    assert price_european_mc(**kw, antithetic=True).std_error < price_european_mc(**kw).std_error


@pytest.mark.parametrize("method", ["box_muller", "polar", "acceptance_rejection"])
def test_antithetic_with_other_rng_methods_within_3_std(method):
    ref = price_asian(**BASE, n_paths=100_000, antithetic=True)
    res = price_asian(**BASE, n_paths=100_000, antithetic=True, rng_method=method)
    assert abs(res.price - ref.price) < 3 * math.hypot(res.std_error, ref.std_error)


def test_antithetic_reproducible_bitwise():
    kw = dict(BASE, n_paths=20_000, antithetic=True)
    a, b = price_asian(**kw), price_asian(**kw)
    assert a.price == b.price and a.std_error == b.std_error


# --- combinaison antithétique + contrôle ---------------------------------------------------------------

@pytest.mark.parametrize("case", MC_CASES)
@pytest.mark.parametrize("option", ["call", "put"])
def test_control_is_applied_to_pair_means(case, option):
    """Ȳ_i, X̄_i = moyennes de paires ; b = Cov(Ȳ, X̄)/Var(X̄) ; écart-type des résidus sur
    n_paths/2 paires ; « sans contrôle » = antithétique seul sur le même échantillon."""
    n = 20_000
    res = price_asian(**case, option=option, n_paths=n, antithetic=True, control="geometric",
                      batch_size=6_001)
    Y, X = _pair_payoffs(case, option, n)
    Yb, Xb = 0.5 * (Y[0::2] + Y[1::2]), 0.5 * (X[0::2] + X[1::2])
    cov = np.cov(Yb, Xb, ddof=1)
    b = cov[0, 1] / cov[1, 1]
    resid = Yb - b * (Xb - geometric_asian_price(**case, option=option))
    assert res.beta == pytest.approx(b, rel=1e-10)
    assert res.corr == pytest.approx(np.corrcoef(Yb, Xb)[0, 1], rel=1e-10)
    assert res.price == pytest.approx(resid.mean(), rel=1e-11)
    assert res.std_error == pytest.approx(resid.std(ddof=1) / math.sqrt(n / 2), rel=1e-7)
    assert res.std_error_no_control == pytest.approx(Yb.std(ddof=1) / math.sqrt(n / 2),
                                                     rel=1e-10)
    anti = price_asian(**case, option=option, n_paths=n, antithetic=True, batch_size=6_001)
    assert res.std_error_no_control == anti.std_error


@pytest.mark.parametrize("case", MC_CASES)
@pytest.mark.parametrize("option", ["call", "put"])
def test_combination_beats_antithetic_alone(case, option):
    """Écart-type de la combinaison < celui de l'antithétique seul, à n_paths égal ; le prix
    combiné reste à 3 écarts-types (combinés) du prix contrôlé sans antithétique."""
    kw = dict(case, option=option, n_paths=200_000)
    anti = price_asian(**kw, antithetic=True)
    ctrl = price_asian(**kw, control="geometric")
    both = price_asian(**kw, antithetic=True, control="geometric")
    assert both.std_error < anti.std_error
    assert abs(both.price - ctrl.price) < 3 * math.hypot(both.std_error, ctrl.std_error)


@pytest.mark.parametrize("case,option", [(MC_CASES[1], "call"), (MC_CASES[2], "put")])
def test_combination_is_worse_than_control_alone_for_in_the_money_options(case, option):
    """Constat mesuré, contraire à l'attente « combinaison < chacun des deux » du prompt P3.

    Le contrôle laisse le résidu e = Y − bX ≈ e^{−rT}(A − G) quand l'option finit dans la
    monnaie. A − G mesure la dispersion de la trajectoire : c'est une fonction presque paire
    de Z, donc e(Z) et e(−Z) sont corrélés positivement. Or, à n_paths égal,
    Var(combinaison) ≈ Var(contrôle seul)·(1 + ρ_e) : l'antithétique dégrade alors le contrôle.
    Ici (options dans la monnaie à ≈ 78 %) ρ_e ≈ +0,23 et +0,41 ; le seuil 3/√M est
    3 écarts-types d'une corrélation empirique nulle sur M paires."""
    n = 200_000
    Y, X = _pair_payoffs(case, option, n)
    b = np.cov(Y, X, ddof=1)[0, 1] / X.var(ddof=1)
    e = Y - b * X
    rho_e = np.corrcoef(e[0::2], e[1::2])[0, 1]
    assert rho_e > 3 / math.sqrt(n / 2)
    kw = dict(case, option=option, n_paths=n, control="geometric")
    both = price_asian(**kw, antithetic=True)
    ctrl = price_asian(**kw)
    assert both.std_error > ctrl.std_error
    # ordre de grandeur attendu : √(1 + ρ_e), à 5 % près (b ré-optimisé sur les paires,
    # échantillons différents : écarts-types estimés à ≈ 1 % près chacun)
    assert both.std_error / ctrl.std_error == pytest.approx(math.sqrt(1 + rho_e), rel=0.05)


@pytest.mark.parametrize("option", ["call", "put"])
def test_geometric_target_with_antithetic_and_control_is_the_closed_form(option):
    res = price_asian(**BASE, option=option, average="geometric", control="geometric", beta=1.0,
                      n_paths=20_000, antithetic=True)
    assert res.price == pytest.approx(geometric_asian_price(**BASE, option=option), rel=1e-13)
    assert res.std_error == 0.0


def test_pilot_with_antithetic_draws_pairs_and_is_not_reused():
    n_pilot, n = 2_000, 10_000
    res = price_asian(**BASE, n_paths=n, antithetic=True, control="geometric", beta="pilot",
                      n_pilot=n_pilot)
    assert res.n_uniforms == (n_pilot + n) // 2 * 12
    Y, X = _pair_payoffs(BASE, "call", n_pilot + n)
    Yb, Xb = 0.5 * (Y[0::2] + Y[1::2]), 0.5 * (X[0::2] + X[1::2])
    k = n_pilot // 2
    cov = np.cov(Yb[:k], Xb[:k], ddof=1)
    b = cov[0, 1] / cov[1, 1]
    resid = Yb[k:] - b * (Xb[k:] - geometric_asian_price(**BASE))
    assert res.beta == pytest.approx(b, rel=1e-10)
    assert res.price == pytest.approx(resid.mean(), rel=1e-11)
    with pytest.raises(ValueError):
        price_asian(**BASE, n_paths=n, antithetic=True, control="geometric", beta="pilot",
                    n_pilot=2_001)


def test_antithetic_must_be_a_boolean():
    with pytest.raises(TypeError):
        price_asian(**BASE, n_paths=100, antithetic="yes")
