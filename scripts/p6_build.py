"""P6 : dossier du groupe, texte de l'oral et rapport de 2 pages, écrits depuis des gabarits.

Règle des chiffres : aucun nombre de résultat n'est tapé dans un texte. Chaque texte est un gabarit
à champs {{nom}} ; ce script remplit les champs depuis les CSV de results/ (et, pour les décisions
et les versions, depuis CLAUDE.md et requirements.txt), puis écrit les fichiers :

    docs/templates/DOSSIER_GROUPE.md  →  docs/DOSSIER_GROUPE.md
    docs/templates/ORAL.md            →  docs/ORAL.md
    docs/templates/CONFORMITE.md      →  docs/CONFORMITE.md   (grille de conformité au sujet)
    rapport/rapport_template.html     →  rapport/rapport.html  →  rapport/Rapport_Pricing_Asiatique.pdf

Arrondis : prix à 10^-4 ; écarts-types et demi-largeurs d'IC sous 10^-4 en notation scientifique à
2 chiffres significatifs (pricer.plotstyle.fmt_err) ; gains d'efficacité et temps à l'ordre de
grandeur (og : 2 chiffres significatifs). Un gain d'efficacité dépend d'un temps mesuré : le champ
« _gain_env » est la moyenne des deux mesures faites (results/historique/p3_vr_atm_mesure1.csv, puis
results/p3_vr_atm.csv, machine au repos), arrondie par og.

results/historique/ : deux anciennes versions de CSV, recopiées octet pour octet de l'historique
git (HISTORY ; un test compare les fichiers à `git show`). Elles servent à citer la dispersion entre
deux mesures de temps et le biais mesuré sur 500 runs.

Usage :
    python scripts/p6_build.py            écrit les .md et le .html
    python scripts/p6_build.py --pdf      écrit aussi le PDF (Chrome ou Edge, mode headless)
    python scripts/p6_build.py --list     liste les champs utilisés par document, avec leur source

Aucun calcul de prix, aucun appel réseau, aucune dépendance nouvelle.
"""
from __future__ import annotations

import argparse
import csv
import functools
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pricer.plotstyle import MINUS, NBSP, fmt_err, fmt_int, fmt_num, fmt_pct, sup  # noqa: E402

RESULTS = ROOT / "results"
HISTORY_DIR = RESULTS / "historique"
PDF = ROOT / "rapport" / "Rapport_Pricing_Asiatique.pdf"

DOCUMENTS = {                                   # fichier produit → gabarit
    "docs/DOSSIER_GROUPE.md": "docs/templates/DOSSIER_GROUPE.md",
    "docs/ORAL.md": "docs/templates/ORAL.md",
    "docs/CONFORMITE.md": "docs/templates/CONFORMITE.md",
    "rapport/rapport.html": "rapport/rapport_template.html",
}
INTERNAL = ("docs/DOSSIER_GROUPE.md",)          # document interne au groupe
RENDUS = tuple(out for out in DOCUMENTS if out not in INTERNAL)   # rendus au professeur

HISTORY = [                                     # (fichier de results/historique, commit, chemin)
    ("p3_vr_atm_mesure1.csv", "01dca19", "results/p3_vr_atm.csv"),
    ("p4_beta_bias_500runs.csv", "beb2bb2", "results/p4_beta_bias.csv"),
]

GROUP = ["Zoe HUBERT", "Arthur LOURENCO", "Matthieu DEHNEL", "Pierre DUPLESSIS",
         "Charlotte PONTCHATEAU", "Thomas GALLOIS", "Sacha BEAUQUESNES"]   # Loup, 17/11/2026
LOUP = "[Loup — nom]"                           # nom de famille : à demander à Loup

PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")
DECIMAL = re.compile(r"\d+[.,]\d+")
FORBIDDEN = [                                   # outillage de travail : jamais dans un rendu
    re.compile(r"cowork", re.I), re.compile(r"claude", re.I), re.compile(r"prompt", re.I),
    re.compile(r"\bP[1-6][ab]?\b"), re.compile(r"tranché", re.I),
    re.compile(r"reports/"), re.compile(r"prompts/"),
]

T_TOK = {0.25: "025", 0.5: "05", 1.0: "1", 2.0: "2"}
OPTIONS = ("call", "put")
P3_EST = {"plain": "sans", "antithetic": "anti", "control_beta_1": "ctrl1",
          "control_beta_optimal": "ctrl", "antithetic_control": "antictrl"}
P4_EST = {"plain": "sans", "antithetic": "anti", "control": "ctrl",
          "antithetic_control": "antictrl"}
P1_METHODS = {"inverse_as241": "as241", "inverse_hastings": "hastings", "box_muller": "bm",
              "polar": "polaire", "acceptance_rejection": "rejet"}
RNG_METHODS = {"inverse": "as241", "inverse_hastings": "hastings", "box_muller": "bm",
               "polar": "polaire", "acceptance_rejection": "rejet"}
STRIKES = {"spot": "spot", "forward": "fwd"}
PACKAGES = ("numpy", "scipy", "pandas", "matplotlib", "openpyxl", "pytest")


@dataclass(frozen=True)
class Field:
    name: str
    text: str
    source: str


# --- formats ---------------------------------------------------------------------------------

def og(v: float, sig: int = 2) -> str:
    """Ordre de grandeur : sig chiffres significatifs (1 349,6 → « 1 300 » ; 0,3126 → « 0,31 »)."""
    v = float(v)
    if v == 0:
        return "0"
    exp = math.floor(math.log10(abs(v)))
    r = round(v / 10 ** (exp - sig + 1)) * 10 ** (exp - sig + 1)
    if abs(r) >= 10 ** (exp + 1):               # 9,96 → 10
        exp += 1
    decimals = max(0, sig - 1 - exp)
    return fmt_num(r, decimals) if decimals else fmt_int(r)


def sci(v: float) -> str:
    """Notation scientifique à 2 chiffres significatifs : 4,44e-4 → « 4,4 × 10⁻⁴ »."""
    v = float(v)
    exp = math.floor(math.log10(abs(v)))
    mant = round(v / 10 ** exp, 1)
    if abs(mant) >= 10:
        mant, exp = mant / 10, exp + 1
    return f"{fmt_num(mant, 1)} × 10{sup(exp)}"


def signed(v: float, decimals: int) -> str:
    """Nombre avec son signe : « +1,00 », « −1,45 »."""
    return ("+" if float(v) >= 0 else "") + fmt_num(v, decimals)


def fr_date(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{d}/{m}/{y}"


def plain(v: float) -> str:
    """Nombre court tel qu'écrit dans le CSV, virgule décimale : 0.25 → « 0,25 », 2.0 → « 2 »."""
    return f"{float(v):g}".replace(".", ",").replace("-", MINUS)


def pct_of(decimals: int):
    """Valeur déjà en pour cent dans le CSV : 4.62 → « 4,62 % »."""
    return lambda v: f"{fmt_num(v, decimals)}{NBSP}%"


def frac(decimals: int):
    """Fraction du CSV écrite en pour cent : 0.2 → « 20 % »."""
    return lambda v: fmt_pct(float(v), decimals)


def dec(n: int):
    return lambda v: fmt_num(v, n)


def int_or_one_decimal(v: float) -> str:
    return fmt_int(v) if float(v) >= 10 else fmt_num(v, 1)


def raw_int(v: float) -> str:
    return str(int(float(v)))


P4, P2, P1, P3, P6 = dec(4), dec(2), dec(1), dec(3), dec(6)


# --- lecture des CSV -------------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def _read(path: Path) -> tuple[dict, ...]:
    with path.open(encoding="utf-8", newline="") as f:
        return tuple(csv.DictReader(f))


def table(name: str) -> tuple[dict, ...]:
    return _read(RESULTS / name)


def history(name: str) -> tuple[dict, ...]:
    return _read(HISTORY_DIR / name)


def _match(row: dict, where: dict) -> bool:
    for key, want in where.items():
        have = row[key]
        if isinstance(want, str):
            if have != want:
                return False
        elif have == "" or not math.isclose(float(have), float(want), rel_tol=1e-12, abs_tol=0):
            return False
    return True


def select(rows, **where) -> list[dict]:
    return [r for r in rows if _match(r, where)]


def one(rows, **where) -> dict:
    hits = select(rows, **where)
    if len(hits) != 1:
        raise LookupError(f"{len(hits)} ligne(s) pour {where}")
    return hits[0]


def _where(where: dict) -> str:
    return ", ".join(f"{k} = {v if isinstance(v, str) else plain(v)}" for k, v in where.items())


def _is_number(text: str) -> bool:
    try:
        float(text)
        return True
    except ValueError:
        return False


class _Fields(dict):
    def put(self, name: str, text: str, source: str) -> None:
        if name in self:
            raise ValueError(f"champ en double : {name}")
        self[name] = Field(name, str(text), source)

    def cell(self, name: str, fmt, file: str, col: str, /, rows=None, **where) -> float:
        """Champ = une cellule d'un CSV (ligne unique désignée par where), mise en forme par fmt."""
        row = one(table(file) if rows is None else rows, **where)
        value = row[col]
        self.put(name, fmt(value), f"{file} · {col} · {_where(where)}")
        return float(value) if _is_number(value) else math.nan


def _col(rows, col: str) -> list[float]:
    return [float(r[col]) for r in rows]


# --- les champs ------------------------------------------------------------------------------

def _theoretical(f: _Fields) -> None:
    file, at = "p4_grid_cv.csv", {"K": 100, "T": 1, "option": "call"}
    f.cell("th_S0", fmt_int, file, "S0", **at)
    f.cell("th_K", fmt_int, file, "K", **at)
    f.cell("th_sigma", P2, file, "sigma", **at)
    f.cell("th_sigma_pct", frac(0), file, "sigma", **at)
    f.cell("th_r", P2, file, "r", **at)
    f.cell("th_r_pct", frac(0), file, "r", **at)
    f.cell("th_q", P2, file, "q", **at)
    f.cell("th_q_pct", frac(0), file, "q", **at)
    f.cell("th_N", fmt_int, file, "n_paths", **at)
    f.cell("th_nobs", fmt_int, file, "n_obs", **at)
    f.cell("seed", raw_int, file, "seed", **at)
    for T, tok in T_TOK.items():
        f.cell(f"T{tok}", plain, file, "T", K=100, T=T, option="call")


def _p1(f: _Fields) -> None:
    file = "p1_rng_diagnostics.csv"
    rows = table(file)
    for method, tok in P1_METHODS.items():
        at = {"method": method}
        f.cell(f"p1_{tok}_temps", P3, file, "time_median_s", **at)
        f.cell(f"p1_{tok}_unif", P2, file, "uniforms_per_normal", **at)
        f.cell(f"p1_{tok}_ks", P2, file, "ks_pvalue", **at)
        f.cell(f"p1_{tok}_moy", P4, file, "mean", **at)
        f.cell(f"p1_{tok}_var", P4, file, "variance", **at)
    for tok, method in (("polaire", "polar"), ("rejet", "acceptance_rejection")):
        f.cell(f"p1_{tok}_accept", P4, file, "acceptance_rate", method=method)
        f.cell(f"p1_{tok}_accept_theo", P4, file, "acceptance_theoretical", method=method)
    f.cell("p1_as241_err", sci, file, "phi_inv_max_abs_err_vs_ndtri", method="inverse_as241")
    f.cell("p1_hastings_err", sci, file, "phi_inv_max_abs_err_vs_ndtri", method="inverse_hastings")
    f.cell("p1_N", fmt_int, file, "n", method="inverse_as241")
    f.cell("p1_nruns", fmt_int, file, "n_runs", method="inverse_as241")
    f.put("p1_ks_min", P2(min(_col(rows, "ks_pvalue"))), f"{file} · min de ks_pvalue (5 méthodes)")
    t = {r["method"]: float(r["time_median_s"]) for r in rows}
    f.put("p1_as241_sur_hastings", og(t["inverse_as241"] / t["inverse_hastings"]),
          f"{file} · time_median_s AS241 / Hastings, ordre de grandeur")


def _p2(f: _Fields) -> None:
    file = "p2_grid.csv"
    rows = table(file)
    for opt in OPTIONS:
        for T, tok in T_TOK.items():
            at, p = {"K": 100, "T": T, "option": opt}, f"p2_{opt}_T{tok}"
            f.cell(f"{p}_asiat", P4, file, "asian_price", **at)
            f.cell(f"{p}_se", fmt_err, file, "asian_std_error", **at)
            f.cell(f"{p}_euro", P4, file, "euro_mc_price", **at)
            f.cell(f"{p}_euro_se", fmt_err, file, "euro_mc_std_error", **at)
            f.cell(f"{p}_bs", P4, file, "euro_bs_price", **at)
            f.cell(f"{p}_ecart", lambda v: signed(v, 2), file, "euro_mc_minus_bs_in_se", **at)
            f.cell(f"{p}_ratio", P4, file, "ratio_asian_over_euro_bs", **at)
    f.put("p2_n", fmt_int(len(rows)), f"{file} · nombre de lignes")
    f.cell("p2_N", fmt_int, file, "n_paths", K=100, T=1, option="call")
    f.put("p2_ecart_max", P2(max(abs(v) for v in _col(rows, "euro_mc_minus_bs_in_se"))),
          f"{file} · max de |euro_mc_minus_bs_in_se| (40 lignes)")
    inside = sum(float(r["euro_mc_ci_low"]) <= float(r["euro_bs_price"]) <= float(r["euro_mc_ci_high"])
                 for r in rows)
    f.put("p2_n_dans_ic", fmt_int(inside),
          f"{file} · lignes où euro_bs_price est dans [euro_mc_ci_low ; euro_mc_ci_high]")
    smaller = sum(float(r["asian_std_error"]) < float(r["euro_mc_std_error"]) for r in rows)
    f.put("p2_n_se_plus_petit", fmt_int(smaller),
          f"{file} · lignes où asian_std_error < euro_mc_std_error")


def _p3(f: _Fields) -> None:
    file, old_file = "p3_vr_atm.csv", "historique/p3_vr_atm_mesure1.csv"
    rows, old_rows = table(file), history("p3_vr_atm_mesure1.csv")
    mean_gain = {}
    for opt in OPTIONS:
        for T, tok in T_TOK.items():
            if not select(rows, T=T, option=opt):
                continue
            for est, e in P3_EST.items():
                at, p = {"T": T, "option": opt, "estimator": est}, f"vr_{opt}_T{tok}_{e}"
                row = one(rows, **at)
                f.cell(f"{p}_prix", P4, file, "price", **at)
                f.cell(f"{p}_se", fmt_err, file, "std_error", **at)
                half = (float(row["ci_high"]) - float(row["ci_low"])) / 2
                f.put(f"{p}_demi", fmt_err(half), f"{file} · (ci_high − ci_low)/2 · {_where(at)}")
                f.cell(f"{p}_ratio", P2 if est == "antithetic" else fmt_int, file,
                       "var_ratio_vs_plain", **at)
                now = f.cell(f"{p}_gain", int_or_one_decimal, file, "efficiency_gain_vs_plain", **at)
                before = f.cell(f"{p}_gain1", int_or_one_decimal, old_file,
                                "efficiency_gain_vs_plain", rows=old_rows, **at)
                mean_gain[(T, opt, est)] = (now + before) / 2
                f.put(f"{p}_gain_env", og(mean_gain[(T, opt, est)]),
                      f"{file} et {old_file} · moyenne des deux efficiency_gain_vs_plain, "
                      f"ordre de grandeur · {_where(at)}")
                f.cell(f"{p}_temps", P3, file, "time_median_s", **at)
                if row["beta"]:
                    f.cell(f"{p}_beta", P4, file, "beta", **at)
                    f.cell(f"{p}_corr", P4, file, "corr", **at)
                    f.cell(f"{p}_corr6", P6, file, "corr", **at)
            f.cell(f"vr_{opt}_T{tok}_geo", P4, file, "geometric_closed_form", T=T, option=opt,
                   estimator="control_beta_optimal")
    f.cell("vr_N", fmt_int, file, "n_paths", T=1, option="call", estimator="plain")

    def span(prefix: str, est: str, col: str, fmt) -> None:
        values = _col(select(rows, estimator=est), col)
        f.put(f"{prefix}_min", fmt(min(values)), f"{file} · min de {col} · estimator = {est}")
        f.put(f"{prefix}_max", fmt(max(values)), f"{file} · max de {col} · estimator = {est}")

    span("vr_ctrl_ratio", "control_beta_optimal", "var_ratio_vs_plain", fmt_int)
    span("vr_ctrl1_ratio", "control_beta_1", "var_ratio_vs_plain", fmt_int)
    span("vr_antictrl_ratio", "antithetic_control", "var_ratio_vs_plain", fmt_int)
    span("vr_anti_ratio", "antithetic", "var_ratio_vs_plain", P2)
    span("vr_anti_gain", "antithetic", "efficiency_gain_vs_plain", P1)
    span("vr_beta", "control_beta_optimal", "beta", P4)
    span("vr_corr", "control_beta_optimal", "corr", P4)
    for est, e in (("control_beta_optimal", "ctrl"), ("antithetic_control", "antictrl")):
        means = [g for (_T, _o, x), g in mean_gain.items() if x == est]
        src = (f"{file} et {old_file} · moyenne des deux efficiency_gain_vs_plain, ordre de "
               f"grandeur · estimator = {est}")
        f.put(f"vr_{e}_gain_env_min", og(min(means)), src + " · min")
        f.put(f"vr_{e}_gain_env_max", og(max(means)), src + " · max")
    ratio = [float(one(rows, T=T, option=o, estimator="control_beta_optimal")["var_ratio_vs_plain"])
             / float(one(rows, T=T, option=o, estimator="control_beta_1")["var_ratio_vs_plain"])
             for T in (0.25, 1, 2) for o in OPTIONS]
    src = f"{file} · var_ratio_vs_plain, β optimal / β = 1"
    f.put("vr_opt_sur_un_min", P1(min(ratio)), src + " · min")
    f.put("vr_opt_sur_un_max", P1(max(ratio)), src + " · max")
    rel = [float(r["efficiency_gain_vs_plain"])
           / float(one(old_rows, T=float(r["T"]), option=r["option"],
                       estimator=r["estimator"])["efficiency_gain_vs_plain"]) - 1
           for r in rows if r["estimator"] != "plain"]
    src = f"{file} / {old_file} − 1 sur efficiency_gain_vs_plain (24 lignes hors « sans réduction »)"
    f.put("disp_min", signed(100 * min(rel), 0) + f"{NBSP}%", src + " · min")
    f.put("disp_max", signed(100 * max(rel), 0) + f"{NBSP}%", src + " · max")


def _p4_convergence(f: _Fields) -> None:
    file = "p4_convergence_slopes.csv"
    for est, e in P4_EST.items():
        f.cell(f"pente_{e}", P4, file, "slope", estimator=est)
        f.cell(f"pente_{e}_2", P2, file, "slope", estimator=est)
        f.cell(f"pente_{e}_se", P4, file, "slope_std_error", estimator=est)
    f.cell("pente_theo", P1, file, "expected_slope", estimator="plain")
    f.cell("pente_npoints", fmt_int, file, "n_points", estimator="plain")
    f.cell("conv_N_min", fmt_int, file, "n_min", estimator="plain")
    f.cell("conv_N_max", fmt_int, file, "n_max", estimator="plain")

    file = "p4_convergence.csv"
    for est, e in P4_EST.items():
        f.cell(f"conv_{e}_demi_1e3", fmt_err, file, "half_width_95", estimator=est, n_paths=1000)
        f.cell(f"conv_{e}_demi_1e6", fmt_err, file, "half_width_95", estimator=est, n_paths=1000000)
    at = {"estimator": "plain", "n_paths": 1000}
    f.cell("conv_ref", P4, file, "ref_price", **at)
    f.cell("conv_ref_se", fmt_err, file, "ref_std_error", **at)
    f.cell("conv_ref_N", fmt_int, file, "ref_n_paths", **at)

    file = "p4_n_required.csv"
    n = {}
    for est, e in P4_EST.items():
        for eps, tok in ((0.01, "eps01"), (0.001, "eps001")):
            at = {"estimator": est, "epsilon": eps}
            n[(est, eps)] = f.cell(f"nreq_{e}_{tok}", fmt_int, file, "n_required", **at)
            f.cell(f"nreq_{e}_temps_{tok}", og, file, "time_estimated_s", **at)
        f.cell(f"nreq_{e}_sigma", P4, file, "sigma_hat", estimator=est, epsilon=0.01)
    at = {"estimator": "plain", "epsilon": 0.01}
    f.cell("eps_01", plain, file, "epsilon", **at)
    f.cell("eps_001", plain, file, "epsilon", estimator="plain", epsilon=0.001)
    f.cell("z95", P6, file, "z", **at)
    f.cell("nreq_N_mesure", fmt_int, file, "sigma_hat_n_paths", **at)
    f.put("nreq_sans_sur_ctrl", og(n[("plain", 0.01)] / n[("control", 0.01)]),
          f"{file} · n_required sans réduction / contrôle (ε = 0,01), ordre de grandeur")

    file = "p4_equal_time.csv"
    half = {}
    for budget, b in ((0.5, "05"), (2, "2"), (8, "8")):
        f.cell(f"teq_b{b}", plain, file, "budget_s", estimator="plain", budget_s=budget)
        for est, e in P4_EST.items():
            at = {"estimator": est, "budget_s": budget}
            f.cell(f"teq_{b}_{e}_N", og, file, "n_paths", **at)
            half[(budget, est)] = f.cell(f"teq_{b}_{e}_demi", fmt_err, file, "half_width_95", **at)
    f.put("teq_8_sans_sur_antictrl", og(half[(8, "plain")] / half[(8, "antithetic_control")]),
          f"{file} · half_width_95 sans réduction / antithétique + contrôle (8 s), ordre de grandeur")
    f.put("teq_8_ctrl_sur_antictrl", og(half[(8, "control")] / half[(8, "antithetic_control")]),
          f"{file} · half_width_95 contrôle / antithétique + contrôle (8 s), ordre de grandeur")


def _p4_beta(f: _Fields) -> None:
    file = "p4_beta_bias.csv"
    for mode in ("optimal", "pilot"):
        at = {"beta_mode": mode}
        f.cell(f"biais_{mode}_moy", P4, file, "mean_price", **at)
        f.cell(f"biais_{mode}_biais", lambda v: ("+" if float(v) >= 0 else "") + sci(v), file,
               "bias", **at)
        f.cell(f"biais_{mode}_sd", lambda v: signed(v, 2), file, "bias_in_sd_of_mean", **at)
        f.cell(f"biais_{mode}_couv", frac(1), file, "ci95_coverage", **at)
        f.cell(f"biais_{mode}_beta", P4, file, "mean_beta", **at)
    at = {"beta_mode": "pilot"}
    f.cell("biais_ref", P4, file, "ref_price", **at)
    f.cell("biais_ref_se", fmt_err, file, "ref_std_error", **at)
    f.cell("biais_ref_N", fmt_int, file, "ref_n_paths", **at)
    f.cell("biais_runs", fmt_int, file, "n_seeds", **at)
    f.cell("biais_N", fmt_int, file, "n_paths", **at)
    f.cell("biais_npilot", fmt_int, file, "n_pilot", **at)
    f.cell("biais_scan", fmt_int, file, "stream_states_scanned", **at)
    f.cell("biais_ref_pos", fmt_int, file, "ref_offset_uniforms", **at)
    old_file, old = "historique/p4_beta_bias_500runs.csv", history("p4_beta_bias_500runs.csv")
    f.cell("biais_runs_500", fmt_int, old_file, "n_seeds", rows=old, **at)
    for mode in ("optimal", "pilot"):
        f.cell(f"biais_{mode}_sd_500", lambda v: signed(v, 2), old_file, "bias_in_sd_of_mean",
               rows=old, beta_mode=mode)


def _p4_sensitivities(f: _Fields) -> None:
    file = "p4_rng_methods.csv"
    rows = table(file)
    for method, tok in RNG_METHODS.items():
        at = {"rng_method": method, "control": "geometric"}
        f.cell(f"rng_{tok}_prix", P4, file, "price", **at)
        f.cell(f"rng_{tok}_ecart", lambda v: signed(v, 2), file, "minus_ref_in_se", **at)
        f.cell(f"rng_{tok}_temps", P3, file, "time_median_s", **at)
        f.cell(f"rng_{tok}_unif", P2, file, "uniforms_per_normal", **at)
        at = {"rng_method": method, "control": ""}
        f.cell(f"rng_{tok}_prix_sans", P4, file, "price", **at)
        f.cell(f"rng_{tok}_ecart_sans", lambda v: signed(v, 2), file, "minus_ref_in_se", **at)
    f.put("rng_ecart_max", P2(max(abs(v) for v in _col(rows, "minus_ref_in_se"))),
          f"{file} · max de |minus_ref_in_se| (5 méthodes, avec et sans contrôle)")
    f.cell("rng_se_ctrl", fmt_err, file, "std_error", rng_method="inverse", control="geometric")
    f.cell("rng_se_sans", fmt_err, file, "std_error", rng_method="inverse", control="")
    f.cell("rng_N", fmt_int, file, "n_paths", rng_method="inverse", control="")

    file = "p4_frequency.csv"
    for opt in OPTIONS:
        for n in (1, 4, 12, 52, 252):
            at = {"option": opt, "n_obs": n}
            f.cell(f"freq_{n}_{opt}", P4, file, "price", **at)
            f.cell(f"freq_{n}_{opt}_geo", P4, file, "geometric_exact", **at)
            f.cell(f"freq_{n}_{opt}_ratio", P4, file, "ratio_to_euro_bs", **at)
        f.cell(f"freq_cont_{opt}", P4, file, "geometric_continuous", option=opt, n_obs=12)
        f.cell(f"freq_{opt}_bs", P4, file, "euro_bs_price", option=opt, n_obs=12)

    file = "p4_grid_cv.csv"
    rows = table(file)
    for r in rows:
        K, T, opt = float(r["K"]), float(r["T"]), r["option"]
        at, p = {"K": K, "T": T, "option": opt}, f"{opt}_K{int(K)}_T{T_TOK[T]}"
        f.cell(f"ratio_{p}", P2, file, "ratio", **at)
        if K == 100:
            f.cell(f"ratio_{p}_4", P4, file, "ratio", **at)
            f.cell(f"grid_{opt}_T{T_TOK[T]}_prix", P4, file, "price", **at)
            f.cell(f"grid_{opt}_T{T_TOK[T]}_se", fmt_err, file, "std_error", **at)
            f.cell(f"grid_{opt}_T{T_TOK[T]}_bs", P4, file, "euro_bs_price", **at)
            f.cell(f"grid_{opt}_T{T_TOK[T]}_ratiovar", fmt_int, file, "variance_ratio", **at)
            f.put(f"remise_{opt}_T{T_TOK[T]}", fmt_pct(1 - float(r["ratio"]), 0),
                  f"{file} · 1 − ratio · {_where(at)}")
    at = {"K": 120, "T": 0.25, "option": "put"}
    f.cell("ratio_put_K120_T025_4", P4, file, "ratio", **at)
    f.cell("ratio_put_K120_T025_ic_bas", P4, file, "ratio_ci_low", **at)
    f.cell("ratio_put_K120_T025_ic_haut", P4, file, "ratio_ci_high", **at)
    vr = _col(rows, "variance_ratio")
    f.put("grid_n", fmt_int(len(rows)), f"{file} · nombre de lignes")
    f.put("grid_n_sous", fmt_int(sum(v < 1 for v in _col(rows, "ratio"))),
          f"{file} · lignes où ratio < 1")
    f.put("grid_ratiovar_min", fmt_int(min(vr)), f"{file} · min de variance_ratio (40 cases)")
    f.put("grid_ratiovar_max", fmt_int(max(vr)), f"{file} · max de variance_ratio (40 cases)")
    f.put("grid_div_se_min", fmt_int(math.sqrt(min(vr))), f"{file} · √(min de variance_ratio)")
    f.put("grid_div_se_max", fmt_int(math.sqrt(max(vr))), f"{file} · √(max de variance_ratio)")
    atm = one(rows, K=100, T=1, option="call")
    f.put("grid_se_p2", fmt_err(atm["p2_plain_std_error"]),
          f"{file} · p2_plain_std_error · K = 100, T = 1, option = call")
    f.put("grid_div_se_atm", fmt_int(float(atm["p2_plain_std_error"]) / float(atm["std_error"])),
          f"{file} · p2_plain_std_error / std_error · K = 100, T = 1, option = call")


def _p4_course(f: _Fields) -> None:
    file = "p4_ex77.csv"
    rows = table(file)
    for r in rows:
        opt, K = r["option"], int(float(r["K"]))
        at, p = {"option": opt, "K": K}, f"ex77_{opt}_K{K}"
        f.cell(f"{p}_geo", P4, file, "geometric_exact", **at)
        f.cell(f"{p}_ref", P4, file, "arithmetic_reference", **at)
        f.cell(f"{p}_mc", P4, file, "mc_price", **at)
        f.cell(f"{p}_mc_se", fmt_err, file, "mc_std_error", **at)
        f.cell(f"{p}_cv", P4, file, "cv_price", **at)
        f.cell(f"{p}_cv_se", fmt_err, file, "cv_std_error", **at)
        f.cell(f"{p}_ratiovar", fmt_int, file, "variance_ratio", **at)
    at = {"option": "call", "K": 50}
    for name, col in (("ex77_S0", "S0"), ("ex77_nobs", "n_obs"), ("ex77_N", "n_paths"),
                      ("ex77_ref_N", "ref_n_paths")):
        f.cell(name, fmt_int, file, col, **at)
    f.cell("ex77_T", plain, file, "T", **at)
    f.cell("ex77_sigma_pct", frac(0), file, "sigma", **at)
    f.cell("ex77_r_pct", frac(0), file, "r", **at)
    valued = [v for v in _col(rows, "variance_ratio") if v > 1000]
    f.put("ex77_ratiovar_min", fmt_int(min(valued)),
          f"{file} · min de variance_ratio (cas où l'option a de la valeur : ratio > 1 000)")
    f.put("ex77_ratiovar_max", fmt_int(max(valued)),
          f"{file} · max de variance_ratio (cas où l'option a de la valeur : ratio > 1 000)")
    f.put("ex77_n_values", fmt_int(len(valued)), f"{file} · nombre de cas de ratio > 1 000")

    file78 = "p4_ex78.csv"
    rows78 = table(file78)
    for opt in OPTIONS:
        for K in (90, 100, 110):
            at, p = {"option": opt, "K": K, "n_paths": 100000}, f"ex78_{opt}_K{K}"
            f.cell(f"{p}_exact", P4, file78, "price_exact", **at)
            f.cell(f"{p}_corr", P2, file78, "antithetic_corr", **at)
            f.cell(f"{p}_gainvar", P2, file78, "estimator_var_ratio_mc_over_anti", **at)
    at = {"option": "call", "K": 100, "n_paths": 100000}
    f.cell("ex78_S0", fmt_int, file78, "S0", **at)
    f.cell("ex78_sigma_pct", frac(0), file78, "sigma", **at)
    f.cell("ex78_r_pct", frac(0), file78, "r", **at)
    f.cell("ex78_q_pct", frac(0), file78, "q", **at)
    f.cell("ex78_N", fmt_int, file78, "n_paths", **at)
    gaps = _col(select(rows78, n_paths=100000), "anti_minus_exact_in_se")
    src = f"{file78} · anti_minus_exact_in_se · n_paths = 100000"
    f.put("ex78_anti_ecart_min", signed(min(gaps), 2), src + " · min")
    f.put("ex78_anti_ecart_max", signed(max(gaps), 2), src + " · max")
    cells = ([r[c] for r in rows for c in ("ref_in_mc_ci99", "ref_in_cv_ci99")]
             + [r[c] for r in rows78 for c in ("exact_in_mc_ci99", "exact_in_anti_ci99")])
    src = (f"{file} (ref_in_mc_ci99, ref_in_cv_ci99) et {file78} (exact_in_mc_ci99, "
           "exact_in_anti_ci99)")
    f.put("ex_couv_n", fmt_int(sum(c == "True" for c in cells)), src + " · cases à True")
    f.put("ex_couv_total", fmt_int(len(cells)), src + " · nombre de cases")


def _p4_greeks(f: _Fields) -> None:
    file = "p4_greeks.csv"
    vega = {}
    for opt in OPTIONS:
        asian = {"kind": "asian", "option": opt, "K": 100, "crn": "True", "control": "geometric"}
        euro = {"kind": "european", "option": opt, "K": 100, "crn": "True", "control": ""}
        for greek in ("delta", "gamma", "vega"):
            v = f.cell(f"gk_as_{opt}_{greek}", P4, file, greek, **asian)
            f.cell(f"gk_eu_{opt}_{greek}", P4, file, greek, **euro)
            b = f.cell(f"gk_bs_{opt}_{greek}", P4, file, f"bs_{greek}", **euro)
            if greek == "vega":
                vega[opt] = v / b
        f.cell(f"gk_eu_{opt}_delta_ecart", lambda v: signed(v, 2), file, "delta_minus_bs_in_se",
               **euro)
    f.put("gk_vega_ratio", fmt_pct(vega["call"], 0),
          f"{file} · vega asiatique (CRN, contrôle) / bs_vega · K = 100, option = call")
    base = {"option": "call", "K": 100}
    f.cell("gk_as_delta_se", fmt_err, file, "delta_se", kind="asian", crn="True",
           control="geometric", **base)
    f.cell("gk_as_delta_se_sanscrn", fmt_err, file, "delta_se", kind="asian", crn="False",
           control="geometric", **base)
    f.cell("gk_as_delta_se_sansctrl", fmt_err, file, "delta_se", kind="asian", crn="True",
           control="", **base)
    f.cell("gk_eu_delta_se", fmt_err, file, "delta_se", kind="european", crn="True", control="",
           **base)
    f.cell("gk_eu_delta_se_sanscrn", fmt_err, file, "delta_se", kind="european", crn="False",
           control="", **base)
    f.cell("gk_eu_gamma_sanscrn", P4, file, "gamma", kind="european", crn="False", control="",
           **base)
    f.cell("gk_eu_gamma_se_sanscrn", fmt_err, file, "gamma_se", kind="european", crn="False",
           control="", **base)
    asian = {"kind": "asian", "crn": "True", "control": "geometric", **base}
    f.cell("gk_h_spot", plain, file, "h_spot", **asian)
    f.cell("gk_h_spot_pct", frac(0), file, "h_spot_rel", **asian)
    f.cell("gk_h_vol", plain, file, "h_vol", **asian)
    f.cell("gk_N", fmt_int, file, "n_paths", **asian)


def _p5(f: _Fields) -> None:
    file = "p5_market.csv"
    f.cell("fx_S0", P4, file, "value", name="S0")
    f.cell("fx_S0_date", fr_date, file, "date", name="S0")
    f.cell("fx_sigma", P4, file, "value", name="sigma_ecb")
    f.cell("fx_sigma_pct", frac(2), file, "value", name="sigma_ecb")
    f.cell("fx_sigma_debut", fr_date, file, "date_first", name="sigma_ecb")
    f.cell("fx_sigma_av_pct", frac(2), file, "value", name="sigma_av")
    f.cell("fx_r", P4, file, "value", name="r_usd")
    f.cell("fx_r_pct", frac(2), file, "value", name="r_usd")
    f.cell("fx_r_date", fr_date, file, "date", name="r_usd")
    f.cell("fx_r_annuel", P4, file, "value", name="r_usd_annual_alt")
    f.cell("fx_y_usd", pct_of(2), file, "value", name="y_usd_1y_pct")
    f.cell("fx_q", P4, file, "value", name="q_eur")
    f.cell("fx_q_pct", frac(2), file, "value", name="q_eur")
    f.cell("fx_q_date", fr_date, file, "date", name="q_eur")
    f.cell("fx_F", P4, file, "value", name="forward_1y")
    f.cell("fx_estr", pct_of(2), file, "value", name="estr_pct")
    f.cell("fx_xcheck_n", fmt_int, file, "value", name="xcheck_n_common")
    f.cell("fx_xcheck_moy", P4, file, "value", name="xcheck_mean_diff")
    f.cell("fx_xcheck_abs", P4, file, "value", name="xcheck_mean_abs_diff")
    f.cell("fx_xcheck_max", P4, file, "value", name="xcheck_max_abs_diff")
    f.cell("fx_xcheck_max_date", fr_date, file, "date", name="xcheck_max_abs_diff")

    file = "p5_eurusd.csv"
    rows = table(file)
    for strike, s in STRIKES.items():
        for opt in OPTIONS:
            at, p = {"strike_type": strike, "option": opt}, f"fx_{s}_{opt}"
            row = one(rows, **at)
            f.cell(f"{p}_prix", P4, file, "asian_price", **at)
            f.cell(f"{p}_se", fmt_err, file, "asian_std_error", **at)
            half = (float(row["asian_ci_high"]) - float(row["asian_ci_low"])) / 2
            f.put(f"{p}_demi", fmt_err(half),
                  f"{file} · (asian_ci_high − asian_ci_low)/2 · {_where(at)}")
            f.cell(f"{p}_pct", pct_of(2), file, "asian_pct_S0", **at)
            f.cell(f"{p}_bs", P4, file, "euro_bs_price", **at)
            f.cell(f"{p}_bs_pct", pct_of(2), file, "euro_bs_pct_S0", **at)
            f.cell(f"{p}_ratio", P2, file, "ratio_asian_euro_bs", **at)
            f.cell(f"{p}_ratio_4", P4, file, "ratio_asian_euro_bs", **at)
            f.cell(f"{p}_ratiovar", fmt_int, file, "variance_ratio", **at)
            f.cell(f"{p}_beta", P4, file, "beta", **at)
            f.cell(f"{p}_corr", P4, file, "corr", **at)
            f.cell(f"{p}_euro_ecart", lambda v: signed(v, 2), file, "euro_mc_minus_bs_in_se", **at)
        at = {"strike_type": strike, "option": "call"}
        f.cell(f"fx_{s}_K", P4, file, "K", **at)
        f.cell(f"fx_{s}_prime_usd", fmt_int, file, "hedge_cost_usd", **at)
        f.cell(f"fx_{s}_prime_eur", fmt_int, file, "hedge_cost_eur", **at)
        f.cell(f"fx_{s}_nominal", fmt_int, file, "notional_eur", **at)
        f.cell(f"fx_{s}_pct_recettes", pct_of(2), file, "hedge_cost_pct_receipts", **at)
    at = {"strike_type": "spot", "option": "call"}
    row = one(rows, **at)
    f.cell("fx_usd_mois", fmt_int, file, "usd_per_month", **at)
    f.cell("fx_n_mois", fmt_int, file, "n_months", **at)
    f.cell("fx_N", fmt_int, file, "n_paths", **at)
    f.cell("fx_nobs", fmt_int, file, "n_obs", **at)
    f.put("fx_recettes", fmt_int(float(row["usd_per_month"]) * float(row["n_months"])),
          f"{file} · usd_per_month × n_months")
    ratios = _col(rows, "variance_ratio")
    f.put("fx_ratiovar_min", fmt_int(min(ratios)), f"{file} · min de variance_ratio (4 lignes)")
    f.put("fx_ratiovar_max", fmt_int(max(ratios)), f"{file} · max de variance_ratio (4 lignes)")

    file = "p5_eurusd_sensitivity.csv"
    grid = select(table(file), sigma_label="grille")
    for r in grid:
        sigma, strike, opt = float(r["sigma"]), r["strike_type"], r["option"]
        at = {"sigma": sigma, "strike_type": strike, "option": opt}
        p = f"sens_{round(100 * sigma)}_{STRIKES[strike]}_{opt}"
        f.cell(f"{p}_prix", P4, file, "asian_price", **at)
        f.cell(f"{p}_pct", pct_of(2), file, "asian_pct_S0", **at)
        f.cell(f"{p}_ratio", P4, file, "ratio_asian_euro_bs", **at)
    sigmas = _col(grid, "sigma")
    f.put("sens_sigma_min", fmt_pct(min(sigmas), 0), f"{file} · min de sigma (grille)")
    f.put("sens_sigma_max", fmt_pct(max(sigmas), 0), f"{file} · max de sigma (grille)")


def _conformite(f: _Fields) -> None:
    """Champs propres à la grille de conformité : la grille K × T telle qu'elle est dans le CSV,
    la taille du groupe, le gain des nombres aléatoires communs sur l'écart-type du delta."""
    file = "p4_grid_cv.csv"
    rows = table(file)
    strikes = sorted({float(r["K"]) for r in rows})
    maturities = sorted({float(r["T"]) for r in rows})
    f.put("grid_strikes", ", ".join(fmt_int(k) for k in strikes), f"{file} · valeurs de K")
    f.put("grid_n_strikes", fmt_int(len(strikes)), f"{file} · nombre de valeurs de K")
    f.put("grid_maturites", " ; ".join(plain(t) for t in maturities), f"{file} · valeurs de T")
    f.put("grid_n_maturites", fmt_int(len(maturities)), f"{file} · nombre de valeurs de T")
    f.put("n_membres", fmt_int(len(GROUP) + 1), "p6_build.GROUP (noms donnés par Loup) et Loup")
    file = "p4_greeks.csv"
    at = {"kind": "asian", "option": "call", "K": 100, "control": "geometric"}
    crn = float(one(table(file), crn="True", **at)["delta_se"])
    sans = float(one(table(file), crn="False", **at)["delta_se"])
    f.put("gk_delta_crn_div", og(sans / crn),
          f"{file} · delta_se sans / avec nombres aléatoires communs, ordre de grandeur · "
          f"{_where(at)}")


def _decisions(f: _Fields) -> None:
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    for package in PACKAGES:
        version = re.search(rf"^{package}==(\S+)$", req, re.M).group(1)
        f.put(f"v_{package}", version, f"requirements.txt · {package}==")
    f.put("v_python", re.search(r"\(Python (\d+\.\d+\.\d+)", req).group(1),
          "requirements.txt · commentaire du pip freeze")

    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    f.put("z_cours", re.search(r"au lieu du (\d,\d+) arrondi du cours", claude).group(1),
          "CLAUDE.md · décision P4 (niveau de confiance)")
    f.put("var_50000", re.search(r"variance (\d,\d+) des 50 000 premières", claude).group(1),
          "CLAUDE.md · décision P4, Q3 (slide 78)")
    f.put("date_rendu", re.search(r"\*\*Rendu : ([^.*]+)\.\*\*", claude).group(1),
          "CLAUDE.md · en-tête (date de rendu)")
    f.put("as_formule", re.search(r"Abramowitz-Stegun (\d+\.\d+\.\d+)", claude).group(1),
          "CLAUDE.md · décision P1, Q1 (numéro de la formule d'Abramowitz-Stegun)")

    for i, name in enumerate(GROUP, start=1):
        f.put(f"membre_{i}", name, "noms du groupe donnés par Loup le 17/11/2026 (p6_build.GROUP)")
    f.put("loup", LOUP, "nom de famille à demander à Loup (p6_build.LOUP)")


@functools.lru_cache(maxsize=None)
def fields() -> dict[str, Field]:
    f = _Fields()
    for part in (_theoretical, _p1, _p2, _p3, _p4_convergence, _p4_beta, _p4_sensitivities,
                 _p4_course, _p4_greeks, _p5, _conformite, _decisions):
        part(f)
    return f


# --- gabarits --------------------------------------------------------------------------------

def render(template: str, table_: dict[str, Field]) -> tuple[str, list[str]]:
    """Remplace chaque {{nom}} par le texte du champ ; renvoie (texte, champs utilisés)."""
    used: list[str] = []

    def repl(m: re.Match) -> str:
        name = m.group(1)
        if name not in table_:
            raise KeyError(f"champ inconnu dans le gabarit : {{{{{name}}}}}")
        if name not in used:
            used.append(name)
        return table_[name].text

    return PLACEHOLDER.sub(repl, template), used


def render_all() -> dict[str, tuple[str, list[str]]]:
    table_ = fields()
    return {out: render((ROOT / template).read_text(encoding="utf-8"), table_)
            for out, template in DOCUMENTS.items()}


def build() -> list[Path]:
    written = []
    for out, (text, _used) in render_all().items():
        path = ROOT / out
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        written.append(path)
    return written


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"):
            self._skip += 1
        for key, value in attrs:
            if key in ("alt", "title") and value:
                self.parts.append(value)

    def handle_endtag(self, tag):
        if tag in ("style", "script"):
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def visible_text(text: str, name: str) -> str:
    """Texte lu par le lecteur : tout le fichier pour un .md ; pour un .html, les nœuds de texte
    et les attributs alt / title (ni style, ni script, ni commentaires)."""
    if not str(name).endswith(".html"):
        return text
    parser = _Text()
    parser.feed(text)
    return " ".join(parser.parts)


def decimals(text: str) -> list[str]:
    return DECIMAL.findall(text)


def forbidden_hits(text: str) -> list[str]:
    return [m.group(0) for pattern in FORBIDDEN for m in pattern.finditer(text)]


# --- PDF -------------------------------------------------------------------------------------

def find_browser() -> Path | None:
    """Chrome, sinon Edge, installés sur la machine (aucun téléchargement)."""
    roots = [os.environ.get(k) for k in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
    for relative in ("Google/Chrome/Application/chrome.exe",
                     "Microsoft/Edge/Application/msedge.exe"):
        for root in roots:
            if root and (Path(root) / relative).is_file():
                return Path(root) / relative
    for name in ("chrome", "google-chrome", "chromium", "msedge"):
        if shutil.which(name):
            return Path(shutil.which(name))
    return None


def build_pdf(html: Path = ROOT / "rapport" / "rapport.html", pdf: Path = PDF) -> tuple[Path, Path]:
    """rapport.html → PDF par le navigateur en mode headless (fonds imprimés, sans en-tête ni
    pied de page, profil temporaire, mises à jour et réseau d'arrière-plan coupés)."""
    browser = find_browser()
    if browser is None:
        raise FileNotFoundError("ni Chrome ni Edge trouvés : PDF non produit")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as profile:
        subprocess.run([
            str(browser), "--headless=new", "--disable-gpu", "--no-first-run",
            "--disable-extensions", "--disable-background-networking",
            "--disable-component-update", "--disable-sync", "--disable-default-apps",
            f"--user-data-dir={profile}", "--no-pdf-header-footer",
            f"--print-to-pdf={pdf}", html.resolve().as_uri(),
        ], check=True, capture_output=True, timeout=180)
    if not pdf.is_file():
        raise RuntimeError(f"{browser.name} n'a pas écrit {pdf}")
    return pdf, browser


def pdf_page_count(pdf: Path) -> int:
    """Nombre d'objets « /Type /Page » du fichier (les pages ; « /Pages » n'est pas compté)."""
    return len(re.findall(rb"/Type\s*/Page\b", pdf.read_bytes()))


def find_pdftotext() -> Path | None:
    if shutil.which("pdftotext"):
        return Path(shutil.which("pdftotext"))
    git = shutil.which("git")
    if git:                                     # Git pour Windows fournit pdftotext (mingw64/bin)
        for parent in Path(git).resolve().parents:
            candidate = parent / "mingw64" / "bin" / "pdftotext.exe"
            if candidate.is_file():
                return candidate
    return None


def pdf_text(pdf: Path) -> str:
    tool = find_pdftotext()
    if tool is None:
        raise FileNotFoundError("pdftotext introuvable")
    done = subprocess.run([str(tool), "-enc", "UTF-8", "-layout", str(pdf), "-"], check=True,
                          capture_output=True, timeout=60)
    return done.stdout.decode("utf-8", errors="replace")   # le sujet a des glyphes mathématiques


# --- ligne de commande -----------------------------------------------------------------------

def listing() -> str:
    table_ = fields()
    lines = []
    for out, (_text, used) in render_all().items():
        lines.append(f"## {out} ({len(used)} champs)")
        lines += [f"{{{{{name}}}}} = {table_[name].text}  ←  {table_[name].source}" for name in used]
        lines.append("")
    return "\n".join(lines)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pdf", action="store_true", help="produit aussi le PDF du rapport")
    parser.add_argument("--list", action="store_true", help="liste les champs utilisés")
    parser.add_argument("--all-fields", action="store_true", help="liste tous les champs")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if args.all_fields:
        for field in fields().values():
            print(f"{field.name} = {field.text}  ←  {field.source}")
        return
    if args.list:
        print(listing())
        return
    for path in build():
        print("écrit", path.relative_to(ROOT))
    if args.pdf:
        pdf, browser = build_pdf()
        print(f"écrit {pdf.relative_to(ROOT)} · {pdf_page_count(pdf)} pages · navigateur : {browser}")


if __name__ == "__main__":
    main()
