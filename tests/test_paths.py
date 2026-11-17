"""Tests des trajectoires du MBG (cours PricingMonteCarlo_2026, slides 35 et 42-43).

Schéma exact sur les dates d'observation :
    S_{k+1} = S_k · exp((r − q − σ²/2)Δt_k + σ√Δt_k · Z_k).
Tolérances statistiques = 3 écarts-types de l'estimateur, jamais une tolérance absolue arbitraire.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from pricer.normals import METHODS, normals
from pricer.paths import FREQUENCIES, NormalStream, gbm_paths, n_obs_from, obs_dates

SEED = 20261117
S0, SIGMA, R, Q, T = 100.0, 0.2, 0.03, 0.01, 1.0


def _all_paths(**kw) -> np.ndarray:
    return np.concatenate(list(gbm_paths(**kw)), axis=0)


# --- dates d'observation -----------------------------------------------------------------

def test_frequencies_are_the_prompt_table():
    assert FREQUENCIES == {"daily": 252, "weekly": 52, "monthly": 12, "quarterly": 4}


def test_obs_dates_integer_excludes_s0_by_default():
    d = obs_dates(1.0, 4)
    np.testing.assert_array_equal(d, np.array([0.25, 0.5, 0.75, 1.0]))


def test_obs_dates_include_s0_prepends_zero():
    d = obs_dates(2.0, 4, include_s0=True)
    np.testing.assert_array_equal(d, np.array([0.0, 0.5, 1.0, 1.5, 2.0]))


def test_obs_dates_last_date_is_exactly_T():
    for T_ in (0.25, 0.5, 1.0, 2.0, 1.0 / 3.0):
        for n in (1, 3, 12, 252):
            assert obs_dates(T_, n)[-1] == T_


@pytest.mark.parametrize("freq,T_,expected", [
    ("monthly", 1.0, 12), ("monthly", 0.25, 3), ("monthly", 2.0, 24),
    ("weekly", 0.5, 26), ("daily", 0.5, 126), ("quarterly", 2.0, 8), ("daily", 1.0, 252),
])
def test_n_obs_from_frequency_string(freq, T_, expected):
    assert n_obs_from(freq, T_) == expected
    assert len(obs_dates(T_, freq)) == expected


def test_n_obs_from_integer_is_identity():
    assert n_obs_from(7, 3.0) == 7


@pytest.mark.parametrize("bad", ["yearly", "", 0, -3, 2.5, True, None])
def test_n_obs_invalid_values_raise(bad):
    with pytest.raises((ValueError, TypeError)):
        n_obs_from(bad, 1.0)


def test_n_obs_frequency_rounding_to_zero_raises():
    # quarterly sur T = 0,1 an : round(0,4) = 0 observation → erreur explicite
    with pytest.raises(ValueError):
        n_obs_from("quarterly", 0.1)


@pytest.mark.parametrize("bad_T", [0.0, -1.0, float("nan"), float("inf")])
def test_obs_dates_invalid_maturity_raises(bad_T):
    with pytest.raises(ValueError):
        obs_dates(bad_T, 12)


# --- flux de normales unique ---------------------------------------------------------------

@pytest.mark.parametrize("method", METHODS)
def test_normal_stream_chunks_equal_one_big_draw(method):
    """Le flux découpé en morceaux de tailles impaires redonne exactement un tirage unique."""
    ref = normals(1001, method, seed=SEED).z
    s = NormalStream(SEED, method)
    parts = [s.take(k) for k in (1, 7, 300, 2, 691)]
    np.testing.assert_array_equal(np.concatenate(parts), ref)
    assert s.n_normals == 1001


def test_normal_stream_rejects_unknown_method():
    with pytest.raises(ValueError):
        NormalStream(SEED, "numpy")


# --- schéma exact ----------------------------------------------------------------------------

def test_paths_follow_exact_scheme_path_major():
    """Trajectoire i, date k utilise Z[i·n_obs + k] ; récurrence multiplicative du slide 35."""
    n_obs, n_paths = 5, 3
    z = normals(n_obs * n_paths, "inverse", seed=SEED).z.reshape(n_paths, n_obs)
    t = obs_dates(T, n_obs)
    dt = np.diff(np.concatenate(([0.0], t)))
    S = _all_paths(S0=S0, sigma=SIGMA, r=R, T=T, q=Q, obs=n_obs, n_paths=n_paths, seed=SEED)
    assert S.shape == (n_paths, n_obs)
    for i in range(n_paths):
        s = S0
        for k in range(n_obs):
            s = s * math.exp((R - Q - 0.5 * SIGMA**2) * dt[k] + SIGMA * math.sqrt(dt[k]) * z[i, k])
            assert S[i, k] == pytest.approx(s, rel=1e-13)


def test_paths_include_s0_first_column():
    S = _all_paths(S0=S0, sigma=SIGMA, r=R, T=T, q=Q, obs=4, n_paths=10, seed=SEED,
                   include_s0=True)
    assert S.shape == (10, 5)
    assert (S[:, 0] == S0).all()
    S_ex = _all_paths(S0=S0, sigma=SIGMA, r=R, T=T, q=Q, obs=4, n_paths=10, seed=SEED)
    np.testing.assert_array_equal(S[:, 1:], S_ex)


# --- lois -----------------------------------------------------------------------------------

N_STAT = 200_000


@pytest.fixture(scope="module")
def ST_monthly():
    S = _all_paths(S0=S0, sigma=SIGMA, r=R, T=T, q=Q, obs="monthly", n_paths=N_STAT, seed=SEED)
    return S[:, -1]


def test_mean_ST_is_forward_within_3_std(ST_monthly):
    expected = S0 * math.exp((R - Q) * T)
    se = ST_monthly.std(ddof=1) / math.sqrt(N_STAT)
    assert abs(ST_monthly.mean() - expected) < 3 * se


def test_log_ST_mean_within_3_std(ST_monthly):
    x = np.log(ST_monthly)
    expected = math.log(S0) + (R - Q - 0.5 * SIGMA**2) * T
    se = SIGMA * math.sqrt(T) / math.sqrt(N_STAT)
    assert abs(x.mean() - expected) < 3 * se


def test_log_ST_variance_within_3_std(ST_monthly):
    x = np.log(ST_monthly)
    v = SIGMA**2 * T
    se = v * math.sqrt(2.0 / (N_STAT - 1))     # écart-type de s² pour une loi normale
    assert abs(x.var(ddof=1) - v) < 3 * se


def test_log_increments_variance_matches_dt():
    """Chaque incrément ln S_{k+1} − ln S_k a une variance σ²Δt (contrôle date par date)."""
    S = _all_paths(S0=S0, sigma=SIGMA, r=R, T=2.0, q=Q, obs="quarterly", n_paths=50_000,
                   seed=SEED, include_s0=True)
    inc = np.diff(np.log(S), axis=1)
    v = SIGMA**2 * 0.25
    se = v * math.sqrt(2.0 / (50_000 - 1))
    assert np.all(np.abs(inc.var(axis=0, ddof=1) - v) < 3 * se)


# --- blocs et reproductibilité --------------------------------------------------------------

@pytest.mark.parametrize("method", ["inverse", "box_muller", "polar"])
def test_same_paths_for_different_batch_sizes(method):
    kw = dict(S0=S0, sigma=SIGMA, r=R, T=T, q=Q, obs=7, n_paths=2_345, seed=SEED,
              rng_method=method)
    a = _all_paths(batch_size=50_000, **kw)
    b = _all_paths(batch_size=333, **kw)
    c = _all_paths(batch_size=1, **kw)
    np.testing.assert_array_equal(a, b)
    np.testing.assert_array_equal(a, c)


def test_blocks_never_exceed_batch_size():
    sizes = [blk.shape[0] for blk in gbm_paths(S0=S0, sigma=SIGMA, r=R, T=T, q=Q, obs=12,
                                               n_paths=1_050, seed=SEED, batch_size=400)]
    assert sizes == [400, 400, 250]


def test_same_seed_same_paths_bitwise():
    kw = dict(S0=S0, sigma=SIGMA, r=R, T=T, q=Q, obs="weekly", n_paths=1_000, seed=SEED)
    np.testing.assert_array_equal(_all_paths(**kw), _all_paths(**kw))


def test_other_seed_other_paths():
    kw = dict(S0=S0, sigma=SIGMA, r=R, T=T, q=Q, obs=3, n_paths=100)
    assert not np.array_equal(_all_paths(seed=SEED, **kw), _all_paths(seed=SEED + 1, **kw))


@pytest.mark.parametrize("bad", [dict(n_paths=0), dict(batch_size=0), dict(S0=-1.0),
                                 dict(sigma=-0.1), dict(seed=None)])
def test_invalid_inputs_raise(bad):
    kw = dict(S0=S0, sigma=SIGMA, r=R, T=T, q=Q, obs=3, n_paths=10, seed=SEED)
    kw.update(bad)
    with pytest.raises((ValueError, TypeError)):
        _all_paths(**kw)
