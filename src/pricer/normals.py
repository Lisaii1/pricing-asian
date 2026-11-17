"""Génération de variables normales N(0, 1) à partir du LCG du cours.

Point d'entrée unique : ``normals(n, method, seed, **opts)``.

Méthodes (cours PricingMonteCarlo_2026, A. W. Sanoussi Mani, S1 2026) :
  "inverse"              transformée inverse X = Φ^{-1}(U) (slides 13-14).
                         Φ^{-1} : Wichura AS241 / PPND16 double précision (polycopié Haqueberge
                         2018 p. 11 et annexe pp. 22-23), ou Hastings (slide 24) si
                         precision="hastings".
  "box_muller"           slide 22 : R = −2 log U1, V = 2π U2, Z1 = √R cos V, Z2 = √R sin V.
  "polar"                Marsaglia-Bray, slide 23, avec V = 2U − 1 (le slide imprime « −2U − 1 »,
                         coquille : V serait dans ]−3, −1[ et X = V1² + V2² > 1 toujours, la
                         boucle ne terminerait jamais).
  "acceptance_rejection" méthode d'acceptation-rejet des slides 17-18. Le cours ne donne pas
                         d'exemple pour la loi normale : HORS COURS, demi-normale
                         f(x) = √(2/π) e^{−x²/2} (x ≥ 0) proposée par une exponentielle
                         g(x) = e^{−x} tirée par transformée inverse X = −log(1 − U) (slide 14),
                         c = sup f/g = √(2e/π), test U ≤ f(X)/(c g(X)) = exp(−(X − 1)²/2),
                         puis signe aléatoire. Taux d'acceptation théorique 1/c ≈ 0,7602.

Consommation d'uniformes (toutes les méthodes tirent dans le même LCG) :
  inverse 1 par normale ; box_muller 2 par paire ; polar 2 par candidat ;
  acceptance_rejection 3 par candidat (U1 → X, U2 → test, U3 → signe).
Les méthodes à rejet sont vectorisées par blocs de candidats ; les candidats tirés au-delà
du dernier utilisé sont rendus au générateur (état replacé), si bien que la suite produite et
l'état final du LCG sont exactement ceux de la boucle scalaire du cours (testé).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from pricer.rng import LCG

METHODS = ("inverse", "box_muller", "polar", "acceptance_rejection")
PRECISIONS = ("as241", "hastings")

# --- Φ^{-1} : Wichura (1988), algorithme AS241, fonction PPND16 ---------------------------
# Coefficients publiés (Applied Statistics 37(3), 477-484), à 20 chiffres. Le polycopié
# (annexe VBA) les imprime arrondis à 15 chiffres ; tests/test_normals.py vérifie l'accord.
# Les indices suivent le VBA du cours : b[0] = d[0] = f[0] = 0 (le terme constant du
# dénominateur vaut 1).
AS241 = {
    "a": (3.3871328727963666080e0, 1.3314166789178437745e2, 1.9715909503065514427e3,
          1.3731693765509461125e4, 4.5921953931549871457e4, 6.7265770927008700853e4,
          3.3430575583588128105e4, 2.5090809287301226727e3),
    "b": (0.0, 4.2313330701600911252e1, 6.8718700749205790830e2, 5.3941960214247511077e3,
          2.1213794301586595867e4, 3.9307895800092710610e4, 2.8729085735721942674e4,
          5.2264952788528545610e3),
    "c": (1.42343711074968357734e0, 4.63033784615654529590e0, 5.76949722146069140550e0,
          3.64784832476320460504e0, 1.27045825245236838258e0, 2.41780725177450611770e-1,
          2.27238449892691845833e-2, 7.74545014278341407640e-4),
    "d": (0.0, 2.05319162663775882187e0, 1.67638483018380384940e0, 6.89767334985100004550e-1,
          1.48103976427480074590e-1, 1.51986665636164571966e-2, 5.47593808499534494600e-4,
          1.05075007164441684324e-9),
    "e": (6.65790464350110377720e0, 5.46378491116411436990e0, 1.78482653991729133580e0,
          2.96560571828504891230e-1, 2.65321895265761230930e-2, 1.24266094738807843860e-3,
          2.71155556874348757815e-5, 2.01033439929228813265e-7),
    "f": (0.0, 5.99832206555887937690e-1, 1.36929880922735805310e-1, 1.48753612908506148525e-2,
          7.86869131145613259100e-4, 1.84631831751005468180e-5, 1.42151175831644588870e-7,
          2.04426310338993978564e-15),
}
_SPLIT1, _SPLIT2, _CONST1, _CONST2 = 0.425, 5.0, 0.180625, 1.6


def _horner(coefs, r):
    """coefs[0] + coefs[1] r + … + coefs[7] r^7, même ordre d'évaluation que le VBA du cours."""
    out = np.full_like(r, coefs[-1])
    for ck in reversed(coefs[:-1]):
        out = out * r + ck
    return out


def _den(coefs, r):
    """1 + coefs[1] r + … + coefs[7] r^7 (coefs[0] = 0 sert de bouche-trou, comme dans le VBA)."""
    return _horner((1.0,) + tuple(coefs[1:]), r)


def _check_open_unit(u) -> np.ndarray:
    u = np.asarray(u, dtype=np.float64)
    bad = ~((u > 0.0) & (u < 1.0))  # attrape aussi NaN
    if bad.any():
        raise ValueError(f"Φ^{{-1}}(u) exige u ∈ ]0, 1[ ; {int(bad.sum())} valeur(s) hors domaine "
                         f"(ex. {u[bad].ravel()[0]!r})")
    return u


def ppnd16(u) -> np.ndarray:
    """Φ^{-1}(u) par l'algorithme AS241 (PPND16) de Wichura, vectorisé.

    Écart au VBA du cours : pour u hors de ]0, 1[ le VBA renvoie 0 ; ici on lève ValueError.
    """
    u = _check_open_unit(u)
    q = u - 0.5
    z = np.empty_like(u)

    central = np.abs(q) <= _SPLIT1
    if central.any():
        qc = q[central]
        r = _CONST1 - qc * qc
        z[central] = qc * _horner(AS241["a"], r) / _den(AS241["b"], r)

    tail = ~central
    if tail.any():
        qt = q[tail]
        r = np.where(qt < 0.0, u[tail], 1.0 - u[tail])
        r = np.sqrt(-np.log(r))
        zt = np.empty_like(r)
        near = r <= _SPLIT2
        rn = r[near] - _CONST2
        zt[near] = _horner(AS241["c"], rn) / _den(AS241["d"], rn)
        rf = r[~near] - _SPLIT2
        zt[~near] = _horner(AS241["e"], rf) / _den(AS241["f"], rf)
        z[tail] = np.where(qt < 0.0, -zt, zt)
    return z


# --- Φ^{-1} : Hastings (1955), slide 24 ------------------------------------------------
# g(u) = signe(u − 1/2) · ( t − (c0 + c1 t + c2 t²) / (1 + d1 t + d2 t² + d3 t³) ),
# t = √(−2 log min(u, 1 − u)).
# Écarts au slide : (i) le dénominateur imprimé « d1 + d2 t² + d3 t³ » est une coquille, la
# bonne forme est 1 + d1 t + d2 t² + d3 t³ (Abramowitz & Stegun 26.2.23) ; (ii) le texte
# extrait du PDF lit « t = −log(min(U, 1 − U)) » : on suit A&S 26.2.23, t = √(−2 ln p), seule
# forme qui donne la précision 0,45e-3 annoncée par le cours (mesurée dans les tests).
HASTINGS_C = (2.515517, 0.802853, 0.010328)
HASTINGS_D = (1.432788, 0.189269, 0.001308)


def hastings(u) -> np.ndarray:
    u = _check_open_unit(u)
    p = np.minimum(u, 1.0 - u)
    t = np.sqrt(-2.0 * np.log(p))
    c0, c1, c2 = HASTINGS_C
    d1, d2, d3 = HASTINGS_D
    x = t - (c0 + t * (c1 + t * c2)) / (1.0 + t * (d1 + t * (d2 + t * d3)))
    return np.sign(u - 0.5) * x


# --- échantillon renvoyé -------------------------------------------------------------------

@dataclass(frozen=True)
class NormalSample:
    z: np.ndarray                       # les n normales
    method: str
    n_uniforms: int                     # uniformes consommées dans le LCG
    seed: int | None                    # seed du LCG (None si un LCG existant a été fourni)
    precision: str | None = None        # "as241" / "hastings" pour la méthode inverse
    acceptance_rate: float | None = None  # méthodes à rejet : acceptés / candidats
    n_candidates: int | None = None
    lcg_params: dict = field(default_factory=dict)


# --- méthodes ---------------------------------------------------------------------------

_MAX_EMPTY_BLOCKS = 1000


def _no_zero(u: np.ndarray, where: str) -> None:
    if (u == 0.0).any():
        raise ValueError(f"u = 0 rencontré ({where}) : possible seulement avec un LCG mixte "
                         "(x = 0) ; log(0) / Φ^{-1}(0) indéfinis")


def _rejection(lcg: LCG, n_out: int, per_cand: int, out_per_acc: int, p_acc: float,
               accept, values):
    """Boucle d'acceptation-rejet vectorisée par blocs, exacte vis-à-vis de la boucle scalaire.

    accept(U) -> masque des candidats acceptés (U de forme (k, per_cand)) ;
    values(U_acc) -> tableau (k_acc, out_per_acc) des sorties des candidats acceptés.
    """
    need = math.ceil(n_out / out_per_acc)
    chunks, n_cand, n_acc, empty = [], 0, 0, 0
    while n_acc < need:
        remaining = need - n_acc
        k = int(remaining / p_acc * 1.05) + 32
        ints = lcg.integers(per_cand * k)
        U = (ints / float(lcg.m)).reshape(k, per_cand)
        idx = np.flatnonzero(accept(U))
        used = k
        if idx.size >= remaining:
            idx = idx[:remaining]
            used = int(idx[-1]) + 1
            unused = per_cand * (k - used)
            if unused:  # rendre au LCG les candidats non examinés
                state = lcg.get_state()
                state["x"] = int(ints[per_cand * used - 1])
                lcg.set_state(state)
                lcg.count -= unused
        if idx.size:
            chunks.append(values(U[idx]))
            empty = 0
        else:
            empty += 1
            if empty >= _MAX_EMPTY_BLOCKS:
                raise RuntimeError("aucun candidat accepté sur 1000 blocs : algorithme incorrect ?")
        n_cand += used
        n_acc += idx.size
    z = np.concatenate(chunks).ravel()[:n_out] if chunks else np.empty(0)
    rate = n_acc / n_cand if n_cand else None
    return z, n_cand, rate


def _polar_accept(U):
    v = 2.0 * U - 1.0
    s = v[:, 0] * v[:, 0] + v[:, 1] * v[:, 1]
    return (s > 0.0) & (s < 1.0)


def _polar_values(U):
    v = 2.0 * U - 1.0
    s = v[:, 0] * v[:, 0] + v[:, 1] * v[:, 1]
    y = np.sqrt(-2.0 * np.log(s) / s)
    return v * y[:, None]               # colonnes (Z1, Z2)


def _ar_accept(U):
    x = -np.log(1.0 - U[:, 0])
    return U[:, 1] <= np.exp(-0.5 * (x - 1.0) ** 2)


def _ar_values(U):
    x = -np.log(1.0 - U[:, 0])
    return np.where(U[:, 2] <= 0.5, x, -x)[:, None]


C_AR = math.sqrt(2.0 * math.e / math.pi)


def normals(n: int, method: str, seed: int | None = None, **opts) -> NormalSample:
    """n variables N(0, 1) par la méthode ``method`` à partir d'un LCG du cours.

    Paramètres
    ----------
    n       : nombre de normales.
    method  : "inverse", "box_muller", "polar" ou "acceptance_rejection".
    seed    : seed du LCG (entier ; 0 interdit pour un LCG pur). Obligatoire sauf si ``lcg``.
    opts    : precision = "as241" (défaut) | "hastings" (méthode inverse seulement) ;
              a, m, c   = paramètres du LCG (défaut Park-Miller) ;
              lcg       = LCG existant dont on poursuit le flux (exclusif avec seed, a, m, c).
    """
    if method not in METHODS:
        raise ValueError(f"method inconnue {method!r} ; choix : {METHODS}")
    precision = opts.pop("precision", "as241")
    if precision not in PRECISIONS:
        raise ValueError(f"precision inconnue {precision!r} ; choix : {PRECISIONS}")
    lcg = opts.pop("lcg", None)
    lcg_kwargs = {k: opts.pop(k) for k in ("a", "m", "c") if k in opts}
    if opts:
        raise TypeError(f"options inconnues : {sorted(opts)}")
    if lcg is not None:
        if seed is not None or lcg_kwargs:
            raise ValueError("fournir soit seed (et a, m, c), soit lcg, pas les deux")
    else:
        if seed is None:
            raise ValueError("seed obligatoire (aucun aléa implicite)")
        lcg = LCG(seed, **lcg_kwargs)
    if isinstance(n, bool) or not isinstance(n, (int, np.integer)) or n < 0:
        raise ValueError(f"n doit être un entier ≥ 0, reçu {n!r}")
    n = int(n)

    count0 = lcg.count
    rate = cand = None
    if method == "inverse":
        u = lcg.uniforms(n)
        _no_zero(u, "inverse")
        z = ppnd16(u) if precision == "as241" else hastings(u)
    elif method == "box_muller":
        k = math.ceil(n / 2)
        u = lcg.uniforms(2 * k)
        u1, u2 = u[0::2], u[1::2]
        _no_zero(u1, "box_muller, U1")
        r = -2.0 * np.log(u1)
        v = 2.0 * np.pi * u2
        z = np.empty(2 * k)
        z[0::2] = np.sqrt(r) * np.cos(v)
        z[1::2] = np.sqrt(r) * np.sin(v)
        z = z[:n]
    elif method == "polar":
        z, cand, rate = _rejection(lcg, n, 2, 2, math.pi / 4, _polar_accept, _polar_values)
    else:
        z, cand, rate = _rejection(lcg, n, 3, 1, 1.0 / C_AR, _ar_accept, _ar_values)

    return NormalSample(
        z=np.ascontiguousarray(z, dtype=np.float64),
        method=method,
        n_uniforms=lcg.count - count0,
        seed=seed,
        precision=precision if method == "inverse" else None,
        acceptance_rate=rate,
        n_candidates=cand,
        lcg_params={"a": lcg.a, "m": lcg.m, "c": lcg.c},
    )
