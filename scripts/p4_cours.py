"""Exercices du cours reproduits : slides 77 et 78 de PricingMonteCarlo_2026.

Slide 77 (variable de contrôle, asiatique) : S0 = 50, T = 1/4, σ = 20 %, r = 3 %, q = 0, fixing
journalier, call et put sur moyenne arithmétique, contrôle = option sur moyenne géométrique,
K ∈ {30, 40, 50, 60, 70}. Lignes du slide : Price Exact, Price MC, Price Ctr. Var., IC(99 %), correl.
    Fixing journalier = 252 jours/an : n_obs = 252 × 1/4 = 63 dates (écrit dans le CSV).
    N = 100 000 trajectoires, seed 20261117, normales par transformée inverse (AS241).
    « Price Exact » est ambigu (aucune formule exacte pour la moyenne arithmétique) : deux colonnes,
      geometric_exact       prix fermé de l'asiatique géométrique (pricer.geometric, slide 76) ;
      arithmetic_reference  contrôle géométrique à N = 4 000 000 (colonnes ref_*, IC à 99 %).
    La référence tire ses normales dans le même LCG, juste après les uniformes de l'échantillon
    N = 100 000 : sa seed est l'état x_n du LCG après n = mc_n_uniforms tirages,
    x_n = a^n·x_0 mod m (saut exact, Park-Miller). Les deux flux sont donc contigus et disjoints :
    la référence est indépendante de l'échantillon testé.
    Les 10 références (≈ 4·10^6 × 63 normales chacune) tournent dans des processus parallèles ;
    les seeds étant fixées, les valeurs ne dépendent pas de l'ordonnancement.

Slide 78 (variables antithétiques, européen) : S0 = 100, T = 1, σ = 30 %, r = 5 %, q = 7 %,
N ∈ {1 000 ; 10 000 ; 100 000}, K ∈ {90, 100, 110}, call et put. Lignes du slide : Price Exact,
Price MC, Variance MC, Price Anti., Variance Anti., Correl.
    S_T simulé en un pas (obs = 1, slide 43). MC et antithétique avec la même seed à
    N égal : l'antithétique utilise les N/2 premiers tirages de la MC et leurs opposés.
    « Variance » : deux lectures possibles, les deux sont écrites :
      mc_variance        s² des N payoffs actualisés (variance empirique en 1/(N − 1), slide 49)
      mc_estimator_var   s²/N, variance de l'estimateur
      anti_variance      s² des N/2 moyennes de paires (h(Z) + h(−Z))/2
      anti_estimator_var s²_paires/(N/2)
    antithetic_corr = corrélation empirique de (h(Z), h(−Z)) sur les paires.

Tous les IC du fichier sont à 99 % (z = Φ^{-1}(0,995) par AS241). Écarts « in_se » :
    slide 77 : (prix − référence)/√(se² + se_ref²) ; slide 78 : (prix − exact)/se.
Valeurs écrites en pleine précision (arrondi à 10^-4 dans le rapport).
Usage : .venv/Scripts/python.exe scripts/p4_cours.py
"""
from __future__ import annotations

import csv
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pricer.asian import price_asian, price_european_mc  # noqa: E402
from pricer.black_scholes import bs_price  # noqa: E402
from pricer.geometric import geometric_asian_price  # noqa: E402
from pricer.rng import PARK_MILLER_A, PARK_MILLER_M  # noqa: E402

SEED = 20261117
RNG = "inverse"
CONFIDENCE = 0.99
OPTIONS = ("call", "put")

EX77 = dict(S0=50.0, T=0.25, sigma=0.20, r=0.03, q=0.0)
EX77_STRIKES = (30.0, 40.0, 50.0, 60.0, 70.0)
EX77_OBS_PER_YEAR = 252
EX77_N = 100_000
EX77_N_REF = 4_000_000

EX78 = dict(S0=100.0, T=1.0, sigma=0.30, r=0.05, q=0.07)
EX78_STRIKES = (90.0, 100.0, 110.0)
EX78_N = (1_000, 10_000, 100_000)

OUT77 = ROOT / "results" / "p4_ex77.csv"
OUT78 = ROOT / "results" / "p4_ex78.csv"

FIELDS77 = ["exercise", "option", "K", "S0", "T", "sigma", "r", "q", "obs_per_year", "n_obs",
            "rng_method", "seed", "n_paths", "confidence", "z",
            "geometric_exact", "arithmetic_reference",
            "mc_price", "mc_std_error", "mc_ci99_low", "mc_ci99_high",
            "cv_price", "cv_std_error", "cv_ci99_low", "cv_ci99_high", "cv_beta", "corr",
            "variance_ratio",
            "ref_seed", "ref_n_paths", "ref_price", "ref_std_error", "ref_ci99_low",
            "ref_ci99_high", "ref_beta", "ref_corr",
            "mc_minus_ref_in_se", "cv_minus_ref_in_se", "ref_in_mc_ci99", "ref_in_cv_ci99",
            "mc_n_uniforms", "mc_time_s", "cv_time_s", "ref_time_s"]

FIELDS78 = ["exercise", "option", "K", "n_paths", "S0", "T", "sigma", "r", "q", "n_obs",
            "rng_method", "seed", "confidence", "z", "price_exact",
            "mc_price", "mc_std_error", "mc_variance", "mc_estimator_var", "mc_ci99_low",
            "mc_ci99_high", "mc_minus_exact_in_se",
            "anti_price", "anti_std_error", "anti_variance", "anti_estimator_var",
            "anti_ci99_low", "anti_ci99_high", "anti_minus_exact_in_se", "antithetic_corr",
            "estimator_var_ratio_mc_over_anti", "mc_n_uniforms", "anti_n_uniforms",
            "mc_time_s", "anti_time_s", "exact_in_mc_ci99", "exact_in_anti_ci99"]


def seed_after(seed: int, n_uniforms: int) -> int:
    """État du LCG Park-Miller après n tirages : x_n = a^n·x_0 mod m (saut exact)."""
    return pow(PARK_MILLER_A, n_uniforms, PARK_MILLER_M) * seed % PARK_MILLER_M


def _ratio(num, den):
    return num / den if den > 0.0 else ""


def _reference(job):
    option, K, ref_seed = job
    res = price_asian(**EX77, K=K, option=option, obs="daily", n_paths=EX77_N_REF,
                      seed=ref_seed, rng_method=RNG, control="geometric", confidence=CONFIDENCE)
    return (option, K), res


def ex77_rows(refs: dict) -> list[dict]:
    rows = []
    for option in OPTIONS:
        for K in EX77_STRIKES:
            kw = dict(EX77, K=K, option=option, obs="daily", n_paths=EX77_N, seed=SEED,
                      rng_method=RNG, confidence=CONFIDENCE)
            mc = price_asian(**kw)
            cv = price_asian(**kw, control="geometric")
            ref = refs[(option, K)]
            geo = geometric_asian_price(**EX77, K=K, option=option, obs=mc.n_obs)
            d_mc = math.sqrt(mc.std_error**2 + ref.std_error**2)
            d_cv = math.sqrt(cv.std_error**2 + ref.std_error**2)
            rows.append({
                "exercise": "slide77", "option": option, "K": K, **EX77,
                "obs_per_year": EX77_OBS_PER_YEAR, "n_obs": mc.n_obs, "rng_method": RNG,
                "seed": SEED, "n_paths": EX77_N, "confidence": CONFIDENCE, "z": mc.z,
                "geometric_exact": geo, "arithmetic_reference": ref.price,
                "mc_price": mc.price, "mc_std_error": mc.std_error, "mc_ci99_low": mc.ci_low,
                "mc_ci99_high": mc.ci_high,
                "cv_price": cv.price, "cv_std_error": cv.std_error, "cv_ci99_low": cv.ci_low,
                "cv_ci99_high": cv.ci_high, "cv_beta": cv.beta, "corr": cv.corr,
                "variance_ratio": cv.variance_ratio,
                "ref_seed": ref.seed, "ref_n_paths": ref.n_paths, "ref_price": ref.price,
                "ref_std_error": ref.std_error, "ref_ci99_low": ref.ci_low,
                "ref_ci99_high": ref.ci_high, "ref_beta": ref.beta, "ref_corr": ref.corr,
                "mc_minus_ref_in_se": _ratio(mc.price - ref.price, d_mc),
                "cv_minus_ref_in_se": _ratio(cv.price - ref.price, d_cv),
                "ref_in_mc_ci99": mc.ci_low <= ref.price <= mc.ci_high,
                "ref_in_cv_ci99": cv.ci_low <= ref.price <= cv.ci_high,
                "mc_n_uniforms": mc.n_uniforms, "mc_time_s": mc.elapsed,
                "cv_time_s": cv.elapsed, "ref_time_s": ref.elapsed,
            })
            print(f"77 {option:<4} K={K:>4.0f}  géo {geo:.4f}  MC {mc.price:.4f}±{mc.std_error:.4f}"
                  f"  CV {cv.price:.4f}±{cv.std_error:.5f}  réf {ref.price:.4f}  "
                  f"corr {cv.corr:.5f}", flush=True)
    return rows


def ex78_rows() -> list[dict]:
    rows = []
    for option in OPTIONS:
        for n in EX78_N:
            for K in EX78_STRIKES:
                kw = dict(EX78, K=K, option=option, obs=1, n_paths=n, seed=SEED,
                          rng_method=RNG, confidence=CONFIDENCE)
                exact = bs_price(**EX78, K=K, option=option)
                mc = price_european_mc(**kw)
                anti = price_european_mc(**kw, antithetic=True)
                rows.append({
                    "exercise": "slide78", "option": option, "K": K, "n_paths": n, **EX78,
                    "n_obs": mc.n_obs, "rng_method": RNG, "seed": SEED,
                    "confidence": CONFIDENCE, "z": mc.z, "price_exact": exact,
                    "mc_price": mc.price, "mc_std_error": mc.std_error,
                    "mc_variance": mc.std_error**2 * n, "mc_estimator_var": mc.std_error**2,
                    "mc_ci99_low": mc.ci_low, "mc_ci99_high": mc.ci_high,
                    "mc_minus_exact_in_se": (mc.price - exact) / mc.std_error,
                    "anti_price": anti.price, "anti_std_error": anti.std_error,
                    "anti_variance": anti.std_error**2 * (n // 2),
                    "anti_estimator_var": anti.std_error**2,
                    "anti_ci99_low": anti.ci_low, "anti_ci99_high": anti.ci_high,
                    "anti_minus_exact_in_se": (anti.price - exact) / anti.std_error,
                    "antithetic_corr": anti.antithetic_corr,
                    "estimator_var_ratio_mc_over_anti": (mc.std_error / anti.std_error) ** 2,
                    "mc_n_uniforms": mc.n_uniforms, "anti_n_uniforms": anti.n_uniforms,
                    "mc_time_s": mc.elapsed, "anti_time_s": anti.elapsed,
                    "exact_in_mc_ci99": mc.ci_low <= exact <= mc.ci_high,
                    "exact_in_anti_ci99": anti.ci_low <= exact <= anti.ci_high,
                })
                print(f"78 {option:<4} N={n:>6} K={K:>4.0f}  exact {exact:.4f}  "
                      f"MC {mc.price:.4f}  anti {anti.price:.4f}  corr "
                      f"{anti.antithetic_corr:.4f}", flush=True)
    return rows


def _write(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: (repr(v) if isinstance(v, float) else v) for k, v in row.items()})


def main() -> None:
    t0 = time.perf_counter()
    n_obs = round(EX77_OBS_PER_YEAR * EX77["T"])               # 63, contrôlé contre MCResult
    ref_seed = seed_after(SEED, EX77_N * n_obs)                # inverse : 1 uniforme / normale
    jobs = [(o, K, ref_seed) for o in OPTIONS for K in EX77_STRIKES]
    workers = max(1, min(len(jobs), (os.cpu_count() or 2) - 2))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = pool.map(_reference, jobs)
        rows78 = ex78_rows()
        _write(OUT78, FIELDS78, rows78)
        refs = dict(futures)
    rows77 = ex77_rows(refs)
    for row in rows77:
        if row["n_obs"] != n_obs or seed_after(SEED, row["mc_n_uniforms"]) != ref_seed:
            raise RuntimeError("la référence ne suit pas exactement l'échantillon N = 100 000")
    _write(OUT77, FIELDS77, rows77)
    print(f"{len(rows77)} + {len(rows78)} lignes -> {OUT77.relative_to(ROOT)}, "
          f"{OUT78.relative_to(ROOT)} ({time.perf_counter() - t0:.1f} s)")


if __name__ == "__main__":
    main()
