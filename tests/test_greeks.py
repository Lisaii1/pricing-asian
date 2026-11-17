"""Greeks par différences finies (cours, slides 58-61).

Différences centrées (slide 60, biais en h²·h'''/6) :
    Δ = [P(S0 + h) − P(S0 − h)]/(2h),  Γ = [P(S0 + h) − 2P(S0) + P(S0 − h)]/h²,
    ν = [P(σ + h_σ) − P(σ − h_σ)]/(2h_σ),  h = 1 % de S0, h_σ = 0,01.
Nombres aléatoires communs (CRN) : les prix bumpés sont calculés sur les mêmes normales ; sans CRN,
chaque prix a son propre flux (flux contigus et disjoints du même LCG).
Greeks fermés de Black-Scholes avec q (slide 61) :
    Δ_call = e^{−qT}Φ(d1), Δ_put = −e^{−qT}Φ(−d1), Γ = e^{−qT}φ(d1)/(S0σ√T), ν = S0e^{−qT}√T φ(d1).
Tolérances : 3 écarts-types, plus l'erreur de troncature des différences finies calculée sur le
prix fermé (le quotient aux différences du prix exact est l'espérance de l'estimateur CRN).
"""
from __future__ import annotations

import math

import pytest

from pricer.asian import price_asian, price_european_mc
from pricer.black_scholes import bs_price
from pricer.greeks import FDGreeks, bs_greeks, fd_greeks

SEED = 20261117
CASES = [
    dict(S0=100.0, K=100.0, sigma=0.20, r=0.03, T=1.0, q=0.01),
    dict(S0=42.0, K=40.0, sigma=0.20, r=0.10, T=0.5, q=0.0),
    dict(S0=100.0, K=120.0, sigma=0.35, r=0.05, T=2.0, q=0.04),
]
BASE = CASES[0]


def _fd_exact(case, option, h_rel=0.01, h_vol=0.01):
    """Quotients aux différences centrées du prix BS exact (espérance de l'estimateur CRN)."""
    S0, s = case["S0"], case["sigma"]
    h = h_rel * S0

    def p(**kw):
        return bs_price(**{**case, **kw}, option=option)

    up, mid, dn = p(S0=S0 + h), p(), p(S0=S0 - h)
    return dict(delta=(up - dn) / (2 * h), gamma=(up - 2 * mid + dn) / h**2,
                vega=(p(sigma=s + h_vol) - p(sigma=s - h_vol)) / (2 * h_vol))


# --- Greeks fermés -------------------------------------------------------------------------------

@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("option", ["call", "put"])
def test_bs_greeks_match_numerical_derivatives_of_bs_price(case, option):
    g = bs_greeks(**case, option=option)
    num = _fd_exact(case, option, h_rel=1e-4, h_vol=1e-5)
    # oracle numérique : troncature h²·f'''/6 ≈ 2e−8 pour h = 1e−4·S0 (mesuré, put K = 40)
    assert g["delta"] == pytest.approx(num["delta"], rel=1e-6, abs=1e-9)
    assert g["gamma"] == pytest.approx(num["gamma"], rel=1e-4)
    assert g["vega"] == pytest.approx(num["vega"], rel=1e-6)


@pytest.mark.parametrize("case", CASES)
def test_bs_greeks_call_put_relations(case):
    c, p = bs_greeks(**case, option="call"), bs_greeks(**case, option="put")
    assert c["delta"] - p["delta"] == pytest.approx(math.exp(-case["q"] * case["T"]), rel=1e-14)
    assert c["gamma"] == p["gamma"] and c["vega"] == p["vega"]


def test_bs_greeks_course_formulas_by_hand():
    S0, K, s, r, T, q = 100.0, 95.0, 0.3, 0.04, 2.0, 0.02
    d1 = (math.log(S0 / K) + (r - q + 0.5 * s * s) * T) / (s * math.sqrt(T))
    phi = math.exp(-0.5 * d1 * d1) / math.sqrt(2 * math.pi)
    Phi = 0.5 * math.erfc(-d1 / math.sqrt(2))
    g = bs_greeks(S0, K, s, r, T, q, "put")
    assert g["delta"] == pytest.approx(-math.exp(-q * T) * (1 - Phi), rel=1e-12)
    assert g["gamma"] == pytest.approx(math.exp(-q * T) * phi / (S0 * s * math.sqrt(T)), rel=1e-12)
    assert g["vega"] == pytest.approx(S0 * math.exp(-q * T) * math.sqrt(T) * phi, rel=1e-12)


# --- différences finies européennes vs formules fermées -------------------------------------------

@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("option", ["call", "put"])
def test_european_fd_greeks_within_3_std_of_closed_form(case, option):
    fd = fd_greeks(**case, option=option, kind="european", obs=1, n_paths=200_000)
    exact = bs_greeks(**case, option=option)
    quot = _fd_exact(case, option)
    for name in ("delta", "gamma", "vega"):
        est, se = getattr(fd, name), getattr(fd, f"{name}_se")
        trunc = abs(quot[name] - exact[name])                    # biais de troncature (slide 60)
        assert se > 0.0
        assert abs(est - exact[name]) < 3 * se + trunc, name


def test_fd_greeks_record_steps_and_inputs():
    fd = fd_greeks(**BASE, n_paths=10_000)
    assert isinstance(fd, FDGreeks)
    assert fd.h_spot == pytest.approx(1.0) and fd.h_vol == 0.01
    assert fd.crn is True and fd.kind == "asian" and fd.n_paths == 10_000 and fd.seed == SEED


# --- CRN : même dérivée que les prix du pricer sur la même seed ------------------------------------

def test_asian_crn_greeks_equal_pricer_differences_on_same_seed():
    n, h = 20_000, 1.0
    fd = fd_greeks(**BASE, n_paths=n)

    def p(**kw):
        return price_asian(**{**BASE, **kw}, n_paths=n, seed=SEED).price

    up, mid, dn = p(S0=101.0), p(), p(S0=99.0)
    assert fd.delta == pytest.approx((up - dn) / (2 * h), rel=1e-9)
    assert fd.gamma == pytest.approx((up - 2 * mid + dn) / h**2, rel=1e-6)
    assert fd.vega == pytest.approx((p(sigma=0.21) - p(sigma=0.19)) / 0.02, rel=1e-9)
    assert fd.price == pytest.approx(mid, rel=1e-12)


def test_without_crn_prices_use_disjoint_contiguous_streams():
    n = 10_000
    fd = fd_greeks(**BASE, n_paths=n, crn=False)
    assert len(fd.seeds) == 5 and len(set(fd.seeds)) == 5 and fd.seeds[0] == SEED

    def p(seed, **kw):
        return price_asian(**{**BASE, **kw}, n_paths=n, seed=seed)

    up, dn = p(fd.seeds[1], S0=101.0), p(fd.seeds[2], S0=99.0)
    assert fd.delta == pytest.approx((up.price - dn.price) / 2.0, rel=1e-12)
    assert fd.delta_se == pytest.approx(math.hypot(up.std_error, dn.std_error) / 2.0, rel=1e-12)


@pytest.mark.parametrize("kind,obs", [("asian", "monthly"), ("european", 1)])
def test_crn_reduces_delta_and_vega_std_error(kind, obs):
    a = fd_greeks(**BASE, kind=kind, obs=obs, n_paths=20_000, crn=True)
    b = fd_greeks(**BASE, kind=kind, obs=obs, n_paths=20_000, crn=False)
    assert a.delta_se < b.delta_se / 5
    assert a.vega_se < b.vega_se / 5


# --- contrôle géométrique ------------------------------------------------------------------------

def test_control_reduces_asian_greek_std_errors_and_agrees():
    plain = fd_greeks(**BASE, n_paths=50_000)
    cv = fd_greeks(**BASE, n_paths=50_000, control="geometric")
    assert cv.control == "geometric"
    for name in ("delta", "vega"):
        se_p, se_c = getattr(plain, f"{name}_se"), getattr(cv, f"{name}_se")
        assert se_c < se_p
        assert abs(getattr(cv, name) - getattr(plain, name)) < 3 * se_p


def test_control_price_matches_pricer():
    cv = fd_greeks(**BASE, n_paths=20_000, control="geometric")
    ref = price_asian(**BASE, n_paths=20_000, control="geometric")
    assert cv.price == pytest.approx(ref.price, rel=1e-12)


def test_european_price_matches_pricer():
    fd = fd_greeks(**BASE, kind="european", obs=1, n_paths=20_000)
    assert fd.price == pytest.approx(price_european_mc(**BASE, obs=1, n_paths=20_000).price,
                                     rel=1e-12)


# --- CSV de results/ ---------------------------------------------------------------------------

def test_greeks_csv():
    import csv
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "results" / "p4_greeks.csv"
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3 * 2 * 5
    for r in rows:
        assert float(r["h_spot"]) == pytest.approx(1.0) and float(r["h_vol"]) == 0.01
        if r["kind"] == "european":
            for name in ("delta", "gamma", "vega"):
                trunc = abs(float(r[f"fd_exact_{name}"]) - float(r[f"bs_{name}"]))
                assert abs(float(r[name]) - float(r[f"bs_{name}"])) < (
                    3 * float(r[f"{name}_se"]) + trunc), (r["option"], r["K"], name)
    for kind, control in (("asian", "geometric"), ("european", "")):
        for opt in ("call", "put"):
            for K in ("90.0", "100.0", "110.0"):
                sel = {r["crn"]: r for r in rows if (r["kind"], r["control"], r["option"],
                                                     r["K"]) == (kind, control, opt, K)}
                assert float(sel["True"]["delta_se"]) < float(sel["False"]["delta_se"])


# --- validation ----------------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [dict(h_spot=0.0), dict(h_spot=1.0), dict(h_vol=0.0),
                                 dict(h_vol=0.2), dict(kind="american"),
                                 dict(kind="european", control="geometric")])
def test_fd_greeks_rejects_bad_inputs(bad):
    with pytest.raises((ValueError, NotImplementedError)):
        fd_greeks(**BASE, n_paths=1_000, **bad)
