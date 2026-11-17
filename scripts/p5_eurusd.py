"""Cas réel EUR/USD (P5a, étape 3) → results/p5_eurusd.csv et results/p5_eurusd_sensitivity.csv.

Cas (décision de Loup, 17/11/2026) : entreprise française qui encaisse des USD chaque mois pendant
1 an et couvre son taux moyen. Elle perd si l'euro monte (ses USD valent moins d'euros) : elle
achète un call asiatique sur EUR/USD (moyenne arithmétique de 12 fixings mensuels, T = 1).

Paramètres : results/p5_market.csv (scripts/p5_market.py) : S0 = dernier fixing BCE, σ historique
BCE 252 fixings, r = Trésor 1 an (USD), q = BCE AAA 1 an (EUR).
Strikes : K = S0 (à la monnaie spot) et K = forward 1 an F = S0·e^{(r − q)T}.
Monte-Carlo : N = 200 000, seed 20261117, transformée inverse AS241, contrôle géométrique (β optimal,
slide 50) + antithétique ; européen BS fermé (avec q) et européen MC sur les mêmes trajectoires
(même seed, même grille mensuelle, mêmes paires antithétiques). Call et put en lignes séparées.

Prix : USD pour 1 EUR de nominal, et en % de S0.
Couverture (call, hypothèse de nominal illustrative) : 1 000 000 USD encaissés par mois, 12 mois,
nominal en euros N_EUR = 12 × 1 000 000 / K ; prime en USD = prix × N_EUR ; prime en EUR = prime USD
/ S0 (convertie au fixing du jour).

Sensibilité : σ ∈ {4 % ; 5 % ; σ mesuré ; 6 % ; 7 % ; 8 %}, mêmes strikes (le forward ne dépend pas
de σ), call et put : prix asiatique (MC, même réglage), européen BS, ratio asiatique / européen.

Usage : .venv/Scripts/python.exe scripts/p5_eurusd.py
"""
from __future__ import annotations

import csv
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from p5_market import calibrate  # noqa: E402
from pricer.asian import price_asian, price_european_mc  # noqa: E402
from pricer.black_scholes import bs_price  # noqa: E402

OUT = ROOT / "results" / "p5_eurusd.csv"
OUT_SENS = ROOT / "results" / "p5_eurusd_sensitivity.csv"
SEED = 20261117
N_PATHS = 200_000
T = 1.0
OBS = "monthly"
RNG = "inverse"
OPTIONS = ("call", "put")
USD_PER_MONTH = 1_000_000
N_MONTHS = 12
SIGMAS = (0.04, 0.05, None, 0.06, 0.07, 0.08)      # None = σ mesuré (BCE)
HEDGE_FORMULA = ("N_EUR = 12 × 1 000 000 / K ; prime_USD = prix × N_EUR ; "
                 "prime_EUR = prime_USD / S0")
NOTIONAL_NOTE = "nominal illustratif : 1 000 000 USD encaissés par mois pendant 12 mois"

FIELDS = ["strike_type", "K", "option", "S0", "S0_date", "sigma", "sigma_source", "r", "r_date",
          "q", "q_date", "T", "obs", "n_obs", "n_paths", "seed", "rng_method", "control",
          "beta_mode", "antithetic", "asian_price", "asian_std_error", "asian_ci_low",
          "asian_ci_high", "asian_pct_S0", "beta", "corr", "variance_ratio", "antithetic_corr",
          "asian_std_error_no_control", "euro_mc_price", "euro_mc_std_error", "euro_mc_ci_low",
          "euro_mc_ci_high", "euro_bs_price", "euro_bs_pct_S0", "euro_mc_minus_bs_in_se",
          "ratio_asian_euro_bs", "ratio_ci_low", "ratio_ci_high", "usd_per_month", "n_months",
          "notional_eur", "hedge_cost_usd", "hedge_cost_eur", "hedge_cost_pct_receipts",
          "hedge_cost_formula", "notional_note", "time_asian_s", "time_euro_s"]
FIELDS_SENS = ["sigma", "sigma_label", "strike_type", "K", "option", "S0", "r", "q", "T", "n_obs",
               "n_paths", "seed", "rng_method", "control", "beta_mode", "antithetic",
               "asian_price", "asian_std_error", "asian_ci_low", "asian_ci_high",
               "euro_bs_price", "euro_mc_price", "euro_mc_std_error", "ratio_asian_euro_bs",
               "ratio_ci_low", "ratio_ci_high", "asian_pct_S0", "euro_bs_pct_S0", "time_s"]


def _write(path: Path, fields, rows) -> None:
    path.parent.mkdir(exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: (repr(float(v)) if isinstance(v, float) else v) for k, v in row.items()})


def _blank(v):
    return "" if v is None else v


def _price_pair(S0, K, sigma, r, q, option):
    common = dict(S0=S0, K=K, sigma=sigma, r=r, T=T, q=q, option=option, obs=OBS,
                  n_paths=N_PATHS, seed=SEED, rng_method=RNG, antithetic=True)
    a = price_asian(**common, control="geometric", beta="optimal")
    e = price_european_mc(**common)
    if a.n_uniforms != e.n_uniforms:
        raise RuntimeError("asiatique et européen n'ont pas consommé le même flux")
    return a, e


def main() -> None:
    t0 = time.perf_counter()
    m = calibrate()
    S0, sigma, r, q = (float(m[k]["value"]) for k in ("S0", "sigma_ecb", "r_usd", "q_eur"))
    strikes = {"spot": S0, "forward": float(m["forward_1y"]["value"])}
    print(f"S0 {S0} ({m['S0']['date']})  sigma {sigma:.6f}  r {r:.6f}  q {q:.6f}  "
          f"F {strikes['forward']:.6f}", flush=True)

    rows = []
    for kind, K in strikes.items():
        for option in OPTIONS:
            a, e = _price_pair(S0, K, sigma, r, q, option)
            bs = bs_price(S0, K, sigma, r, T, q, option)
            row = {"strike_type": kind, "K": K, "option": option, "S0": S0,
                   "S0_date": m["S0"]["date"], "sigma": sigma,
                   "sigma_source": f"historique BCE 252 fixings ({m['sigma_ecb']['date_first']} → "
                                   f"{m['sigma_ecb']['date']})",
                   "r": r, "r_date": m["r_usd"]["date"], "q": q, "q_date": m["q_eur"]["date"],
                   "T": T, "obs": OBS, "n_obs": a.n_obs, "n_paths": N_PATHS, "seed": SEED,
                   "rng_method": RNG, "control": a.control, "beta_mode": a.beta_mode,
                   "antithetic": a.antithetic, "asian_price": a.price,
                   "asian_std_error": a.std_error, "asian_ci_low": a.ci_low,
                   "asian_ci_high": a.ci_high, "asian_pct_S0": 100 * a.price / S0,
                   "beta": a.beta, "corr": a.corr, "variance_ratio": a.variance_ratio,
                   "antithetic_corr": _blank(a.antithetic_corr),
                   "asian_std_error_no_control": a.std_error_no_control,
                   "euro_mc_price": e.price, "euro_mc_std_error": e.std_error,
                   "euro_mc_ci_low": e.ci_low, "euro_mc_ci_high": e.ci_high,
                   "euro_bs_price": bs, "euro_bs_pct_S0": 100 * bs / S0,
                   "euro_mc_minus_bs_in_se": (e.price - bs) / e.std_error,
                   "ratio_asian_euro_bs": a.price / bs, "ratio_ci_low": a.ci_low / bs,
                   "ratio_ci_high": a.ci_high / bs, "usd_per_month": USD_PER_MONTH,
                   "n_months": N_MONTHS, "notional_eur": "", "hedge_cost_usd": "",
                   "hedge_cost_eur": "", "hedge_cost_pct_receipts": "", "hedge_cost_formula": "",
                   "notional_note": "", "time_asian_s": a.elapsed, "time_euro_s": e.elapsed}
            if option == "call":                     # la couverture de l'exportateur est le call
                n_eur = N_MONTHS * USD_PER_MONTH / K
                usd = a.price * n_eur
                row.update(notional_eur=n_eur, hedge_cost_usd=usd, hedge_cost_eur=usd / S0,
                           hedge_cost_pct_receipts=100 * usd / (N_MONTHS * USD_PER_MONTH),
                           hedge_cost_formula=HEDGE_FORMULA, notional_note=NOTIONAL_NOTE)
            rows.append(row)
            print(f"{kind:<8} {option:<4} K {K:.6f}  asiat {a.price:.6f} +- {a.std_error:.6f}  "
                  f"euro MC {e.price:.6f} +- {e.std_error:.6f}  BS {bs:.6f}  "
                  f"ratio {a.price / bs:.4f}  VR {a.variance_ratio:.1f}", flush=True)
    _write(OUT, FIELDS, rows)

    sens = []
    for s in SIGMAS:
        sig, label = (sigma, "mesuré") if s is None else (s, "grille")
        for kind, K in strikes.items():
            for option in OPTIONS:
                a, e = _price_pair(S0, K, sig, r, q, option)
                bs = bs_price(S0, K, sig, r, T, q, option)
                sens.append({"sigma": sig, "sigma_label": label, "strike_type": kind, "K": K,
                             "option": option, "S0": S0, "r": r, "q": q, "T": T,
                             "n_obs": a.n_obs, "n_paths": N_PATHS, "seed": SEED,
                             "rng_method": RNG, "control": a.control, "beta_mode": a.beta_mode,
                             "antithetic": a.antithetic, "asian_price": a.price,
                             "asian_std_error": a.std_error, "asian_ci_low": a.ci_low,
                             "asian_ci_high": a.ci_high, "euro_bs_price": bs,
                             "euro_mc_price": e.price, "euro_mc_std_error": e.std_error,
                             "ratio_asian_euro_bs": a.price / bs, "ratio_ci_low": a.ci_low / bs,
                             "ratio_ci_high": a.ci_high / bs, "asian_pct_S0": 100 * a.price / S0,
                             "euro_bs_pct_S0": 100 * bs / S0, "time_s": a.elapsed + e.elapsed})
        print(f"sigma {sig:.6f} ({label}) fait", flush=True)
    _write(OUT_SENS, FIELDS_SENS, sens)
    print(f"temps total {time.perf_counter() - t0:.1f} s")


if __name__ == "__main__":
    main()
