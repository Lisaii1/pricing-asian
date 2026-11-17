"""Tests des générateurs de loi normale (cours PricingMonteCarlo_2026 slides 13-24,
polycopié Haqueberge 2018 pp. 10-11 et annexe PPND16 pp. 22-23).

SciPy sert uniquement de référence ici (autorisé dans tests/).
"""
from __future__ import annotations

import math

import numpy as np
import pytest
from scipy import special, stats

from pricer.normals import (
    AS241,
    HASTINGS_C,
    HASTINGS_D,
    METHODS,
    NormalSample,
    hastings,
    normals,
    ppnd16,
)
from pricer.rng import LCG, PARK_MILLER_M

SEED = 20261117
N_STAT = 1_000_000

# Coefficients PPND16 tels qu'imprimés dans le polycopié Haqueberge (annexe, pp. 22-23),
# arrondis à 15 chiffres significatifs par VBA. Ils servent à contrôler la table pleine
# précision (Wichura 1988) utilisée dans src/.
COURSE_VBA = {
    "a": [3.38713287279637, 133.141667891784, 1971.59095030655, 13731.6937655095,
          45921.9539315499, 67265.7709270087, 33430.5755835881, 2509.08092873012],
    "b": [0, 42.3133307016009, 687.187007492058, 5394.19602142475,
          21213.7943015866, 39307.8958000927, 28729.0857357219, 5226.49527885285],
    "c": [1.42343711074968, 4.63033784615655, 5.76949722146069, 3.6478483247632,
          1.27045825245237, 0.241780725177451, 2.27238449892692e-02, 7.74545014278341e-04],
    "d": [0, 2.05319162663776, 1.6763848301838, 0.6897673349851,
          0.14810397642748, 1.51986665636165e-02, 5.47593808499535e-04, 1.05075007164442e-09],
    "e": [6.6579046435011, 5.46378491116411, 1.78482653991729, 0.296560571828505,
          2.65321895265761e-02, 1.24266094738808e-03, 2.71155556874349e-05, 2.01033439929229e-07],
    "f": [0, 0.599832206555888, 0.136929880922736, 1.48753612908506e-02,
          7.86869131145613e-04, 1.84631831751005e-05, 1.42151175831645e-07, 2.04426310338994e-15],
}


def u_grid() -> np.ndarray:
    """Grille de u : cœur régulier, queues logarithmiques, bornes atteignables par le LCG."""
    core = np.linspace(1e-6, 1 - 1e-6, 200_001)
    tails = np.logspace(-300, -6, 2_000)
    lcg_edges = np.array([1 / PARK_MILLER_M, 2 / PARK_MILLER_M, 1 - 2 / PARK_MILLER_M,
                          (PARK_MILLER_M - 1) / PARK_MILLER_M])
    return np.unique(np.concatenate([core, tails, 1 - tails[tails > 1e-15], lcg_edges]))


# --- inverse de Phi : AS241 / PPND16 ---------------------------------------------------

def test_as241_table_matches_course_vba_coefficients():
    for key, course in COURSE_VBA.items():
        ours = AS241[key]
        assert len(ours) == 8
        for k, (o, v) in enumerate(zip(ours, course)):
            if v == 0:
                assert o == 0, f"{key}[{k}]"
            else:
                assert abs(o - v) <= 1e-14 * abs(v), f"{key}[{k}] : {o!r} vs cours {v!r}"


def test_as241_against_scipy_ndtri_on_lcg_range():
    # Plage atteignable par Park-Miller : u ∈ [1/m, 1 − 1/m], |z| ≤ 6,3 : écart absolu < 1e-14.
    u = u_grid()
    u = u[(u >= 1 / PARK_MILLER_M) & (u <= 1 - 1 / PARK_MILLER_M)]
    err = np.abs(ppnd16(u) - special.ndtri(u))
    assert err.max() < 1e-14, f"écart max AS241 vs ndtri = {err.max():.3e}"


def test_as241_against_scipy_ndtri_relative_in_far_tails():
    # Justification mesurée de l'exception au seuil absolu 1e-14 : dans les queues extrêmes
    # (u jusqu'à 1e-300, |z| jusqu'à 37) l'écart absolu atteint 1,78e-14 (u ≈ 1,9e-206,
    # z ≈ −30,6) mais l'écart relatif reste < 1e-15, soit quelques ulp.
    u = u_grid()
    ref = special.ndtri(u)
    nz = ref != 0
    rel = np.abs(ppnd16(u)[nz] - ref[nz]) / np.abs(ref[nz])
    assert rel.max() < 2e-15, f"écart relatif max AS241 vs ndtri = {rel.max():.3e}"


def test_as241_known_points():
    assert ppnd16(np.array([0.5]))[0] == 0.0
    assert abs(ppnd16(np.array([0.975]))[0] - special.ndtri(0.975)) < 1e-15


def test_as241_is_odd():
    # u dyadiques k / 2^20 : 1 − u est alors exact en float64 (sinon l'arrondi de 1 − u
    # fausse la comparaison près de 0).
    u = np.arange(1, 2**19 + 1, 37) / 2.0**20
    assert np.max(np.abs(ppnd16(u) + ppnd16(1 - u))) < 1e-14


@pytest.mark.parametrize("bad", [0.0, 1.0, -0.1, 1.1, np.nan])
def test_as241_rejects_out_of_domain(bad):
    with pytest.raises(ValueError):
        ppnd16(np.array([0.3, bad]))


# --- inverse de Phi : Hastings (slide 24) ------------------------------------------------

def test_hastings_coefficients_are_course_values():
    assert HASTINGS_C == (2.515517, 0.802853, 0.010328)
    assert HASTINGS_D == (1.432788, 0.189269, 0.001308)


def test_hastings_error_matches_course_precision():
    u = u_grid()
    u = u[(u >= 1e-12) & (u <= 1 - 1e-12)]
    err = np.abs(hastings(u) - special.ndtri(u))
    # le cours annonce une précision de 0,45e-3 (Abramowitz-Stegun 26.2.23 : |eps| < 4.5e-4)
    assert err.max() < 4.5e-4, f"écart max Hastings vs ndtri = {err.max():.3e}"
    assert err.max() > 1e-5  # c'est bien une approximation, pas AS241


# --- API normals() -------------------------------------------------------------------------

def test_unknown_method_rejected():
    with pytest.raises(ValueError, match="method"):
        normals(10, "ziggurat", SEED)


def test_unknown_precision_rejected():
    with pytest.raises(ValueError, match="precision"):
        normals(10, "inverse", SEED, precision="moro")


def test_seed_and_lcg_are_exclusive():
    with pytest.raises(ValueError):
        normals(10, "inverse", SEED, lcg=LCG(1))


def test_seed_required_without_lcg():
    with pytest.raises(ValueError, match="seed"):
        normals(10, "inverse", None)


def test_seed_zero_rejected_through_lcg():
    with pytest.raises(ValueError, match="x0 = 0"):
        normals(10, "box_muller", 0)


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("n", [0, 1, 2, 7, 1000])
def test_shape_dtype_and_consumption(method, n):
    g = LCG(SEED)
    s = normals(n, method, lcg=g)
    assert isinstance(s, NormalSample)
    assert s.z.shape == (n,) and s.z.dtype == np.float64
    assert np.all(np.isfinite(s.z))
    assert s.n_uniforms == g.count  # tout ce qui a été tiré du LCG est compté
    assert s.method == method


@pytest.mark.parametrize("method", METHODS)
def test_same_seed_same_normals(method):
    assert normals(5000, method, SEED).z.tobytes() == normals(5000, method, SEED).z.tobytes()


def test_inverse_consumes_one_uniform_per_normal():
    s = normals(1001, "inverse", SEED)
    assert s.n_uniforms == 1001
    u = LCG(SEED).uniforms(1001)
    assert s.z.tobytes() == ppnd16(u).tobytes()
    assert s.acceptance_rate is None


def test_inverse_hastings_option():
    s = normals(1001, "inverse", SEED, precision="hastings")
    assert s.z.tobytes() == hastings(LCG(SEED).uniforms(1001)).tobytes()


def test_box_muller_course_formula():
    n = 1001
    s = normals(n, "box_muller", SEED)
    u = LCG(SEED).uniforms(2 * math.ceil(n / 2))
    u1, u2 = u[0::2], u[1::2]
    r = -2 * np.log(u1)
    v = 2 * np.pi * u2
    ref = np.empty(2 * u1.size)
    ref[0::2] = np.sqrt(r) * np.cos(v)
    ref[1::2] = np.sqrt(r) * np.sin(v)
    assert np.array_equal(s.z, ref[:n])
    assert s.n_uniforms == 2 * math.ceil(n / 2)


def polar_reference(n: int, g: LCG) -> tuple[list[float], int]:
    """Boucle scalaire du cours (slide 23, avec V = 2U - 1)."""
    out, candidates = [], 0
    while len(out) < n:
        u1, u2 = g.uniforms(2)
        candidates += 1
        v1, v2 = 2 * u1 - 1, 2 * u2 - 1
        s = v1 * v1 + v2 * v2
        if 0 < s < 1:
            y = math.sqrt(-2 * math.log(s) / s)
            out += [v1 * y, v2 * y]
    return out[:n], candidates


def test_polar_equals_scalar_reference_and_resumes_stream():
    n = 2001
    g_fast, g_ref = LCG(SEED), LCG(SEED)
    s = normals(n, "polar", lcg=g_fast)
    ref, cand = polar_reference(n, g_ref)
    np.testing.assert_allclose(s.z, ref, rtol=0, atol=1e-15)
    assert s.n_candidates == cand
    assert s.n_uniforms == 2 * cand
    # le flux reprend exactement après le dernier candidat utilisé
    assert g_fast.uniforms(10).tobytes() == g_ref.uniforms(10).tobytes()


C_AR = math.sqrt(2 * math.e / math.pi)


def ar_reference(n: int, g: LCG) -> tuple[list[float], int]:
    """Demi-normale par rejet sur une exponentielle E(1) (c = sqrt(2e/pi)), puis signe.
    Chaque candidat consomme un triplet (U1 -> X = -log(1-U1), U2 -> test, U3 -> signe)."""
    out, candidates = [], 0
    while len(out) < n:
        u1, u2, u3 = g.uniforms(3)
        candidates += 1
        x = -math.log(1 - u1)
        if u2 <= math.exp(-0.5 * (x - 1) ** 2):
            out.append(x if u3 <= 0.5 else -x)
    return out, candidates


def test_acceptance_rejection_equals_scalar_reference_and_resumes_stream():
    n = 2001
    g_fast, g_ref = LCG(SEED), LCG(SEED)
    s = normals(n, "acceptance_rejection", lcg=g_fast)
    ref, cand = ar_reference(n, g_ref)
    np.testing.assert_allclose(s.z, ref, rtol=0, atol=1e-15)
    assert s.n_candidates == cand
    assert s.n_uniforms == 3 * cand
    assert g_fast.uniforms(10).tobytes() == g_ref.uniforms(10).tobytes()


@pytest.mark.parametrize("method", ["inverse", "box_muller"])
def test_zero_uniform_from_mixed_lcg_is_detected(method):
    # LCG mixte a=5, m=16, c=3 de période complète : x = 0 apparaît dans les 16 premiers tirages
    with pytest.raises(ValueError, match="u = 0"):
        normals(40, method, lcg=LCG(1, a=5, m=16, c=3))


# --- tests statistiques sur 10^6 tirages ------------------------------------------------

STAT_CASES = [
    ("inverse", {}),
    ("inverse", {"precision": "hastings"}),
    ("box_muller", {}),
    ("polar", {}),
    ("acceptance_rejection", {}),
]


@pytest.fixture(scope="module", params=STAT_CASES, ids=lambda c: c[0] + ("-" + c[1]["precision"] if c[1] else ""))
def big_sample(request):
    method, opts = request.param
    return normals(N_STAT, method, SEED, **opts)


def test_moments(big_sample):
    z, n = big_sample.z, N_STAT
    assert abs(z.mean()) < 5 / np.sqrt(n)
    assert abs(z.var() - 1) < 5 * np.sqrt(2 / n)
    assert abs(stats.skew(z)) < 5 * np.sqrt(6 / n)
    assert abs(stats.kurtosis(z)) < 5 * np.sqrt(24 / n)  # kurtosis en excès


def test_kolmogorov_smirnov(big_sample):
    ks = stats.kstest(big_sample.z, "norm")
    assert ks.pvalue > 1e-3, f"KS p-value = {ks.pvalue:.4g} (seed {SEED})"


def test_lag1_autocorrelation(big_sample):
    z = big_sample.z
    assert abs(np.corrcoef(z[:-1], z[1:])[0, 1]) < 5 / np.sqrt(N_STAT)


def test_acceptance_rates(big_sample):
    s = big_sample
    if s.method == "polar":
        p = math.pi / 4
    elif s.method == "acceptance_rejection":
        p = 1 / C_AR
    else:
        assert s.acceptance_rate is None
        return
    tol = 5 * math.sqrt(p * (1 - p) / s.n_candidates)
    assert abs(s.acceptance_rate - p) < tol, f"{s.method}: {s.acceptance_rate:.6f} vs {p:.6f}"
