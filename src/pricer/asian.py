"""Pricer Monte-Carlo : option asiatique à moyenne arithmétique et option européenne.

Payoffs (cours PricingMonteCarlo_2026, slides 38-39) :
    asiatique  call max(A − K, 0), put max(K − A, 0),  A = (1/n) Σ_k S(t_k)
    européen   call max(S_T − K, 0), put max(K − S_T, 0)
Prix = moyenne des payoffs actualisés e^{−rT}·payoff (slides 43-44).

Estimateur et intervalle de confiance (slides 48-49, annexe slides 64-65) :
    prix = (1/N) Σ h_i,  s² = 1/(N − 1) Σ (h_i − prix)²,  écart-type de l'estimateur s/√N,
    IC 95 % = [prix − 1,96·s/√N ; prix + 1,96·s/√N]  (IC symétrique, α1 = α2 = 2,5 %).
Moyenne et variance accumulées bloc par bloc (fusion de Chan, Golub et LeVeque 1979, hors
cours : variante par blocs de l'algorithme de Welford) : la mémoire ne dépend pas de N.
"""
from __future__ import annotations

import math
import numbers
import time
from dataclasses import asdict, dataclass

import numpy as np

from pricer.black_scholes import OPTIONS
from pricer.paths import DEFAULT_BATCH, NormalStream, gbm_paths, n_obs_from

Z_95 = 1.96
REFERENCE_SEED = 20261117
AVERAGES = ("arithmetic", "geometric")


@dataclass(frozen=True)
class MCResult:
    price: float            # estimateur Monte-Carlo du prix
    std_error: float        # écart-type de l'estimateur, s/√N
    ci_low: float           # IC 95 % : prix − 1,96·s/√N
    ci_high: float          # IC 95 % : prix + 1,96·s/√N
    n_paths: int
    seed: int
    rng_method: str
    n_obs: int              # dates simulées (S0 non compté)
    elapsed: float          # temps de calcul, secondes
    option: str             # "call" / "put"
    kind: str               # "asian" / "european"
    include_s0: bool
    n_uniforms: int         # uniformes consommées dans le LCG
    z: float = Z_95
    average: str | None = None   # asiatique : "arithmetic" / "geometric" ; européen : None

    def as_dict(self) -> dict:
        return asdict(self)


class _Moments:
    """Moyenne et somme des carrés des écarts, fusionnées bloc par bloc."""

    def __init__(self):
        self.n, self.mean, self.m2 = 0, 0.0, 0.0

    def add(self, x: np.ndarray) -> None:
        nb = x.size
        if nb == 0:
            return
        mb = float(x.mean())
        m2b = float(np.square(x - mb).sum())
        n = self.n + nb
        delta = mb - self.mean
        self.mean += delta * nb / n
        self.m2 += m2b + delta * delta * self.n * nb / n
        self.n = n

    @property
    def variance(self) -> float:      # s² en 1/(N − 1), slide 49
        return self.m2 / (self.n - 1)


def _price(kind, S0, K, sigma, r, T, q, option, obs, n_paths, seed, rng_method, batch_size,
           include_s0, control, average=None) -> MCResult:
    if control is not None:
        raise NotImplementedError("control (variable de contrôle) est réservé à P3 : seul None "
                                  "est accepté pour l'instant")
    if option not in OPTIONS:
        raise ValueError(f"option inconnue {option!r} ; choix : {OPTIONS}")
    if kind == "asian" and average not in AVERAGES:
        raise ValueError(f"average inconnue {average!r} ; choix : {AVERAGES}")
    K = float(K)
    if not (math.isfinite(K) and K > 0.0):
        raise ValueError(f"K doit être > 0, reçu {K!r}")
    if isinstance(n_paths, bool) or not isinstance(n_paths, numbers.Integral):
        raise TypeError(f"n_paths doit être un entier, reçu {n_paths!r}")
    if n_paths < 2:
        raise ValueError("n_paths doit être ≥ 2 (variance empirique en 1/(N − 1))")

    start = time.perf_counter()
    stream = NormalStream(seed, rng_method)
    n_obs = n_obs_from(obs, T)
    disc = math.exp(-float(r) * float(T))
    acc = _Moments()
    for S in gbm_paths(S0, sigma, r, T, q, obs=obs, n_paths=n_paths, batch_size=batch_size,
                       include_s0=include_s0, stream=stream):
        if kind == "european":
            x = S[:, -1]
        elif average == "arithmetic":
            x = S.mean(axis=1)                       # A = (1/n) Σ S(t_k)
        else:
            x = np.exp(np.log(S).mean(axis=1))       # G = (Π S(t_k))^{1/n}
        payoff = np.maximum(x - K, 0.0) if option == "call" else np.maximum(K - x, 0.0)
        acc.add(disc * payoff)
    se = math.sqrt(acc.variance / acc.n)
    elapsed = time.perf_counter() - start
    return MCResult(price=acc.mean, std_error=se, ci_low=acc.mean - Z_95 * se,
                    ci_high=acc.mean + Z_95 * se, n_paths=int(n_paths), seed=seed,
                    rng_method=rng_method, n_obs=n_obs, elapsed=elapsed, option=option,
                    kind=kind, include_s0=bool(include_s0), n_uniforms=stream.n_uniforms,
                    average=average)


def price_asian(S0, K, sigma, r, T, q=0.0, option="call", obs="monthly", n_paths=100_000,
                seed=REFERENCE_SEED, rng_method="inverse", batch_size=DEFAULT_BATCH,
                include_s0=False, control=None, average="arithmetic") -> MCResult:
    """Call ou put asiatique à moyenne arithmétique par Monte-Carlo.

    Paramètres généraux : S0, K, sigma, r, T, q (dividende continu), option.
    Spécifiques asiatiques : obs = nombre de dates d'observation (entier) ou fréquence
    "daily" / "weekly" / "monthly" / "quarterly" ; include_s0 = S0 compté dans la moyenne ;
    average = "arithmetic" (énoncé) ou "geometric" (payoff sur G simulé, pour valider la
    formule fermée de pricer.geometric).
    Simulation : n_paths, seed, rng_method (méthode de pricer.normals), batch_size.
    control : réservé à P3 (variable de contrôle géométrique), seul None accepté.
    """
    return _price("asian", S0, K, sigma, r, T, q, option, obs, n_paths, seed, rng_method,
                  batch_size, include_s0, control, average)


def price_european_mc(S0, K, sigma, r, T, q=0.0, option="call", obs="monthly",
                      n_paths=100_000, seed=REFERENCE_SEED, rng_method="inverse",
                      batch_size=DEFAULT_BATCH, include_s0=False, control=None) -> MCResult:
    """Call ou put européen par Monte-Carlo, mêmes paramètres que price_asian.

    Payoff sur S_T = dernière date d'observation (t_n = T). Avec les mêmes obs et seed que
    price_asian, les deux prix sont calculés sur les mêmes trajectoires ; avec obs=1, S_T est
    simulé en un pas, exactement comme au slide 43. Le schéma étant exact, la loi de S_T ne
    dépend pas de obs.
    """
    return _price("european", S0, K, sigma, r, T, q, option, obs, n_paths, seed, rng_method,
                  batch_size, include_s0, control)
