"""Trajectoires du mouvement brownien géométrique sur les dates d'observation.

Modèle de Black-Scholes avec dividende continu (cours PricingMonteCarlo_2026, slide 42) :
    dS(t)/S(t) = (r − q)dt + σ dW^Q(t).
Schéma exact du MBG (slide 35, et S_i(T) du slide 43) sur les seules dates d'observation :
    S_{k+1} = S_k · exp((r − q − σ²/2)Δt_k + σ√Δt_k · Z_k),   Δt_k = t_{k+1} − t_k.
Le schéma est exact en loi : une grille plus fine que les dates d'observation n'apporte rien en
Black-Scholes. Il est calculé sous la forme S_k = S0·exp(Σ_{j≤k} x_j) (somme cumulée des
incréments de ln S), algébriquement identique à la récurrence multiplicative (testé).

Dates d'observation (payoff asiatique du slide 39, t_k ∈ [0, T]) : t_k = k·T/n, k = 1..n ;
S0 (t_0 = 0) est exclu par défaut et ajouté en première colonne si include_s0=True.

Aléa : un seul LCG (pricer.rng) pour tout le calcul, transformé en normales par
pricer.normals. Les normales sont consommées dans l'ordre « trajectoire par trajectoire » :
la trajectoire i, date k, utilise Z[i·n + k]. La simulation se fait par blocs de batch_size
trajectoires (mémoire indépendante de N) et la suite des trajectoires ne dépend pas de
batch_size (testé), y compris pour les méthodes qui produisent les normales par paires.
"""
from __future__ import annotations

import math
import numbers
from typing import Iterator

import numpy as np

from pricer.normals import METHODS, normals
from pricer.rng import LCG

FREQUENCIES = {"daily": 252, "weekly": 52, "monthly": 12, "quarterly": 4}
DEFAULT_BATCH = 50_000
_PAIR_METHODS = ("box_muller", "polar")   # produisent les normales deux par deux


def _check_maturity(T) -> float:
    T = float(T)
    if not math.isfinite(T) or T <= 0.0:
        raise ValueError(f"T doit être un réel fini > 0, reçu {T!r}")
    return T


def _check_posint(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, numbers.Integral):
        raise TypeError(f"{name} doit être un entier, reçu {value!r}")
    if value < 1:
        raise ValueError(f"{name} doit être ≥ 1, reçu {value!r}")
    return int(value)


def n_obs_from(obs, T) -> int:
    """Nombre d'observations : entier n ≥ 1, ou fréquence annuelle f → arrondi de f·T.

    Arrondi classique, demi vers le haut : ⌊f·T + 1/2⌋ (pas le round() de Python, qui arrondit
    au pair : 0,5 → 0 et 2,5 → 2), avec un minimum de 1 observation. Seul T ≤ 0 est une erreur
    (décision du 17/11/2026, CLAUDE.md).
    """
    if isinstance(obs, str):
        if obs not in FREQUENCIES:
            raise ValueError(f"fréquence inconnue {obs!r} ; choix : {sorted(FREQUENCIES)}")
        return max(1, math.floor(FREQUENCIES[obs] * _check_maturity(T) + 0.5))
    return _check_posint(obs, "n_obs")


def obs_dates(T, n_obs, include_s0: bool = False) -> np.ndarray:
    """t_k = k·T/n, k = 1..n (t_n = T exactement) ; 0 en tête si include_s0."""
    T = _check_maturity(T)
    n = n_obs_from(n_obs, T)
    t = T * np.arange(1, n + 1, dtype=np.float64) / n
    t[-1] = T
    return np.concatenate(([0.0], t)) if include_s0 else t


class NormalStream:
    """Flux unique de normales N(0, 1) tirées d'un seul LCG, servies à la demande.

    take(n) renvoie les n normales suivantes du flux. Les méthodes par paires (Box-Muller,
    polaire) tirent toujours un nombre pair de normales et gardent le reste en réserve :
    aucune normale n'est jetée, donc la concaténation des take(...) est exactement
    normals(total, method, seed).z, quel que soit le découpage (testé).
    """

    def __init__(self, seed, method: str = "inverse"):
        if method not in METHODS:
            raise ValueError(f"rng_method inconnue {method!r} ; choix : {METHODS}")
        if seed is None:
            raise ValueError("seed obligatoire (aucun aléa implicite)")
        self.seed = seed
        self.method = method
        self.lcg = LCG(seed)
        self._buf = np.empty(0)
        self.n_normals = 0          # normales servies

    @property
    def n_uniforms(self) -> int:
        return self.lcg.count

    def take(self, n: int) -> np.ndarray:
        n = int(n)
        if n <= self._buf.size:
            out, self._buf = self._buf[:n], self._buf[n:]
        else:
            need = n - self._buf.size
            if self.method in _PAIR_METHODS and need % 2:
                need += 1
            z = normals(need, self.method, lcg=self.lcg).z
            full = np.concatenate((self._buf, z))
            out, self._buf = full[:n], full[n:]
        self.n_normals += n
        return out


def _check_model(S0, sigma, r, q) -> tuple[float, float, float, float]:
    S0, sigma, r, q = float(S0), float(sigma), float(r), float(q)
    if not (math.isfinite(S0) and S0 > 0.0):
        raise ValueError(f"S0 doit être > 0, reçu {S0!r}")
    if not (math.isfinite(sigma) and sigma >= 0.0):
        raise ValueError(f"sigma doit être ≥ 0, reçu {sigma!r}")
    if not (math.isfinite(r) and math.isfinite(q)):
        raise ValueError("r et q doivent être finis")
    return S0, sigma, r, q


def gbm_paths(S0, sigma, r, T, q=0.0, obs="monthly", n_paths: int = 100_000,
              seed=20261117, rng_method: str = "inverse", batch_size: int = DEFAULT_BATCH,
              include_s0: bool = False, stream: NormalStream | None = None
              ) -> Iterator[np.ndarray]:
    """Blocs de trajectoires (tableaux (b, n_obs), ou (b, n_obs + 1) avec S0), b ≤ batch_size.

    Les paramètres sont validés à l'appel ; le générateur renvoyé simule bloc par bloc.
    ``stream`` permet de fournir un flux existant (le pricer s'en sert pour compter les
    normales et uniformes consommées) ; sinon un flux neuf est créé à partir de seed.
    """
    S0, sigma, r, q = _check_model(S0, sigma, r, q)
    T = _check_maturity(T)
    n_paths = _check_posint(n_paths, "n_paths")
    batch_size = _check_posint(batch_size, "batch_size")
    t = obs_dates(T, obs)
    if stream is None:
        stream = NormalStream(seed, rng_method)

    dt = np.diff(np.concatenate(([0.0], t)))
    drift = (r - q - 0.5 * sigma * sigma) * dt
    vol = sigma * np.sqrt(dt)
    n = t.size

    def _blocks() -> Iterator[np.ndarray]:
        done = 0
        while done < n_paths:
            b = min(batch_size, n_paths - done)
            z = stream.take(b * n).reshape(b, n)
            S = S0 * np.exp(np.cumsum(drift + vol * z, axis=1))
            if include_s0:
                S = np.concatenate((np.full((b, 1), S0), S), axis=1)
            done += b
            yield S

    return _blocks()
