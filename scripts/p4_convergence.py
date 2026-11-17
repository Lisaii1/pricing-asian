"""Convergence, nombre de simulations nécessaire, comparaison à temps égal (P4, étape 2).

Actif théorique (CLAUDE.md) : S0 = 100, σ = 0,20, r = 0,03, q = 0,01, observations mensuelles ;
call asiatique arithmétique K = 100, T = 1. Normales par transformée inverse (AS241), seed
20261117. Quatre estimateurs :
    plain               sans réduction de variance
    antithetic          trajectoires jumelées (Z, −Z), N = nombre total de trajectoires (pair)
    control             contrôle géométrique, b optimal estimé sur l'échantillon (slide 50)
    antithetic_control  les deux (contrôle sur les moyennes de paires)

1. Convergence (results/p4_convergence.csv) : N sur une grille log de 10^3 à 10^6, 13 points
   (pas 10^0,25, arrondis au pair), même seed pour tous les N : chaque échantillon prolonge le
   précédent (une seule « trajectoire de convergence » par estimateur). Prix, demi-largeur de l'IC
   à 95 % z·s/√N (z = Φ^{-1}(0,975) par AS241), temps d'un run. Référence pour tracer : contrôle à
   N = 4 000 000 sur le flux du LCG qui suit les 12·10^6 uniformes de la grille (seed = état du LCG
   après ces tirages, voir p4_cours.seed_after) : indépendante de tous les points.
   Pentes (results/p4_convergence_slopes.csv) : moindres carrés de log(demi-largeur) contre log(N)
   sur les 13 points ; attendu −0,5 (slide 49 : écart-type s/√N).
2. N nécessaire (results/p4_n_required.csv) : marge ε ∈ {0,01 ; 0,001} à 95 %,
   N = ⌈(z·σ̂/ε)²⌉ (arrondi au pair supérieur pour les antithétiques), σ̂ = écart-type par
   trajectoire mesuré à N = 10^5 : σ̂ = se(10^5)·√(10^5). Pour les antithétiques N compte les
   trajectoires, σ̂ est donc l'écart-type « par trajectoire » équivalent (s_paires/√2). Temps
   estimé = N × temps par trajectoire (médiane de 3 runs à N = 10^5). Question 2 du DS 2024-2025.
3. Temps égal (results/p4_equal_time.csv) : budgets 0,5 s, 2 s, 8 s ; pour chaque estimateur, le
   plus grand N dont le temps mesuré tient dans le budget (recherche itérative : N suivant =
   0,98·N·budget/temps), puis sa demi-largeur à 95 %. Les essais sont écrits (colonne trials).

Les temps dépendent de la machine et de sa charge (mesurés avec time.perf_counter dans le pricer).
Valeurs écrites en pleine précision (arrondi à 10^-4 dans le rapport).
Usage : .venv/Scripts/python.exe scripts/p4_convergence.py
"""
from __future__ import annotations

import csv
import math
import statistics
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from p4_cours import seed_after  # noqa: E402
from pricer.asian import price_asian  # noqa: E402

PARAMS = dict(S0=100.0, sigma=0.20, r=0.03, q=0.01)
K, T, OPTION, OBS = 100.0, 1.0, "call", "monthly"
SEED = 20261117
RNG = "inverse"
CONFIDENCE = 0.95
N_GRID = (1_000, 1_000_000, 13)
N_SIGMA = 100_000
N_TIMING_RUNS = 3
N_REF = 4_000_000
EPSILONS = (0.01, 0.001)
BUDGETS = (0.5, 2.0, 8.0)
EXPECTED_SLOPE = -0.5

ESTIMATORS = {
    "plain": {},
    "antithetic": dict(antithetic=True),
    "control": dict(control="geometric"),
    "antithetic_control": dict(antithetic=True, control="geometric"),
}
PAIRED = ("antithetic", "antithetic_control")

OUT_CONV = ROOT / "results" / "p4_convergence.csv"
OUT_SLOPES = ROOT / "results" / "p4_convergence_slopes.csv"
OUT_NREQ = ROOT / "results" / "p4_n_required.csv"
OUT_TIME = ROOT / "results" / "p4_equal_time.csv"

COMMON = ["S0", "K", "sigma", "r", "q", "T", "option", "obs", "n_obs", "seed", "rng_method"]
FIELDS_CONV = ["estimator", "n_paths", *COMMON, "confidence", "z", "price", "std_error",
               "half_width_95", "ci_low", "ci_high", "beta", "corr", "antithetic_corr",
               "n_uniforms", "time_s", "ref_price", "ref_std_error", "ref_n_paths", "ref_seed",
               "price_minus_ref_in_se"]
FIELDS_SLOPES = ["estimator", "n_points", "n_min", "n_max", "slope", "slope_std_error",
                 "intercept", "expected_slope", "slope_minus_expected"]
FIELDS_NREQ = ["estimator", "epsilon", "confidence", "z", *COMMON, "sigma_hat_n_paths",
               "std_error_at_n", "sigma_hat", "n_required", "time_per_path_s", "time_runs_s",
               "time_estimated_s"]
FIELDS_TIME = ["estimator", "budget_s", "n_paths", "time_s", *COMMON, "price", "std_error",
               "half_width_95", "n_trials", "trials"]


# --- fonctions d'analyse (testées dans tests/test_p4_convergence.py) ------------------------------

def log_grid(lo: int, hi: int, k: int) -> list[int]:
    """k entiers pairs répartis géométriquement de lo à hi (bornes comprises)."""
    x = lo * (hi / lo) ** (np.arange(k) / (k - 1))
    return [int(2 * round(v / 2)) for v in x]


def loglog_slope(n, y) -> tuple[float, float]:
    """(pente, ordonnée) de la droite des moindres carrés de log(y) contre log(n)."""
    slope, intercept = np.polyfit(np.log(np.asarray(n, float)), np.log(np.asarray(y, float)), 1)
    return float(slope), float(intercept)


def _slope_std_error(n, y, slope, intercept) -> float:
    x, v = np.log(np.asarray(n, float)), np.log(np.asarray(y, float))
    resid = v - (slope * x + intercept)
    return float(math.sqrt(resid @ resid / (x.size - 2) / ((x - x.mean()) @ (x - x.mean()))))


def n_required(sigma_hat: float, epsilon: float, z: float) -> int:
    """N = ⌈(z·σ̂/ε)²⌉ ; le facteur (1 − 1e−12) absorbe l'arrondi flottant d'un carré exact."""
    return math.ceil((z * sigma_hat / epsilon) ** 2 * (1.0 - 1e-12))


def _even(n: float) -> int:
    return max(2, int(n) - int(n) % 2)


def largest_n_within_budget(run, budget: float, n_start: float, even: bool = False,
                            max_iter: int = 8) -> dict:
    """Plus grand N mesuré dont le temps tient dans le budget.

    run(n) -> (résultat, temps en s). N suivant = 0,98·N·budget/temps ; arrêt quand un N tient
    dans le budget et que le suivant ne le dépasse pas de plus de 1 %.
    """
    best, trials = None, []
    n = _even(n_start) if even else max(2, int(n_start))
    for _ in range(max_iter):
        res, elapsed = run(n)
        trials.append((n, elapsed))
        fits = elapsed <= budget
        if fits and (best is None or n > best["n_paths"]):
            best = dict(n_paths=n, time_s=elapsed, result=res)
        nxt = 0.98 * n * budget / elapsed
        nxt = _even(nxt) if even else max(2, int(nxt))
        if fits and nxt <= 1.01 * n:
            break
        n = nxt
    if best is None:
        raise RuntimeError(f"aucun N ne tient dans {budget} s : essais {trials}")
    best["trials"] = trials
    return best


# --- simulation -----------------------------------------------------------------------------------

def _price(n, extra):
    return price_asian(**PARAMS, K=K, T=T, option=OPTION, obs=OBS, n_paths=n, seed=SEED,
                       rng_method=RNG, confidence=CONFIDENCE, **extra)


def reference(confidence=CONFIDENCE):
    """Contrôle à N = 4 000 000 sur le flux qui suit les uniformes de la grille (actif théorique)."""
    n_obs = 12
    ref_seed = seed_after(SEED, N_GRID[1] * n_obs)
    return price_asian(**PARAMS, K=K, T=T, option=OPTION, obs=OBS, n_paths=N_REF, seed=ref_seed,
                       rng_method=RNG, control="geometric", confidence=confidence)


def _common(res):
    return dict(PARAMS, K=K, T=T, option=OPTION, obs=OBS, n_obs=res.n_obs, seed=SEED,
                rng_method=RNG)


def _blank(v):
    return "" if v is None else v


def _write(path: Path, fields, rows) -> None:
    path.parent.mkdir(exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: (repr(v) if isinstance(v, float) else v) for k, v in row.items()})


def _timed(extra):
    def run(n):
        res = _price(n, extra)
        return res, res.elapsed
    return run


def main() -> None:
    t0 = time.perf_counter()
    _price(2_000, {})                                              # échauffement
    ref = reference()
    print(f"référence {ref.price:.6f} ± {ref.std_error:.6f} ({ref.elapsed:.1f} s)", flush=True)

    grid = log_grid(*N_GRID)
    conv, slopes = [], []
    for name, extra in ESTIMATORS.items():
        pts = []
        for n in grid:
            res = _price(n, extra)
            hw = res.z * res.std_error
            pts.append((n, hw))
            conv.append({"estimator": name, "n_paths": n, **_common(res),
                         "confidence": CONFIDENCE, "z": res.z, "price": res.price,
                         "std_error": res.std_error, "half_width_95": hw, "ci_low": res.ci_low,
                         "ci_high": res.ci_high, "beta": _blank(res.beta),
                         "corr": _blank(res.corr), "antithetic_corr": _blank(res.antithetic_corr),
                         "n_uniforms": res.n_uniforms, "time_s": res.elapsed,
                         "ref_price": ref.price, "ref_std_error": ref.std_error,
                         "ref_n_paths": ref.n_paths, "ref_seed": ref.seed,
                         "price_minus_ref_in_se": (res.price - ref.price)
                         / math.hypot(res.std_error, ref.std_error)})
        ns, hws = np.array([p[0] for p in pts]), np.array([p[1] for p in pts])
        slope, intercept = loglog_slope(ns, hws)
        slopes.append({"estimator": name, "n_points": len(pts), "n_min": grid[0],
                       "n_max": grid[-1], "slope": slope,
                       "slope_std_error": _slope_std_error(ns, hws, slope, intercept),
                       "intercept": intercept, "expected_slope": EXPECTED_SLOPE,
                       "slope_minus_expected": slope - EXPECTED_SLOPE})
        print(f"{name:<19} pente {slope:+.4f}  demi-largeur à 1e6 {hws[-1]:.6f}", flush=True)
    _write(OUT_CONV, FIELDS_CONV, conv)
    _write(OUT_SLOPES, FIELDS_SLOPES, slopes)

    nreq, per_path = [], {}
    for name, extra in ESTIMATORS.items():
        runs = [_price(N_SIGMA, extra) for _ in range(N_TIMING_RUNS)]
        res = runs[0]
        t_path = statistics.median(r.elapsed for r in runs) / N_SIGMA
        per_path[name] = t_path
        sigma_hat = res.std_error * math.sqrt(N_SIGMA)
        for eps in EPSILONS:
            n = n_required(sigma_hat, eps, res.z)
            if name in PAIRED:
                n += n % 2
            nreq.append({"estimator": name, "epsilon": eps, "confidence": CONFIDENCE,
                         "z": res.z, **_common(res), "sigma_hat_n_paths": N_SIGMA,
                         "std_error_at_n": res.std_error, "sigma_hat": sigma_hat,
                         "n_required": n, "time_per_path_s": t_path,
                         "time_runs_s": " ".join(repr(r.elapsed) for r in runs),
                         "time_estimated_s": n * t_path})
            print(f"{name:<19} eps={eps:<6} N = {n:>13,d}  temps estimé {n * t_path:12.2f} s",
                  flush=True)
    _write(OUT_NREQ, FIELDS_NREQ, nreq)

    eq = []
    for budget in BUDGETS:
        for name, extra in ESTIMATORS.items():
            best = largest_n_within_budget(_timed(extra), budget,
                                           n_start=0.9 * budget / per_path[name],
                                           even=name in PAIRED)
            res = best["result"]
            eq.append({"estimator": name, "budget_s": budget, "n_paths": best["n_paths"],
                       "time_s": best["time_s"], **_common(res), "price": res.price,
                       "std_error": res.std_error, "half_width_95": res.z * res.std_error,
                       "n_trials": len(best["trials"]),
                       "trials": " ".join(f"{n}:{t!r}" for n, t in best["trials"])})
            print(f"budget {budget:>3} s {name:<19} N = {best['n_paths']:>9,d} "
                  f"({best['time_s']:.3f} s)  demi-largeur {res.z * res.std_error:.6f}",
                  flush=True)
    _write(OUT_TIME, FIELDS_TIME, eq)
    print(f"{len(conv)} + {len(slopes)} + {len(nreq)} + {len(eq)} lignes -> results/ "
          f"({time.perf_counter() - t0:.1f} s)")


if __name__ == "__main__":
    main()
