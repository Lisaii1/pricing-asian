"""Option asiatique à moyenne géométrique : formule fermée pour des dates discrètes.

Moyenne géométrique des fixings (cours PricingMonteCarlo_2026, slides 51 et 76) :
    G = (Π_{k=1..n} S(t_k))^{1/n}.
Sous Black-Scholes avec dividende continu q (le slide 76 est écrit avec q = 0),
    ln G = ln S0 + (r − q − σ²/2)·(1/n)Σ_k t_k + (σ/n)·Σ_k W(t_k)
est gaussienne : ln G ~ N(μ_G, σ_G²) avec
    μ_G  = ln S0 + (r − q − σ²/2)·t̄,     t̄ = (1/n)Σ_k t_k,
    σ_G² = (σ²/n²)·Σ_i Σ_j min(t_i, t_j)     (Cov(W(t_i), W(t_j)) = min(t_i, t_j)).
Pour des dates croissantes la double somme vaut Σ_j (2j − 1)·t_{n+1−j} : c'est la variance de
Σ_j W(t_j) du slide 76 (égalité testée). G étant log-normale,
    call = e^{−rT}·[e^{μ_G + σ_G²/2}·Φ(d1) − K·Φ(d2)],
    put  = e^{−rT}·[K·Φ(−d2) − e^{μ_G + σ_G²/2}·Φ(−d1)],
    d2 = (μ_G − ln K)/σ_G,  d1 = d2 + σ_G.
C'est la formule de Black-Scholes d'un MBG de volatilité σ̄ et de dérive r − δ sur l'horizon t̄
(lecture du slide 76 : σ̄² = σ_G²/t̄, δ = σ²/2 − σ̄²/2 ; égalité testée).

Dates t_k = kT/n : t̄ = T(n+1)/(2n) et σ_G² = σ²·T(n+1)(2n+1)/(6n²) (testé contre la forme
générale). Limite n → ∞ : σ_G² → σ²T/3 (Kemna-Vorst continu, hors cours).
S0 compté dans la moyenne (include_s0) : une date t = 0 de plus, n augmente de 1.
Cas σ_G = 0 (hors cours) : limite déterministe e^{−rT}·max(±(e^{μ_G} − K), 0).
"""
from __future__ import annotations

import math

import numpy as np

from pricer.black_scholes import OPTIONS, norm_cdf
from pricer.paths import _check_maturity, _check_model, obs_dates


def _as_dates(dates) -> np.ndarray:
    t = np.asarray(dates, dtype=np.float64).ravel()
    if t.size == 0:
        raise ValueError("il faut au moins une date d'observation")
    if not np.all(np.isfinite(t)) or np.any(t < 0.0):
        raise ValueError("les dates d'observation doivent être finies et ≥ 0")
    return t


def geometric_moments(S0, sigma, r, q, dates) -> tuple[float, float]:
    """(μ_G, σ_G²) de ln G pour des dates d'observation quelconques (t = 0 admis)."""
    S0, sigma, r, q = _check_model(S0, sigma, r, q)
    t = _as_dates(dates)
    n = t.size
    t_bar = float(t.sum()) / n
    mu = math.log(S0) + (r - q - 0.5 * sigma * sigma) * t_bar
    var = sigma * sigma * float(np.minimum.outer(t, t).sum()) / (n * n)
    return mu, var


def geometric_asian_price(S0, K, sigma, r, T, q=0.0, option: str = "call", obs="monthly",
                          include_s0: bool = False, dates=None) -> float:
    """Prix fermé d'un call ou d'un put asiatique à moyenne géométrique, payé en T.

    Mêmes paramètres que price_asian : obs (entier ou fréquence) et include_s0 donnent les
    dates t_k = kT/n. ``dates`` les remplace par des dates quelconques de [0, T].
    """
    if option not in OPTIONS:
        raise ValueError(f"option inconnue {option!r} ; choix : {OPTIONS}")
    K = float(K)
    if not (math.isfinite(K) and K > 0.0):
        raise ValueError(f"K doit être > 0, reçu {K!r}")
    T = _check_maturity(T)
    if dates is None:
        t = obs_dates(T, obs, include_s0)
    else:
        t = _as_dates(dates)
        if np.any(t > T):
            raise ValueError("les dates d'observation doivent être ≤ T")
    mu, var = geometric_moments(S0, sigma, r, q, t)
    disc = math.exp(-float(r) * T)
    sig_g = math.sqrt(var)
    if sig_g == 0.0:
        intrinsic = math.exp(mu) - K
        return disc * (max(intrinsic, 0.0) if option == "call" else max(-intrinsic, 0.0))
    fwd = math.exp(mu + 0.5 * var)                 # E[G]
    d2 = (mu - math.log(K)) / sig_g
    d1 = d2 + sig_g
    if option == "call":
        return disc * (fwd * norm_cdf(d1) - K * norm_cdf(d2))
    return disc * (K * norm_cdf(-d2) - fwd * norm_cdf(-d1))
