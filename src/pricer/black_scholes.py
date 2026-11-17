"""Formule fermée de Black-Scholes avec dividende continu q (cours PricingMonteCarlo_2026,
slides 43-44) :

    C = S0 e^{−qT} Φ(d1) − K e^{−rT} Φ(d2),     P = K e^{−rT} Φ(−d2) − S0 e^{−qT} Φ(−d1),
    d1 = [ln(S0/K) + (r − q + σ²/2)T] / (σ√T),  d2 = d1 − σ√T,
    parité : C − P = S0 e^{−qT} − K e^{−rT}.

Φ est codée sans SciPy : Φ(x) = ½ erfc(−x/√2) (math.erfc de la bibliothèque standard).
Cas σ√T = 0 (hors cours) : limite déterministe, max(±(S0 e^{−qT} − K e^{−rT}), 0).
"""
from __future__ import annotations

import math

import numpy as np

OPTIONS = ("call", "put")
_SQRT2 = math.sqrt(2.0)
_erfc_vec = np.frompyfunc(math.erfc, 1, 1)


def norm_cdf(x):
    """Φ(x) = P(X ≤ x), X ~ N(0, 1) ; scalaire → float, tableau → tableau float64."""
    if np.ndim(x) == 0:
        return 0.5 * math.erfc(-float(x) / _SQRT2)
    return 0.5 * _erfc_vec(-np.asarray(x, dtype=np.float64) / _SQRT2).astype(np.float64)


def _check(S0, K, sigma, r, T, q, option):
    vals = dict(S0=S0, K=K, sigma=sigma, r=r, T=T, q=q)
    vals = {k: float(v) for k, v in vals.items()}
    if not all(math.isfinite(v) for v in vals.values()):
        raise ValueError(f"paramètres non finis : {vals}")
    if vals["S0"] <= 0 or vals["K"] <= 0:
        raise ValueError("S0 et K doivent être > 0")
    if vals["sigma"] < 0:
        raise ValueError("sigma doit être ≥ 0")
    if vals["T"] <= 0:
        raise ValueError("T doit être > 0")
    if option not in OPTIONS:
        raise ValueError(f"option inconnue {option!r} ; choix : {OPTIONS}")
    return vals


def bs_price(S0, K, sigma, r, T, q=0.0, option: str = "call") -> float:
    """Prix Black-Scholes d'un call ou d'un put européen sur actif à dividende continu q."""
    v = _check(S0, K, sigma, r, T, q, option)
    S0, K, sigma, r, T, q = v["S0"], v["K"], v["sigma"], v["r"], v["T"], v["q"]
    fwd_s = S0 * math.exp(-q * T)        # S0 e^{−qT}
    disc_k = K * math.exp(-r * T)        # K e^{−rT}
    vol = sigma * math.sqrt(T)
    if vol == 0.0:
        intrinsic = fwd_s - disc_k
        return max(intrinsic, 0.0) if option == "call" else max(-intrinsic, 0.0)
    d1 = (math.log(S0 / K) + (r - q + 0.5 * sigma * sigma) * T) / vol
    d2 = d1 - vol
    if option == "call":
        return fwd_s * norm_cdf(d1) - disc_k * norm_cdf(d2)
    return disc_k * norm_cdf(-d2) - fwd_s * norm_cdf(-d1)
