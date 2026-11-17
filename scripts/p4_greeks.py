"""Greeks par différences finies (P4, étape 4, bonus ; cours slides 58-61) -> results/p4_greeks.csv.

Actif théorique (CLAUDE.md) : S0 = 100, σ = 0,20, r = 0,03, q = 0,01 ; K ∈ {90, 100, 110}, T = 1,
call et put ; N = 200 000 trajectoires, seed 20261117, normales par transformée inverse (AS241).
Différences centrées : h = 1 % de S0 = 1 (Δ, Γ), h_σ = 0,01 (ν, pour une variation de σ de 1).

Cinq variantes par (K, option) :
    asian       crn=True   control=geometric   Greeks retenus de l'asiatique
    asian       crn=True   control=None        effet du contrôle sur les écarts-types
    asian       crn=False  control=geometric   sans nombres aléatoires communs (5 flux disjoints)
    european    crn=True   (obs = 1)           comparés aux Greeks fermés de BS avec q (slide 61)
    european    crn=False  (obs = 1)
Pour l'européen : bs_* = formules fermées, fd_exact_* = quotients aux différences du prix BS
exact (espérance de l'estimateur, l'écart fd_exact − bs est l'erreur de troncature du slide 60),
*_minus_bs_in_se = (estimation − fermé)/écart-type.

Valeurs écrites en pleine précision (arrondi à 10^-4 dans le rapport).
Usage : .venv/Scripts/python.exe scripts/p4_greeks.py
"""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pricer.black_scholes import bs_price  # noqa: E402
from pricer.greeks import bs_greeks, fd_greeks  # noqa: E402

PARAMS = dict(S0=100.0, sigma=0.20, r=0.03, q=0.01)
T = 1.0
STRIKES = (90.0, 100.0, 110.0)
OPTIONS = ("call", "put")
N_PATHS = 200_000
SEED = 20261117
RNG = "inverse"
H_SPOT, H_VOL = 0.01, 0.01
OUT = ROOT / "results" / "p4_greeks.csv"

VARIANTS = (
    ("asian", True, "geometric", "monthly"),
    ("asian", True, None, "monthly"),
    ("asian", False, "geometric", "monthly"),
    ("european", True, None, 1),
    ("european", False, None, 1),
)
GREEKS = ("delta", "gamma", "vega")

FIELDS = ["kind", "option", "K", "crn", "control", "S0", "sigma", "r", "q", "T", "obs", "n_obs",
          "n_paths", "seed", "seeds", "rng_method", "h_spot", "h_spot_rel", "h_vol",
          "price", "price_se", "delta", "delta_se", "gamma", "gamma_se", "vega", "vega_se",
          "bs_delta", "bs_gamma", "bs_vega", "fd_exact_delta", "fd_exact_gamma", "fd_exact_vega",
          "delta_minus_bs_in_se", "gamma_minus_bs_in_se", "vega_minus_bs_in_se", "time_s"]


def _fd_exact(K, option):
    S0, s, h = PARAMS["S0"], PARAMS["sigma"], H_SPOT * PARAMS["S0"]

    def p(**kw):
        return bs_price(**{**PARAMS, "K": K, "T": T, **kw}, option=option)

    up, mid, dn = p(S0=S0 + h), p(), p(S0=S0 - h)
    return dict(delta=(up - dn) / (2 * h), gamma=(up - 2 * mid + dn) / h**2,
                vega=(p(sigma=s + H_VOL) - p(sigma=s - H_VOL)) / (2 * H_VOL))


def main() -> None:
    t0 = time.perf_counter()
    rows = []
    for option in OPTIONS:
        for K in STRIKES:
            for kind, crn, control, obs in VARIANTS:
                g = fd_greeks(**PARAMS, K=K, T=T, option=option, kind=kind, obs=obs,
                              n_paths=N_PATHS, seed=SEED, rng_method=RNG, h_spot=H_SPOT,
                              h_vol=H_VOL, control=control, crn=crn)
                row = {"kind": kind, "option": option, "K": K, "crn": crn,
                       "control": control or "", **PARAMS, "T": T, "obs": obs,
                       "n_obs": g.n_obs, "n_paths": N_PATHS, "seed": SEED,
                       "seeds": " ".join(str(s) for s in g.seeds), "rng_method": RNG,
                       "h_spot": g.h_spot, "h_spot_rel": g.h_spot_rel, "h_vol": g.h_vol,
                       "price": g.price, "price_se": g.price_se, "time_s": g.elapsed}
                for name in GREEKS:
                    row[name], row[f"{name}_se"] = getattr(g, name), getattr(g, f"{name}_se")
                if kind == "european":
                    bs, quot = bs_greeks(**PARAMS, K=K, T=T, option=option), _fd_exact(K, option)
                    for name in GREEKS:
                        row[f"bs_{name}"], row[f"fd_exact_{name}"] = bs[name], quot[name]
                        row[f"{name}_minus_bs_in_se"] = (row[name] - bs[name]) / row[f"{name}_se"]
                rows.append(row)
                print(f"{option:<4} K={K:>5} {kind:<8} crn={crn!s:<5} {str(control):<9} "
                      f"delta {g.delta:+.5f} ({g.delta_se:.5f})  gamma {g.gamma:.5f} "
                      f"({g.gamma_se:.5f})  vega {g.vega:.4f} ({g.vega_se:.4f})", flush=True)
    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for row in rows:
            w.writerow({k: (repr(v) if isinstance(v, float) else v) for k, v in row.items()})
    print(f"{len(rows)} lignes -> {OUT.relative_to(ROOT)} ({time.perf_counter() - t0:.1f} s)")


if __name__ == "__main__":
    main()
