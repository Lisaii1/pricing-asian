"""Diagnostic des générateurs de normales.

Pour chaque méthode : temps pour 10^6 normales (médiane de 5 runs), moments, test de
Kolmogorov-Smirnov, autocorrélation lag 1, taux d'acceptation, uniformes consommées
-> results/p1_rng_diagnostics.csv
Données de QQ-plot (1 000 quantiles par méthode) -> results/p1_qq.csv

SciPy n'est utilisé ici que comme référence (KS, Φ^{-1} théorique de ndtri) ; aucun tirage
ne vient de SciPy ou NumPy : tout passe par pricer.normals (LCG du cours).

Usage : .venv/Scripts/python.exe scripts/p1_diagnostics.py
"""
from __future__ import annotations

import csv
import math
import platform
import statistics
import sys
import time
from pathlib import Path

import numpy as np
from scipy import special, stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pricer.normals import C_AR, hastings, normals, ppnd16  # noqa: E402
from pricer.rng import PARK_MILLER_A, PARK_MILLER_M  # noqa: E402

N = 1_000_000
SEED = 20261117
N_RUNS = 5
N_QQ = 1_000

CASES = [
    ("inverse_as241", "inverse", {"precision": "as241"}),
    ("inverse_hastings", "inverse", {"precision": "hastings"}),
    ("box_muller", "box_muller", {}),
    ("polar", "polar", {}),
    ("acceptance_rejection", "acceptance_rejection", {}),
]
THEORETICAL_ACCEPTANCE = {"polar": math.pi / 4, "acceptance_rejection": 1 / C_AR}


def phi_inverse_max_error(fn) -> float:
    """Écart absolu max à scipy.special.ndtri sur la plage atteignable par le LCG."""
    u = np.unique(np.concatenate([
        np.linspace(1 / PARK_MILLER_M, 1 - 1 / PARK_MILLER_M, 200_001),
        np.logspace(math.log10(1 / PARK_MILLER_M), -6, 2_000),
        1 - np.logspace(math.log10(1 / PARK_MILLER_M), -6, 2_000),
    ]))
    return float(np.max(np.abs(fn(u) - special.ndtri(u))))


def moments(z: np.ndarray) -> dict:
    m = z.mean()
    c = z - m
    var = float(np.mean(c * c))              # variance empirique (1/N)
    sd = math.sqrt(var)
    return {
        "mean": float(m),
        "variance": var,
        "skewness": float(np.mean(c**3) / sd**3),
        "excess_kurtosis": float(np.mean(c**4) / var**2 - 3.0),
    }


def main() -> None:
    results_dir = ROOT / "results"
    results_dir.mkdir(exist_ok=True)
    rows, qq_rows = [], []
    p_qq = (np.arange(1, N_QQ + 1) - 0.5) / N_QQ
    q_theo = special.ndtri(p_qq)

    for label, method, opts in CASES:
        times, sample = [], None
        for _ in range(N_RUNS):
            t0 = time.perf_counter()
            s = normals(N, method, SEED, **opts)
            times.append(time.perf_counter() - t0)
            if sample is None:
                sample = s
            else:  # même seed : même échantillon à chaque run
                assert s.z.tobytes() == sample.z.tobytes()
        z = sample.z
        ks = stats.kstest(z, "norm")
        row = {
            "method": label,
            "n": N,
            "seed": SEED,
            "lcg": f"a={PARK_MILLER_A},m={PARK_MILLER_M},c=0",
            "time_median_s": statistics.median(times),
            "time_min_s": min(times),
            "time_max_s": max(times),
            "n_runs": N_RUNS,
            **moments(z),
            "ks_statistic": float(ks.statistic),
            "ks_pvalue": float(ks.pvalue),
            "lag1_autocorr": float(np.corrcoef(z[:-1], z[1:])[0, 1]),
            "n_uniforms": sample.n_uniforms,
            "uniforms_per_normal": sample.n_uniforms / N,
            "n_candidates": sample.n_candidates if sample.n_candidates is not None else "",
            "acceptance_rate": sample.acceptance_rate if sample.acceptance_rate is not None else "",
            "acceptance_theoretical": THEORETICAL_ACCEPTANCE.get(method, ""),
            "phi_inv_max_abs_err_vs_ndtri": (
                phi_inverse_max_error(ppnd16 if opts.get("precision") == "as241" else hastings)
                if method == "inverse" else ""
            ),
        }
        rows.append(row)

        q_emp = np.quantile(z, p_qq)
        for i in range(N_QQ):
            qq_rows.append({"method": label, "i": i + 1, "p": p_qq[i],
                            "q_theoretical": q_theo[i], "q_empirical": q_emp[i]})
        print(f"{label:22s} t_med={row['time_median_s']:.4f}s  mean={row['mean']:+.5f}  "
              f"var={row['variance']:.5f}  KS p={row['ks_pvalue']:.4f}  "
              f"acc={row['acceptance_rate']}")

    with open(results_dir / "p1_rng_diagnostics.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(results_dir / "p1_qq.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(qq_rows[0]))
        w.writeheader()
        w.writerows(qq_rows)
    print(f"Python {platform.python_version()}, NumPy {np.__version__}, {platform.platform()}")
    print("écrit : results/p1_rng_diagnostics.csv, results/p1_qq.csv")


if __name__ == "__main__":
    main()
