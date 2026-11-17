"""Tableau de réduction de variance à la monnaie (énoncé 2, questions 3 et 4).

Actif théorique du projet : S0 = 100, σ = 0,20, r = 0,03, q = 0,01, observations mensuelles.
K = 100, T ∈ {0,25 ; 1 ; 2}, call et put, N = 200 000 trajectoires, seed 20261117, normales par
transformée inverse (AS241).

Cinq estimateurs par (T, option) :
    plain                     sans réduction de variance
    antithetic                trajectoires jumelées (Z, −Z) : 100 000 paires
    control_beta_optimal      contrôle géométrique, b optimal estimé sur l'échantillon
    antithetic_control        les deux : contrôle (b optimal) sur les moyennes de paires
    control_beta_1            contrôle géométrique avec b = 1

Colonnes :
    price, std_error, ci_low, ci_high   prix, écart-type de l'estimateur, IC 95 %
    beta, corr                          b utilisé et corrélation empirique de (Y, X) ; pour
                                        antithetic_control, sur les moyennes de paires
    geometric_closed_form               E[X], prix fermé de l'asiatique géométrique
    var_ratio_vs_plain                  (écart-type plain / écart-type)², à N égal
    var_ratio_same_sample               variance sans contrôle / avec contrôle sur le même
                                        échantillon (MCResult.variance_ratio)
    time_median_s, time_runs_s          médiane des temps de 3 runs, et les 3 temps
    efficiency                          variance de l'estimateur × temps = std_error² × time_median_s
    efficiency_gain_vs_plain            efficiency(plain) / efficiency : > 1 = mieux que plain

Lecture : chaque appel repart de la même seed. plain, control_beta_optimal et control_beta_1
utilisent donc exactement les mêmes 200 000 trajectoires ; antithetic et antithetic_control
utilisent les 100 000 premières et leurs jumelles. Les prix et écarts-types sont reproductibles
au bit près (vérifié sur les 3 runs) ; les temps dépendent de la machine et de sa charge.

Valeurs écrites en pleine précision (arrondi à 10^-4 dans le rapport).
Usage : .venv/Scripts/python.exe scripts/p3_vr_atm.py
"""
from __future__ import annotations

import csv
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pricer.asian import price_asian  # noqa: E402
from pricer.geometric import geometric_asian_price  # noqa: E402

PARAMS = dict(S0=100.0, sigma=0.20, r=0.03, q=0.01)
K = 100.0
OBS = "monthly"
N_PATHS = 200_000
SEED = 20261117
RNG = "inverse"
MATURITIES = (0.25, 1.0, 2.0)
OPTIONS = ("call", "put")
N_RUNS = 3
OUT = ROOT / "results" / "p3_vr_atm.csv"

ESTIMATORS = (
    ("plain", {}),
    ("antithetic", dict(antithetic=True)),
    ("control_beta_optimal", dict(control="geometric")),
    ("antithetic_control", dict(antithetic=True, control="geometric")),
    ("control_beta_1", dict(control="geometric", beta=1.0)),
)

FIELDS = ["T", "option", "estimator", "K", "S0", "sigma", "r", "q", "obs", "n_obs", "n_paths",
          "seed", "rng_method", "antithetic", "control", "beta_mode",
          "price", "std_error", "ci_low", "ci_high", "beta", "corr", "geometric_closed_form",
          "n_uniforms", "var_ratio_vs_plain", "var_ratio_same_sample",
          "time_median_s", "time_runs_s", "efficiency", "efficiency_gain_vs_plain"]


def _blank(value):
    return "" if value is None else value


def main() -> None:
    t0 = time.perf_counter()
    price_asian(**PARAMS, K=K, T=1.0, n_paths=2_000, control="geometric")   # échauffement
    rows = []
    for T in MATURITIES:
        for option in OPTIONS:
            kw = dict(PARAMS, K=K, T=T, option=option, obs=OBS, n_paths=N_PATHS, seed=SEED,
                      rng_method=RNG)
            geo = geometric_asian_price(**PARAMS, K=K, T=T, option=option, obs=OBS)
            plain_se = plain_eff = None
            for name, extra in ESTIMATORS:
                runs = [price_asian(**kw, **extra) for _ in range(N_RUNS)]
                res = runs[0]
                if any((x.price, x.std_error) != (res.price, res.std_error) for x in runs):
                    raise RuntimeError(f"{name} T={T} {option} : runs non reproductibles")
                t_med = statistics.median(x.elapsed for x in runs)
                eff = res.std_error**2 * t_med
                if name == "plain":
                    plain_se, plain_eff = res.std_error, eff
                rows.append({
                    "T": T, "option": option, "estimator": name, "K": K, **PARAMS, "obs": OBS,
                    "n_obs": res.n_obs, "n_paths": res.n_paths, "seed": SEED, "rng_method": RNG,
                    "antithetic": res.antithetic, "control": _blank(res.control),
                    "beta_mode": _blank(res.beta_mode),
                    "price": res.price, "std_error": res.std_error, "ci_low": res.ci_low,
                    "ci_high": res.ci_high, "beta": _blank(res.beta), "corr": _blank(res.corr),
                    "geometric_closed_form": geo, "n_uniforms": res.n_uniforms,
                    "var_ratio_vs_plain": (plain_se / res.std_error) ** 2,
                    "var_ratio_same_sample": _blank(res.variance_ratio),
                    "time_median_s": t_med,
                    "time_runs_s": " ".join(repr(x.elapsed) for x in runs),
                    "efficiency": eff, "efficiency_gain_vs_plain": plain_eff / eff,
                })
                print(f"T={T:<5} {option:<4} {name:<21} {res.price:8.4f} ± {res.std_error:.4f}  "
                      f"ratio var {(plain_se / res.std_error) ** 2:9.1f}  "
                      f"temps {t_med:.3f} s  gain eff. {plain_eff / eff:9.1f}", flush=True)
    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} lignes -> {OUT.relative_to(ROOT)} ({time.perf_counter() - t0:.1f} s)")


if __name__ == "__main__":
    main()
