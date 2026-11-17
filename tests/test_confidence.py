"""Niveau de confiance de l'IC et corrélation antithétique (P4, étape 0).

IC symétrique au niveau c (slides 48-49 ; exercice des slides 77 et 81 : IC à 95 % et à 99 %) :
    [prix − z·s/√N ; prix + z·s/√N],  z = Φ^{-1}((1 + c)/2),
z calculé par l'inverse AS241 du projet (pricer.normals.ppnd16), jamais codé en dur.
Valeurs attendues (tables usuelles, 7 chiffres) : z(0,95) = 1,959964 ; z(0,99) = 2,575829.

Corrélation antithétique (slide 52 ; tableau du slide 78, ligne « Correl. ») : corrélation
empirique entre h(Z) et h(−Z) sur les paires, calculée sur le payoff Y (pas sur le résidu du
contrôle).
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from pricer.asian import MCResult, Z_95, price_asian, price_european_mc, z_value
from pricer.normals import ppnd16
from pricer.paths import gbm_paths

SEED = 20261117
BASE = dict(S0=100.0, K=100.0, sigma=0.20, r=0.03, T=1.0, q=0.01)
MODEL = dict(S0=100.0, sigma=0.20, r=0.05, T=1.0, q=0.01)


# --- z ------------------------------------------------------------------------------------------

def test_z_95_and_99_match_tables():
    assert z_value(0.95) == pytest.approx(1.959964, abs=1e-6)
    assert z_value(0.99) == pytest.approx(2.575829, abs=1e-6)


@pytest.mark.parametrize("c", [0.5, 0.9, 0.95, 0.98, 0.99, 0.999])
def test_z_is_as241_inverse_at_one_plus_c_over_two(c):
    assert z_value(c) == float(ppnd16(np.array([(1.0 + c) / 2.0]))[0])


def test_z_95_constant_is_computed_not_hardcoded():
    assert Z_95 == z_value(0.95)
    assert Z_95 != 1.96


@pytest.mark.parametrize("bad", [0.0, 1.0, -0.1, 1.5, math.nan, math.inf])
def test_z_rejects_level_outside_open_unit_interval(bad):
    with pytest.raises(ValueError):
        z_value(bad)


@pytest.mark.parametrize("bad", ["0.95", None, True])
def test_z_rejects_non_real(bad):
    with pytest.raises(TypeError):
        z_value(bad)


# --- confidence dans les pricers ----------------------------------------------------------------

@pytest.mark.parametrize("pricer", [price_asian, price_european_mc])
def test_default_confidence_is_95(pricer):
    res = pricer(**BASE, n_paths=5_000)
    assert res.confidence == 0.95
    assert res.z == z_value(0.95)
    assert res.ci_low == res.price - res.z * res.std_error
    assert res.ci_high == res.price + res.z * res.std_error


@pytest.mark.parametrize("pricer", [price_asian, price_european_mc])
def test_confidence_99_widens_interval_only(pricer):
    a = pricer(**BASE, n_paths=5_000)
    b = pricer(**BASE, n_paths=5_000, confidence=0.99)
    assert (b.price, b.std_error) == (a.price, a.std_error)      # mêmes trajectoires
    assert b.confidence == 0.99 and b.z == z_value(0.99)
    assert b.ci_low == b.price - z_value(0.99) * b.std_error
    assert b.ci_high == b.price + z_value(0.99) * b.std_error
    assert b.ci_high - b.ci_low > a.ci_high - a.ci_low


def test_confidence_with_control_uses_controlled_std_error():
    res = price_asian(**BASE, n_paths=5_000, control="geometric", confidence=0.99)
    assert res.ci_low == res.price - z_value(0.99) * res.std_error
    assert res.std_error < res.std_error_no_control


@pytest.mark.parametrize("bad", [0.0, 1.0, 1.2])
def test_pricer_rejects_bad_confidence(bad):
    with pytest.raises(ValueError):
        price_asian(**BASE, n_paths=1_000, confidence=bad)


# --- corrélation antithétique ---------------------------------------------------------------------

def _antithetic_payoffs(option, n, kind, obs="monthly"):
    S = np.concatenate(list(gbm_paths(**MODEL, obs=obs, n_paths=n, seed=SEED, antithetic=True)))
    level = S[:, -1] if kind == "european" else S.mean(axis=1)
    sign = 1.0 if option == "call" else -1.0
    return math.exp(-MODEL["r"] * MODEL["T"]) * np.maximum(sign * (level - 100.0), 0.0)


def test_antithetic_corr_is_none_without_antithetic():
    assert price_asian(**BASE, n_paths=2_000).antithetic_corr is None
    assert MCResult.__dataclass_fields__["antithetic_corr"].default is None


@pytest.mark.parametrize("kind,pricer", [("asian", price_asian), ("european", price_european_mc)])
@pytest.mark.parametrize("option", ["call", "put"])
def test_antithetic_corr_is_pair_correlation_of_payoffs(kind, pricer, option):
    n = 20_000
    res = pricer(**MODEL, K=100.0, option=option, n_paths=n, antithetic=True, batch_size=3_001)
    h = _antithetic_payoffs(option, n, kind)
    expected = np.corrcoef(h[0::2], h[1::2])[0, 1]
    assert res.antithetic_corr == pytest.approx(expected, rel=1e-9)
    assert -1.0 <= res.antithetic_corr < 0.0          # call/put monotones en Z : corrélation < 0


def test_antithetic_corr_with_control_is_on_payoff_not_residual():
    n = 20_000
    res = price_asian(**MODEL, K=100.0, n_paths=n, antithetic=True, control="geometric")
    h = _antithetic_payoffs("call", n, "asian")
    assert res.antithetic_corr == pytest.approx(np.corrcoef(h[0::2], h[1::2])[0, 1], rel=1e-9)
