"""Grille P2 de comparaison asiatique / européen (énoncé 2, question 2).

Actif théorique (tranché par Cowork, 17/11/2026) : S0 = 100, σ = 0,20, r = 0,03, q = 0,01,
observations mensuelles, N = 200 000 trajectoires, seed 20261117, normales par transformée
inverse (AS241). K ∈ {80, 90, 100, 110, 120}, T ∈ {0,25 ; 0,5 ; 1 ; 2}, call et put.

Pour chaque (K, T, option) : asiatique MC (prix, écart-type, IC 95 %, temps), européen MC
(prix, écart-type, IC 95 %, temps), européen Black-Scholes fermé, écart européen MC − BS en
écarts-types de l'estimateur, ratio asiatique MC / européen BS.

Remarque de lecture : chaque appel repart de la même seed, avec les mêmes dates mensuelles.
Pour un T donné, les 10 lignes (5 strikes × call/put) et les deux pricers (asiatique,
européen MC) utilisent donc exactement les mêmes trajectoires : les écarts MC − BS des lignes
d'un même T ne sont pas indépendants.

Valeurs écrites en pleine précision (arrondi à 10^-4 dans le rapport).
Usage : .venv/Scripts/python.exe scripts/p2_grid.py
"""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pricer.asian import price_asian, price_european_mc  # noqa: E402
from pricer.black_scholes import bs_price  # noqa: E402

PARAMS = dict(S0=100.0, sigma=0.20, r=0.03, q=0.01)
OBS = "monthly"
N_PATHS = 200_000
SEED = 20261117
RNG = "inverse"
STRIKES = (80.0, 90.0, 100.0, 110.0, 120.0)
MATURITIES = (0.25, 0.5, 1.0, 2.0)
OPTIONS = ("call", "put")
OUT = ROOT / "results" / "p2_grid.csv"

FIELDS = ["K", "T", "option", "S0", "sigma", "r", "q", "obs", "n_obs", "n_paths", "seed",
          "rng_method",
          "asian_price", "asian_std_error", "asian_ci_low", "asian_ci_high", "asian_time_s",
          "euro_mc_price", "euro_mc_std_error", "euro_mc_ci_low", "euro_mc_ci_high",
          "euro_mc_time_s", "euro_bs_price", "euro_mc_minus_bs_in_se",
          "ratio_asian_over_euro_bs"]


def main() -> None:
    rows = []
    t0 = time.perf_counter()
    for T in MATURITIES:
        for K in STRIKES:
            for option in OPTIONS:
                kw = dict(PARAMS, K=K, T=T, option=option)
                sim = dict(obs=OBS, n_paths=N_PATHS, seed=SEED, rng_method=RNG)
                a = price_asian(**kw, **sim)
                e = price_european_mc(**kw, **sim)
                bs = bs_price(**kw)
                rows.append({
                    "K": K, "T": T, "option": option, **PARAMS, "obs": OBS, "n_obs": a.n_obs,
                    "n_paths": N_PATHS, "seed": SEED, "rng_method": RNG,
                    "asian_price": a.price, "asian_std_error": a.std_error,
                    "asian_ci_low": a.ci_low, "asian_ci_high": a.ci_high,
                    "asian_time_s": a.elapsed,
                    "euro_mc_price": e.price, "euro_mc_std_error": e.std_error,
                    "euro_mc_ci_low": e.ci_low, "euro_mc_ci_high": e.ci_high,
                    "euro_mc_time_s": e.elapsed, "euro_bs_price": bs,
                    "euro_mc_minus_bs_in_se": (e.price - bs) / e.std_error,
                    "ratio_asian_over_euro_bs": a.price / bs,
                })
                print(f"T={T:<5} K={K:<6} {option:<4}  asian {a.price:9.4f} ± {a.std_error:.4f}  "
                      f"euro MC {e.price:9.4f} ± {e.std_error:.4f}  BS {bs:9.4f}  "
                      f"({(e.price - bs) / e.std_error:+.2f} σ)", flush=True)
    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} lignes -> {OUT.relative_to(ROOT)} ({time.perf_counter() - t0:.1f} s)")


if __name__ == "__main__":
    main()
