"""Sensibilités de l'estimateur (P4, étape 3) : biais de β, méthode d'aléa, fréquence
d'observation, grille K × T refaite avec le contrôle.

Actif théorique (CLAUDE.md) : S0 = 100, σ = 0,20, r = 0,03, q = 0,01, contrôle géométrique avec
b optimal (slide 50) sauf mention contraire. IC à 95 % (z = Φ^{-1}(0,975) par AS241).

1. Biais de β (results/p4_beta_bias.csv, détail par seed dans p4_beta_bias_runs.csv) : call
   K = 100, T = 1, mensuel ; N = 1 000 trajectoires, 500 seeds 20261117 + i (i = 0..499), contrôle
   « optimal » (b estimé sur l'échantillon, biais d'ordre 1/N) et « pilot » (b estimé sur 10 000
   trajectoires préalables, sans biais). Biais = moyenne des 500 prix − référence (contrôle à
   N = 4 000 000, même référence que p4_convergence.py), exprimé en écarts-types de la moyenne
   (sd_of_mean = s_prix/√500) et en écart-type combiné √(sd_of_mean² + se_ref²).
   Diagnostic d'indépendance : les flux de seeds voisines du LCG Park-Miller occupent des positions
   pseudo-aléatoires du même cycle ; on compte exactement les paires de seeds dont les fenêtres
   d'uniformes se recouvrent, et les seeds dont la fenêtre recouvre celle de la référence.
2. Méthode d'aléa (results/p4_rng_methods.csv) : les 4 méthodes de pricer.normals et la
   transformée inverse avec Hastings, N = 200 000, sans et avec contrôle, même seed : prix, IC,
   temps (médiane de 3 runs), uniformes consommées, écart à la référence en écarts-types.
3. Fréquence (results/p4_frequency.csv) : n_obs ∈ {1, 4, 12, 52, 252} dates sur T = 1, K = 100,
   call et put, N = 200 000, contrôle : asiatique arithmétique (MC), géométrique exact (formule
   discrète), limite géométrique continue (σ_G² = σ²T/3, hors cours) et européen BS.
4. Grille de P2 refaite avec le contrôle (results/p4_grid_cv.csv) : K ∈ {80, …, 120},
   T ∈ {0,25 ; 0,5 ; 1 ; 2}, call et put, mensuel, N = 200 000 : ratio asiatique / européen BS
   et son IC (IC du prix divisé par le prix BS, exact) ; prix sans contrôle de results/p2_grid.csv
   repris pour comparaison.

Valeurs écrites en pleine précision (arrondi à 10^-4 dans le rapport).
Usage : .venv/Scripts/python.exe scripts/p4_sensibilites.py
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

from p4_convergence import reference  # noqa: E402
from pricer.asian import price_asian  # noqa: E402
from pricer.black_scholes import bs_price  # noqa: E402
from pricer.geometric import (geometric_asian_continuous_price,  # noqa: E402
                              geometric_asian_price)
from pricer.paths import RNG_METHODS  # noqa: E402
from pricer.rng import LCG  # noqa: E402

PARAMS = dict(S0=100.0, sigma=0.20, r=0.03, q=0.01)
SEED = 20261117
RNG = "inverse"
K0, T0 = 100.0, 1.0

N_BIAS, N_SEEDS = 1_000, 500
N_RNG, N_RNG_RUNS = 200_000, 3
FREQ_N_OBS = (1, 4, 12, 52, 252)
N_FREQ = 200_000
GRID_STRIKES = (80.0, 90.0, 100.0, 110.0, 120.0)
GRID_MATURITIES = (0.25, 0.5, 1.0, 2.0)
N_GRID = 200_000
OPTIONS = ("call", "put")

OUT_BIAS = ROOT / "results" / "p4_beta_bias.csv"
OUT_BIAS_RUNS = ROOT / "results" / "p4_beta_bias_runs.csv"
OUT_RNG = ROOT / "results" / "p4_rng_methods.csv"
OUT_FREQ = ROOT / "results" / "p4_frequency.csv"
OUT_GRID = ROOT / "results" / "p4_grid_cv.csv"
P2_GRID = ROOT / "results" / "p2_grid.csv"

MODEL = ["S0", "sigma", "r", "q"]
FIELDS_BIAS = ["beta_mode", "n_seeds", "seed_first", "seed_last", "n_paths", "n_pilot", *MODEL,
               "K", "T", "option", "obs", "n_obs", "rng_method", "mean_price", "sd_prices",
               "sd_of_mean", "mean_std_error", "ref_price", "ref_std_error", "ref_n_paths",
               "ref_seed", "bias", "bias_in_sd_of_mean", "bias_in_combined_se",
               "ci95_coverage", "mean_beta", "sd_beta", "n_uniforms_per_run",
               "n_seed_pairs_overlapping", "n_seeds_overlapping_ref", "time_total_s"]
FIELDS_RUNS = ["beta_mode", "seed", "price", "std_error", "ci_low", "ci_high", "beta",
               "ref_in_ci"]
FIELDS_RNG = ["rng_method", "control", "n_paths", *MODEL, "K", "T", "option", "obs", "n_obs",
              "seed", "price", "std_error", "ci_low", "ci_high", "beta", "corr", "n_uniforms",
              "uniforms_per_normal", "time_median_s", "time_runs_s", "ref_price",
              "ref_std_error", "minus_ref_in_se"]
FIELDS_FREQ = ["option", "n_obs", *MODEL, "K", "T", "n_paths", "seed", "rng_method", "control",
               "price", "std_error", "ci_low", "ci_high", "beta", "corr", "variance_ratio",
               "geometric_exact", "geometric_continuous", "euro_bs_price",
               "geometric_exact_minus_continuous", "price_minus_geometric_exact",
               "ratio_to_euro_bs", "time_s"]
FIELDS_GRID = ["K", "T", "option", *MODEL, "obs", "n_obs", "n_paths", "seed", "rng_method",
               "control", "price", "std_error", "ci_low", "ci_high", "beta", "corr",
               "variance_ratio", "euro_bs_price", "ratio", "ratio_ci_low", "ratio_ci_high",
               "p2_plain_price", "p2_plain_std_error", "time_s"]


def _blank(v):
    return "" if v is None else v


def _write(path: Path, fields, rows) -> None:
    path.parent.mkdir(exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: (repr(float(v)) if isinstance(v, float) else v)   # np.float64 -> float
                        for k, v in row.items()})


# --- 1. biais de β --------------------------------------------------------------------------------

def _overlaps(seeds: list[int], window: int, ref_seed: int, ref_window: int) -> tuple[int, int]:
    """(paires de seeds dont les fenêtres se recouvrent, seeds dont la fenêtre recouvre celle de
    la référence). Le flux de la seed x utilise les états x_1..x_W ; ceux de x et y se recouvrent
    si y ∈ {x_1, …, x_{W−1}} ou x ∈ {y_1, …, y_{W−1}}."""
    targets = np.array(seeds, dtype=np.uint64)
    pairs, near_ref = set(), set()
    for i, s in enumerate(seeds):
        states = LCG(s).integers(window - 1)
        pairs.update(frozenset((i, int(j))) for j in np.flatnonzero(np.isin(targets, states))
                     if j != i)
        if np.isin(np.uint64(ref_seed), states):
            near_ref.add(i)
    g, done = LCG(ref_seed), 0
    while done < ref_window - 1:
        chunk = min(1_000_000, ref_window - 1 - done)
        near_ref.update(int(j) for j in np.flatnonzero(np.isin(targets, g.integers(chunk))))
        done += chunk
    return len(pairs), len(near_ref)


def beta_bias(ref):
    summary, runs = [], []
    seeds = [SEED + i for i in range(N_SEEDS)]
    for mode in ("optimal", "pilot"):
        t0 = time.perf_counter()
        res = [price_asian(**PARAMS, K=K0, T=T0, option="call", obs="monthly", n_paths=N_BIAS,
                           seed=s, rng_method=RNG, control="geometric", beta=mode)
               for s in seeds]
        elapsed = time.perf_counter() - t0
        prices = np.array([x.price for x in res])
        betas = np.array([x.beta for x in res])
        sd_mean = prices.std(ddof=1) / math.sqrt(N_SEEDS)
        bias = float(prices.mean()) - ref.price
        inside = [x.ci_low <= ref.price <= x.ci_high for x in res]
        window = res[0].n_uniforms
        n_pairs, n_ref = _overlaps(seeds, window, ref.seed, ref.n_uniforms)
        summary.append({
            "beta_mode": mode, "n_seeds": N_SEEDS, "seed_first": seeds[0], "seed_last": seeds[-1],
            "n_paths": N_BIAS, "n_pilot": res[0].n_pilot, **PARAMS, "K": K0, "T": T0,
            "option": "call", "obs": "monthly", "n_obs": res[0].n_obs, "rng_method": RNG,
            "mean_price": float(prices.mean()), "sd_prices": float(prices.std(ddof=1)),
            "sd_of_mean": float(sd_mean),
            "mean_std_error": float(np.mean([x.std_error for x in res])),
            "ref_price": ref.price, "ref_std_error": ref.std_error, "ref_n_paths": ref.n_paths,
            "ref_seed": ref.seed, "bias": bias, "bias_in_sd_of_mean": bias / sd_mean,
            "bias_in_combined_se": bias / math.hypot(sd_mean, ref.std_error),
            "ci95_coverage": sum(inside) / N_SEEDS, "mean_beta": float(betas.mean()),
            "sd_beta": float(betas.std(ddof=1)), "n_uniforms_per_run": window,
            "n_seed_pairs_overlapping": n_pairs, "n_seeds_overlapping_ref": n_ref,
            "time_total_s": elapsed})
        runs += [{"beta_mode": mode, "seed": s, "price": x.price, "std_error": x.std_error,
                  "ci_low": x.ci_low, "ci_high": x.ci_high, "beta": x.beta, "ref_in_ci": ok}
                 for s, x, ok in zip(seeds, res, inside)]
        print(f"beta {mode:<7} moyenne {prices.mean():.6f}  ref {ref.price:.6f}  "
              f"biais {bias:+.6f} = {bias / sd_mean:+.2f} sd  couverture IC95 "
              f"{sum(inside) / N_SEEDS:.3f}  recouvrements {n_pairs} paires, {n_ref} avec ref",
              flush=True)
    return summary, runs


# --- 2. méthode d'aléa ----------------------------------------------------------------------------

def rng_methods(ref):
    rows = []
    for method in RNG_METHODS:
        for control in (None, "geometric"):
            runs = [price_asian(**PARAMS, K=K0, T=T0, option="call", obs="monthly",
                                n_paths=N_RNG, seed=SEED, rng_method=method, control=control)
                    for _ in range(N_RNG_RUNS)]
            x = runs[0]
            if any((r.price, r.std_error) != (x.price, x.std_error) for r in runs):
                raise RuntimeError(f"{method} : runs non reproductibles")
            t_med = statistics.median(r.elapsed for r in runs)
            rows.append({"rng_method": method, "control": _blank(control), "n_paths": N_RNG,
                         **PARAMS, "K": K0, "T": T0, "option": "call", "obs": "monthly",
                         "n_obs": x.n_obs, "seed": SEED, "price": x.price,
                         "std_error": x.std_error, "ci_low": x.ci_low, "ci_high": x.ci_high,
                         "beta": _blank(x.beta), "corr": _blank(x.corr),
                         "n_uniforms": x.n_uniforms,
                         "uniforms_per_normal": x.n_uniforms / (N_RNG * x.n_obs),
                         "time_median_s": t_med,
                         "time_runs_s": " ".join(repr(r.elapsed) for r in runs),
                         "ref_price": ref.price, "ref_std_error": ref.std_error,
                         "minus_ref_in_se": (x.price - ref.price)
                         / math.hypot(x.std_error, ref.std_error)})
            print(f"{method:<21} {str(control):<9} {x.price:.6f} +- {x.std_error:.6f}  "
                  f"{t_med:.3f} s  {rows[-1]['minus_ref_in_se']:+.2f} se", flush=True)
    return rows


# --- 3. fréquence ---------------------------------------------------------------------------------

def frequency():
    rows = []
    for option in OPTIONS:
        cont = geometric_asian_continuous_price(**PARAMS, K=K0, T=T0, option=option)
        euro = bs_price(**PARAMS, K=K0, T=T0, option=option)
        for n in FREQ_N_OBS:
            x = price_asian(**PARAMS, K=K0, T=T0, option=option, obs=n, n_paths=N_FREQ,
                            seed=SEED, rng_method=RNG, control="geometric")
            geo = geometric_asian_price(**PARAMS, K=K0, T=T0, option=option, obs=n)
            rows.append({"option": option, "n_obs": n, **PARAMS, "K": K0, "T": T0,
                         "n_paths": N_FREQ, "seed": SEED, "rng_method": RNG,
                         "control": "geometric", "price": x.price, "std_error": x.std_error,
                         "ci_low": x.ci_low, "ci_high": x.ci_high, "beta": x.beta,
                         "corr": x.corr, "variance_ratio": x.variance_ratio,
                         "geometric_exact": geo, "geometric_continuous": cont,
                         "euro_bs_price": euro, "geometric_exact_minus_continuous": geo - cont,
                         "price_minus_geometric_exact": x.price - geo,
                         "ratio_to_euro_bs": x.price / euro, "time_s": x.elapsed})
            print(f"{option:<4} n_obs={n:<4} arith {x.price:.6f} +- {x.std_error:.6f}  "
                  f"geo {geo:.6f}  geo continu {cont:.6f}  BS {euro:.6f}", flush=True)
    return rows


# --- 4. grille K × T avec contrôle ----------------------------------------------------------------

def grid_cv():
    with P2_GRID.open(encoding="utf-8") as f:
        p2 = {(float(r["K"]), float(r["T"]), r["option"]): r for r in csv.DictReader(f)}
    rows = []
    for T in GRID_MATURITIES:
        for K in GRID_STRIKES:
            for option in OPTIONS:
                x = price_asian(**PARAMS, K=K, T=T, option=option, obs="monthly",
                                n_paths=N_GRID, seed=SEED, rng_method=RNG, control="geometric")
                bs = bs_price(**PARAMS, K=K, T=T, option=option)
                old = p2[(K, T, option)]
                rows.append({"K": K, "T": T, "option": option, **PARAMS, "obs": "monthly",
                             "n_obs": x.n_obs, "n_paths": N_GRID, "seed": SEED,
                             "rng_method": RNG, "control": "geometric", "price": x.price,
                             "std_error": x.std_error, "ci_low": x.ci_low,
                             "ci_high": x.ci_high, "beta": x.beta, "corr": x.corr,
                             "variance_ratio": x.variance_ratio, "euro_bs_price": bs,
                             "ratio": x.price / bs, "ratio_ci_low": x.ci_low / bs,
                             "ratio_ci_high": x.ci_high / bs,
                             "p2_plain_price": float(old["asian_price"]),
                             "p2_plain_std_error": float(old["asian_std_error"]),
                             "time_s": x.elapsed})
        print(f"grille T={T} faite", flush=True)
    return rows


def main() -> None:
    t0 = time.perf_counter()
    ref = reference()
    print(f"reference {ref.price:.6f} +- {ref.std_error:.6f} (seed {ref.seed})", flush=True)
    summary, runs = beta_bias(ref)
    _write(OUT_BIAS, FIELDS_BIAS, summary)
    _write(OUT_BIAS_RUNS, FIELDS_RUNS, runs)
    t1 = time.perf_counter()
    _write(OUT_RNG, FIELDS_RNG, rng_methods(ref))
    t2 = time.perf_counter()
    _write(OUT_FREQ, FIELDS_FREQ, frequency())
    t3 = time.perf_counter()
    _write(OUT_GRID, FIELDS_GRID, grid_cv())
    t4 = time.perf_counter()
    print(f"temps : biais beta {t1 - t0:.1f} s, alea {t2 - t1:.1f} s, frequence {t3 - t2:.1f} s, "
          f"grille {t4 - t3:.1f} s ; total {t4 - t0:.1f} s")


if __name__ == "__main__":
    main()
