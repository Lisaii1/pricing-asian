"""Tests du générateur congruentiel linéaire (cours PricingMonteCarlo_2026, slides 7-12)."""
from __future__ import annotations

import numpy as np
import pytest

from pricer.rng import LCG

PARK_MILLER_M = 2**31 - 1


def naive_loop(seed: int, n: int, a: int = 16807, m: int = PARK_MILLER_M, c: int = 0) -> np.ndarray:
    """Référence : récurrence du cours x_{i+1} = (a x_i + c) mod m, u = x/m, en entiers Python."""
    x = seed
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        x = (a * x + c) % m
        out[i] = x / m
    return out


# --- validation des paramètres -------------------------------------------------------

def test_seed_zero_rejected_for_pure_lcg():
    with pytest.raises(ValueError, match="x0 = 0"):
        LCG(0)


@pytest.mark.parametrize("seed", [-1, PARK_MILLER_M, PARK_MILLER_M + 5])
def test_seed_out_of_range_rejected(seed):
    with pytest.raises(ValueError, match=r"\[1, m"):
        LCG(seed)


def test_seed_zero_allowed_for_mixed_lcg():
    g = LCG(0, a=5, m=16, c=3)
    assert g.state == 0


@pytest.mark.parametrize("seed", [-1, 16])
def test_seed_out_of_range_rejected_for_mixed(seed):
    with pytest.raises(ValueError, match=r"\[0, m"):
        LCG(seed, a=5, m=16, c=3)


def test_non_integer_seed_rejected():
    with pytest.raises(TypeError):
        LCG(1.5)


def test_modulus_too_large_rejected():
    # m <= 2**32 garantit l'absence de dépassement uint64 (voir preuve dans rng.py)
    with pytest.raises(ValueError, match="2\\*\\*32"):
        LCG(1, a=3, m=2**32 + 1)


# --- exemples du cours ---------------------------------------------------------------

def test_course_example_1_slide_7():
    # a = 3, m = 5, x0 = 1 : 3, 4, 2, 1, 3, 4, 2, 1
    g = LCG(1, a=3, m=5)
    assert list(np.rint(g.uniforms(8) * 5).astype(int)) == [3, 4, 2, 1, 3, 4, 2, 1]


def test_course_example_2_slide_7():
    # a = 3, m = 5, x0 = 2 : la suite démarre à x0 = 2 puis 1, 3, 4, 2, ...
    g = LCG(2, a=3, m=5)
    assert list(np.rint(g.uniforms(7) * 5).astype(int)) == [1, 3, 4, 2, 1, 3, 4]


# --- (a) reproductibilité ---------------------------------------------------------------

def test_same_seed_same_sequence():
    assert np.array_equal(LCG(12345).uniforms(10_000), LCG(12345).uniforms(10_000))


def test_different_seed_different_sequence():
    assert not np.array_equal(LCG(12345).uniforms(100), LCG(12346).uniforms(100))


# --- (b) vectorisé == boucle naïve, octet pour octet ----------------------------------

@pytest.mark.parametrize(
    "seed,a,m",
    [
        (1, 16807, PARK_MILLER_M),          # Park-Miller (cours, figure 2)
        (987654321, 39373, PARK_MILLER_M),  # L'Ecuyer (cours, figure 2)
        (42, 742938285, PARK_MILLER_M),     # Fishman-Moore (cours, figure 2)
        (42, 950706376, PARK_MILLER_M),
        (42, 1226874159, PARK_MILLER_M),
        (7, 40692, 2147483399),             # L'Ecuyer
        (7, 40014, 2147483563),             # L'Ecuyer
    ],
)
def test_vectorized_equals_naive_loop_bytewise(seed, a, m):
    n = 100_000
    fast = LCG(seed, a=a, m=m).uniforms(n)
    ref = naive_loop(seed, n, a=a, m=m)
    assert fast.dtype == np.float64
    assert fast.tobytes() == ref.tobytes()


def test_vectorized_equals_naive_loop_mixed():
    # LCG mixte de période complète (Hull-Dobell) : m = 2**32, a = 1664525, c = 1013904223
    seed, a, m, c = 2026, 1664525, 2**32, 1013904223
    n = 100_000
    fast = LCG(seed, a=a, m=m, c=c).uniforms(n)
    ref = naive_loop(seed, n, a=a, m=m, c=c)
    assert fast.tobytes() == ref.tobytes()


@pytest.mark.parametrize("n", [0, 1, 2, 3, 4095, 4096, 4097, 10_001])
def test_vectorized_equals_naive_loop_at_block_edges(n):
    fast = LCG(31337).uniforms(n)
    assert fast.tobytes() == naive_loop(31337, n).tobytes()


def test_chunked_calls_equal_single_call():
    g = LCG(5)
    parts = np.concatenate([g.uniforms(k) for k in (1, 4096, 3, 9000, 0, 17)])
    assert parts.tobytes() == LCG(5).uniforms(parts.size).tobytes()


# --- (c) valeur publiée de Park & Miller (1988) -----------------------------------------

def test_park_miller_1988_published_value():
    g = LCG(1)
    g.uniforms(10_000)
    assert g.state == 1043618065


# --- (d) ni 0 ni 1 ------------------------------------------------------------------------

def test_uniforms_strictly_inside_unit_interval():
    u = LCG(1).uniforms(1_000_000)
    assert u.min() > 0.0
    assert u.max() < 1.0


def test_extreme_states_map_inside_unit_interval():
    # x = 1 et x = m - 1 sont les états extrêmes d'un LCG pur
    lo = LCG(1, a=1, m=PARK_MILLER_M).uniforms(1)[0]   # a = 1 : x reste à 1
    hi = LCG(PARK_MILLER_M - 1, a=1, m=PARK_MILLER_M).uniforms(1)[0]
    assert 0.0 < lo < hi < 1.0


# --- (e) état sauvegardable ------------------------------------------------------------

def test_state_save_and_resume():
    g = LCG(777)
    first = g.uniforms(5_000)
    saved = g.get_state()
    rest = g.uniforms(5_000)

    resumed = LCG.from_state(saved)
    assert resumed.uniforms(5_000).tobytes() == rest.tobytes()
    assert np.concatenate([first, rest]).tobytes() == LCG(777).uniforms(10_000).tobytes()


def test_set_state_rewinds():
    g = LCG(99)
    saved = g.get_state()
    a = g.uniforms(1000)
    g.set_state(saved)
    assert g.uniforms(1000).tobytes() == a.tobytes()


def test_set_state_validates():
    g = LCG(99)
    with pytest.raises(ValueError):
        g.set_state({"a": 16807, "m": PARK_MILLER_M, "c": 0, "x": 0})


def test_count_tracks_uniforms_drawn():
    g = LCG(3)
    g.uniforms(10)
    g.uniforms(4097)
    assert g.count == 4107


# --- tests statistiques élémentaires (cours slide 6 : H0 iid uniformes) ------------------

def test_uniform_moments_and_ks():
    from scipy import stats  # référence autorisée dans tests/

    n = 1_000_000
    u = LCG(20261117).uniforms(n)
    assert abs(u.mean() - 0.5) < 5 * np.sqrt(1 / 12 / n)
    assert abs(u.var() - 1 / 12) < 5 * np.sqrt(1 / 180 / n)
    ks = stats.kstest(u, "uniform")
    assert ks.pvalue > 1e-3
    ac1 = np.corrcoef(u[:-1], u[1:])[0, 1]
    assert abs(ac1) < 5 / np.sqrt(n)
