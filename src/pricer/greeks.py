"""Greeks par différences finies (cours PricingMonteCarlo_2026, slides 58-61).

Différences centrées (slide 60 : biais en ε²·h'''/6, contre ε·h''/2 pour la différence avant) :
    Δ = [P(S0 + h) − P(S0 − h)]/(2h),
    Γ = [P(S0 + h) − 2P(S0) + P(S0 − h)]/h²,
    ν = [P(σ + h_σ) − P(σ − h_σ)]/(2h_σ),
avec h = h_spot·S0 (1 % de S0 par défaut) et h_σ = h_vol (0,01 par défaut).

Nombres aléatoires communs (crn=True, hors cours : le cours tire « M nouveaux tirages » pour le
prix bumpé) : tous les prix sont calculés sur les mêmes normales. Les trajectoires bumpées en S0
sont les trajectoires de base multipliées par (S0 ± h)/S0 (S est linéaire en S0 à normales
fixées) ; celles bumpées en σ sont resimulées avec la même seed. Chaque Greek est alors la moyenne
d'un échantillon par trajectoire, par exemple D_i = [h(S_i⁺) − h(S_i⁻)]/(2h), et son écart-type
est s_D/√N (slide 49).
Sans CRN (crn=False) : les 5 prix (base, S0 + h, S0 − h, σ + h_σ, σ − h_σ) sont calculés sur des
flux contigus et disjoints du LCG (seed du prix k + 1 = état du LCG après les uniformes du prix k),
donc indépendants : se(Δ) = √(se₊² + se₋²)/(2h), se(Γ) = √(se₊² + 4se₀² + se₋²)/h².

Contrôle géométrique (asiatique seulement) : avec CRN, il porte sur l'échantillon du Greek
lui-même, X_D = [g(G⁺) − g(G⁻)]/(2h) etc., d'espérance connue par la formule fermée
(pricer.geometric) aux points bumpés ; b optimal = Cov/Var sur l'échantillon (slide 50). Sans CRN,
chacun des 5 prix est contrôlé séparément (price_asian(control="geometric")).

Greeks fermés de Black-Scholes avec dividende continu q (slide 61) :
    Δ_call = e^{−qT}Φ(d1),  Δ_put = −e^{−qT}Φ(−d1),
    Γ = e^{−qT}φ(d1)/(S0σ√T),  ν = S0e^{−qT}√T·φ(d1)   (ν pour une variation de σ de 1, pas de 1 %).
"""
from __future__ import annotations

import math
import time
from dataclasses import asdict, dataclass

import numpy as np

from pricer.asian import REFERENCE_SEED, _Moments, price_asian, price_european_mc
from pricer.black_scholes import OPTIONS, _check, norm_cdf
from pricer.geometric import geometric_asian_price
from pricer.paths import DEFAULT_BATCH, gbm_paths, n_obs_from
from pricer.rng import PARK_MILLER_A, PARK_MILLER_M

KINDS = ("asian", "european")
_SQRT_2PI = math.sqrt(2.0 * math.pi)


@dataclass(frozen=True)
class FDGreeks:
    kind: str                   # "asian" / "european"
    option: str
    price: float                # prix au point de base (contrôlé si control)
    price_se: float
    delta: float
    delta_se: float
    gamma: float
    gamma_se: float
    vega: float                 # pour une variation de σ de 1
    vega_se: float
    h_spot: float               # h absolu = h_spot_rel·S0
    h_spot_rel: float
    h_vol: float
    n_paths: int
    seed: int
    rng_method: str
    n_obs: int
    crn: bool
    control: str | None
    seeds: tuple                # seeds utilisées (1 avec CRN, 5 sans)
    elapsed: float

    def as_dict(self) -> dict:
        return asdict(self)


def bs_greeks(S0, K, sigma, r, T, q=0.0, option: str = "call") -> dict:
    """Δ, Γ, ν fermés de Black-Scholes avec q (slide 61) ; σ√T > 0 requis."""
    v = _check(S0, K, sigma, r, T, q, option)
    S0, K, sigma, r, T, q = v["S0"], v["K"], v["sigma"], v["r"], v["T"], v["q"]
    vol = sigma * math.sqrt(T)
    if vol == 0.0:
        raise ValueError("Greeks non définis pour σ√T = 0")
    d1 = (math.log(S0 / K) + (r - q + 0.5 * sigma * sigma) * T) / vol
    phi = math.exp(-0.5 * d1 * d1) / _SQRT_2PI
    disc_q = math.exp(-q * T)
    delta = disc_q * norm_cdf(d1) if option == "call" else -disc_q * norm_cdf(-d1)
    return dict(delta=delta, gamma=disc_q * phi / (S0 * vol),
                vega=S0 * disc_q * math.sqrt(T) * phi)


def _jump_seed(seed: int, n_uniforms: int) -> int:
    """État du LCG Park-Miller après n tirages : x_n = a^n·x_0 mod m."""
    return pow(PARK_MILLER_A, n_uniforms, PARK_MILLER_M) * int(seed) % PARK_MILLER_M


def _estimate(m: _Moments, control_mean: float | None) -> tuple[float, float]:
    if control_mean is None:
        return m.mean, math.sqrt(m.variance / m.n)
    b = m.beta_optimal
    return m.mean - b * (m.mean_x - control_mean), math.sqrt(m.residual_variance(b) / m.n)


def _crn(S0, K, sigma, r, T, q, option, kind, obs, n_paths, seed, rng_method, h, hv, control,
         batch_size):
    disc = math.exp(-r * T)
    sign = 1.0 if option == "call" else -1.0

    def pay(level):
        return disc * np.maximum(sign * (level - K), 0.0)

    def level(S):
        return S[:, -1] if kind == "european" else S.mean(axis=1)

    def geo(S):
        return np.exp(np.log(S).mean(axis=1))

    up, dn = (S0 + h) / S0, (S0 - h) / S0
    m = {k: _Moments() for k in ("price", "delta", "gamma", "vega")}
    sim = dict(r=r, T=T, q=q, obs=obs, n_paths=n_paths, seed=seed, rng_method=rng_method,
               batch_size=batch_size)
    gens = [gbm_paths(S0, s, **sim) for s in (sigma, sigma + hv, sigma - hv)]
    for S, Svu, Svd in zip(*gens):
        a = level(S)
        y0, yu, yd = pay(a), pay(a * up), pay(a * dn)
        yv = (pay(level(Svu)) - pay(level(Svd))) / (2.0 * hv)
        xs = dict(price=None, delta=None, gamma=None, vega=None)
        if control:
            g = geo(S)
            x0, xu, xd = pay(g), pay(g * up), pay(g * dn)
            xs = dict(price=x0, delta=(xu - xd) / (2.0 * h), gamma=(xu - 2.0 * x0 + xd) / h**2,
                      vega=(pay(geo(Svu)) - pay(geo(Svd))) / (2.0 * hv))
        m["price"].add(y0, xs["price"])
        m["delta"].add((yu - yd) / (2.0 * h), xs["delta"])
        m["gamma"].add((yu - 2.0 * y0 + yd) / h**2, xs["gamma"])
        m["vega"].add(yv, xs["vega"])

    means = dict(price=None, delta=None, gamma=None, vega=None)
    if control:
        def ex(**kw):
            p = dict(S0=S0, K=K, sigma=sigma, r=r, T=T, q=q, option=option, obs=obs)
            return geometric_asian_price(**{**p, **kw})
        e0, eu, ed = ex(), ex(S0=S0 + h), ex(S0=S0 - h)
        means = dict(price=e0, delta=(eu - ed) / (2.0 * h), gamma=(eu - 2.0 * e0 + ed) / h**2,
                     vega=(ex(sigma=sigma + hv) - ex(sigma=sigma - hv)) / (2.0 * hv))
    out = {k: _estimate(m[k], means[k]) for k in m}
    return out, (int(seed),)


def _independent(S0, K, sigma, r, T, q, option, kind, obs, n_paths, seed, rng_method, h, hv,
                 control, batch_size):
    points = [dict(), dict(S0=S0 + h), dict(S0=S0 - h), dict(sigma=sigma + hv),
              dict(sigma=sigma - hv)]
    base = dict(S0=S0, K=K, sigma=sigma, r=r, T=T, q=q, option=option, obs=obs,
                n_paths=n_paths, rng_method=rng_method, batch_size=batch_size)
    res, seeds, s = [], [], int(seed)
    for bump in points:
        kw = {**base, **bump, "seed": s}
        x = (price_asian(**kw, control=control) if kind == "asian"
             else price_european_mc(**kw))
        res.append(x)
        seeds.append(s)
        s = _jump_seed(s, x.n_uniforms)
    p0, pu, pd, pvu, pvd = res
    out = dict(
        price=(p0.price, p0.std_error),
        delta=((pu.price - pd.price) / (2.0 * h), math.hypot(pu.std_error, pd.std_error) / (2 * h)),
        gamma=((pu.price - 2.0 * p0.price + pd.price) / h**2,
               math.sqrt(pu.std_error**2 + 4.0 * p0.std_error**2 + pd.std_error**2) / h**2),
        vega=((pvu.price - pvd.price) / (2.0 * hv),
              math.hypot(pvu.std_error, pvd.std_error) / (2.0 * hv)),
    )
    return out, tuple(seeds)


def fd_greeks(S0, K, sigma, r, T, q=0.0, option: str = "call", kind: str = "asian",
              obs="monthly", n_paths: int = 100_000, seed=REFERENCE_SEED,
              rng_method: str = "inverse", h_spot: float = 0.01, h_vol: float = 0.01,
              control=None, crn: bool = True, batch_size: int = DEFAULT_BATCH) -> FDGreeks:
    """Δ, Γ, ν par différences centrées, avec ou sans nombres aléatoires communs.

    kind = "asian" (moyenne arithmétique, comme price_asian) ou "european" (payoff sur la
    dernière date ; obs=1 pour un pas unique). h_spot est relatif (h = h_spot·S0), h_vol absolu.
    control = None ou "geometric" (asiatique seulement).
    """
    if kind not in KINDS:
        raise ValueError(f"kind inconnu {kind!r} ; choix : {KINDS}")
    if option not in OPTIONS:
        raise ValueError(f"option inconnue {option!r} ; choix : {OPTIONS}")
    if control not in (None, "geometric"):
        raise ValueError(f"control inconnu {control!r} ; choix : None, 'geometric'")
    if control and kind != "asian":
        raise NotImplementedError("le contrôle géométrique n'est défini que pour l'asiatique")
    S0, sigma = float(S0), float(sigma)
    if not (0.0 < h_spot < 1.0):
        raise ValueError(f"h_spot (relatif) doit être dans ]0, 1[, reçu {h_spot!r}")
    if not (0.0 < h_vol < sigma):
        raise ValueError(f"h_vol doit être dans ]0, σ[ = ]0, {sigma}[, reçu {h_vol!r}")
    h = h_spot * S0
    start = time.perf_counter()
    args = (S0, float(K), sigma, float(r), float(T), float(q), option, kind, obs, n_paths, seed,
            rng_method, h, float(h_vol), control, batch_size)
    out, seeds = _crn(*args) if crn else _independent(*args)
    elapsed = time.perf_counter() - start
    return FDGreeks(kind=kind, option=option, price=out["price"][0], price_se=out["price"][1],
                    delta=out["delta"][0], delta_se=out["delta"][1], gamma=out["gamma"][0],
                    gamma_se=out["gamma"][1], vega=out["vega"][0], vega_se=out["vega"][1],
                    h_spot=h, h_spot_rel=float(h_spot), h_vol=float(h_vol), n_paths=n_paths,
                    seed=seed, rng_method=rng_method, n_obs=n_obs_from(obs, T), crn=bool(crn),
                    control=control, seeds=seeds, elapsed=elapsed)
