"""Figures du rapport (P5b, étapes 2 et 3) → results/figures/<nom>.png (300 dpi) et .pdf (vectoriel).

Style Plasma de la maquette validée (pricer.plotstyle). Chaque nombre vient d'un CSV de results/ ou
d'un calcul du pricer fait ici ; aucune valeur n'est tapée (test : tests/test_p5_figures.py).
Dimensions en pixels de la maquette A4 (794 px de large, marges de 42 px, gouttière de 30 px) :
pleine largeur 710 px, demi-colonne 340 px ; figure 1 : 534 × 300 px (à côté du rail de chiffres).
Sur la figure : chiffres et source courte ; la méthode va dans la légende du rapport.

fig1_eventail_eurusd   paramètres de results/p5_market.csv (S0 = fixing BCE, σ historique BCE,
                       r = Trésor 1 an semestriel, q = BCE AAA 1 an) ; 200 trajectoires
                       quotidiennes affichées (pricer.paths, seed de p5_eurusd.csv), couleur selon
                       S_T ; trajectoire de S_T médian en blanc avec ses 12 points de moyenne ;
                       histogrammes de S_T et de A sur les N trajectoires mensuelles du pricer
                       (N, seed et grille de results/p5_eurusd.csv), pas sur les 200 affichées.
fig2_disques_ratio     results/p4_grid_cv.csv : ratio asiatique / européen BS, call et put,
                       K × T ; rayon du disque = remise 1 − ratio (ratio > 1 compté 1).
fig3_gain_efficacite   results/p3_vr_atm.csv : gain d'efficacité / sans réduction, par méthode ;
                       point plein = call, anneau = put, taille selon T.
fig4_convergence       results/p4_convergence.csv : demi-largeur d'IC à 95 % mesurée contre N
                       (log-log), 4 estimateurs, droite ajustée de p4_convergence_slopes.csv
                       (ln demi-largeur = intercept + pente·ln N), ligne ±ε (plus grand ε de
                       p4_n_required.csv). Couleur = contrôle ou non, anneau = antithétique.
fig5_nuage_payoffs     2 000 trajectoires mensuelles du pricer (paramètres, K, T = 1 et seed de la
                       ligne call T = 1 de p3_vr_atm.csv) : payoff actualisé arithmétique contre
                       géométrique ; corrélation calculée ici, celle de P3 (N = 200 000) rappelée.
fig6_eurusd_sigma      results/p5_eurusd_sensitivity.csv, K = S0 : prix asiatique (MC) et européen
                       (BS) en % de S0 contre σ de 4 % à 8 %, call et put ; σ mesuré marqué.
tab1_estimateurs       results/p3_vr_atm.csv, T = 1 : 5 estimateurs, call et put, prix, demi-IC
                       à 95 % ((ci_high − ci_low)/2), gain d'efficacité ; meilleur gain call surligné.
tab2_eurusd            results/p5_eurusd.csv : K = S0 et K = forward, call et put, prix
                       asiatique, demi-IC, européen BS, ratio, ratio de variance du contrôle.

Usage : .venv/Scripts/python.exe scripts/p5_figures.py [nom …]
"""
from __future__ import annotations

import csv
import math
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import numpy as np  # noqa: E402
from matplotlib import patheffects  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Circle, Rectangle  # noqa: E402
from matplotlib.ticker import FixedLocator, FuncFormatter  # noqa: E402

from pricer import plotstyle as ps  # noqa: E402
from pricer.paths import FREQUENCIES, gbm_paths  # noqa: E402

RESULTS = ROOT / "results"
FIG_DIR = RESULTS / "figures"
P = ps.PALETTE

# Mise en page (pixels de la maquette A4)
PAGE_PX, PAD_PX, GAP_PX = 794, 42, 30
FULL_PX = PAGE_PX - 2 * PAD_PX                 # 710
COL_PX = (FULL_PX - GAP_PX) // 2               # 340
FIG1_PX = (534, 300)
HIST_X = 0.76               # bord gauche des histogrammes de la figure 1 (fraction)
Q_TAIL = 1e-3              # quantiles de S(T) qui bornent l'axe de la figure 1

# Choix d'affichage fixés par le prompt P5b (pas des résultats)
N_FAN_SHOWN = 200          # trajectoires dessinées dans l'éventail
N_SCATTER = 2_000          # trajectoires du nuage de la figure 5

ESTIMATOR_NAMES = {
    "plain": "Sans réduction",
    "antithetic": "Antithétique",
    "control_beta_1": "Contrôle β = 1",
    "control_beta_optimal": "Contrôle β optimal",
    "antithetic_control": "Antithétique + contrôle",
}


# --- lecture -------------------------------------------------------------------------------------

def _rows(name: str) -> list[dict]:
    with (RESULTS / name).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _market() -> dict:
    return {r["name"]: r for r in _rows("p5_market.csv")}


def _fr_date(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%d/%m/%Y")


def _fr_T(T: float) -> str:
    return f"{T:g}".replace(".", ",")


def _glows(fig, *spots) -> None:
    """Lueurs de la maquette : (cx, cy, couleur, opacité), taille relative fixe."""
    ps.add_glows(fig, [(cx, cy, 0.32, 0.38, c, a) for cx, cy, c, a in spots])


# --- figure 1 : éventail EUR/USD -----------------------------------------------------------------

def fan_data() -> dict:
    """Paramètres calibrés, trajectoires affichées et (S_T, A) des N trajectoires du pricer."""
    m = _market()
    S0, sigma, r, q = (float(m[k]["value"]) for k in ("S0", "sigma_ecb", "r_usd", "q_eur"))
    case = _rows("p5_eurusd.csv")[0]
    T, obs, n_paths, seed = float(case["T"]), case["obs"], int(case["n_paths"]), int(case["seed"])
    n_obs = int(case["n_obs"])
    shown = np.concatenate(list(gbm_paths(S0, sigma, r, T, q, obs="daily", n_paths=N_FAN_SHOWN,
                                          seed=seed, include_s0=True)))
    n_days = shown.shape[1] - 1
    if n_days != FREQUENCIES["daily"] * T or n_days % n_obs:
        raise RuntimeError("grille quotidienne non compatible avec les dates mensuelles")
    monthly_idx = (n_days // n_obs) * np.arange(1, n_obs + 1)
    final = shown[:, -1]
    highlight = int(np.argsort(final)[final.size // 2])        # S_T médian des trajectoires vues
    ST, A = [], []
    for blk in gbm_paths(S0, sigma, r, T, q, obs=obs, n_paths=n_paths, seed=seed):
        ST.append(blk[:, -1])
        A.append(blk.mean(axis=1))                             # moyenne des n_obs fixings
    return dict(S0=S0, sigma=sigma, r=r, q=q, T=T, S0_date=m["S0"]["date"], n_paths=n_paths,
                seed=seed, n_obs=n_obs, shown=shown, monthly_idx=monthly_idx,
                highlight=highlight, ST=np.concatenate(ST), A=np.concatenate(A))


def fig1_fan(d: dict | None = None):
    d = fan_data() if d is None else d
    fig = ps.new_figure(*FIG1_PX)
    _glows(fig, (0.05, 0.95, "a2", 0.35), (0.95, 0.3, "a1", 0.16))
    ax = fig.add_axes((0.085, 0.13, 0.64, 0.72))
    axh = fig.add_axes((HIST_X, 0.13, 0.22, 0.72), sharey=ax)
    shown, idx, n_obs = d["shown"], d["monthly_idx"], d["n_obs"]
    n_days = shown.shape[1] - 1
    months = np.arange(n_days + 1) * n_obs / n_days
    ST, A = d["ST"], d["A"]
    lo = min(shown.min(), np.quantile(ST, Q_TAIL))
    hi = max(shown.max(), np.quantile(ST, 1 - Q_TAIL))

    final = shown[:, -1]
    u = (final - final.min()) / (final.max() - final.min())
    order = np.argsort(np.abs(u - 0.5))                        # trajectoires extrêmes au-dessus
    colors = [(*ps.hex_rgb(P["a1"] if u[i] > 0.5 else P["a2"]), 0.12 + 0.5 * abs(u[i] - 0.5))
              for i in order]
    segs = [np.column_stack((months, shown[i])) for i in order]
    ax.add_collection(LineCollection(segs, colors=colors, linewidths=0.6, zorder=2))
    ex = shown[d["highlight"]]
    ax.plot(months, ex, color=P["a3"], lw=3.2, alpha=0.18, zorder=3)
    ax.plot(months, ex, color="white", lw=1.0, zorder=4)
    ax.scatter(months[idx], ex[idx], s=34, color=P["a3"], alpha=0.25, lw=0, zorder=5)
    ax.scatter(months[idx], ex[idx], s=9, color=P["a3"], lw=0, zorder=6)
    ax.set_xlim(0, n_obs)
    ax.set_ylim(lo, hi)
    ax.xaxis.set_major_locator(FixedLocator(np.arange(0, n_obs + 1, n_obs // 4)))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: ps.fmt_num(v, 2)))
    ax.set_xlabel("mois", color=P["mut"], labelpad=2)
    ps.style_axes(ax)

    bins = np.linspace(lo, hi, 41)
    centers, width = (bins[:-1] + bins[1:]) / 2, bins[1] - bins[0]
    hS, _ = np.histogram(ST, bins, density=True)
    hA, _ = np.histogram(A, bins, density=True)
    axh.hlines(centers - 0.2 * width, 0, hS, color=P["a2"], lw=1.4, alpha=0.75)
    axh.hlines(centers + 0.2 * width, 0, hA, color=P["a3"], lw=1.4)
    axh.set_xlim(0, max(hS.max(), hA.max()) * 1.1)
    ps.style_axes(axh, grid="y")
    axh.tick_params(labelleft=False, labelbottom=False)
    axh.legend(handles=[Line2D([], [], color=P["a2"], lw=1.6), Line2D([], [], color=P["a3"], lw=1.6)],
               labels=["S(T)", "moyenne A"], loc="upper right", labelcolor=P["ink"],
               handlelength=1.2, borderaxespad=0)

    mono = dict(fontfamily=ps.FONT_MONO, fontsize=6.5)
    fig.text(0.085, 0.93, f"EUR/USD · S0 = {ps.fmt_num(d['S0'], 4)} ({_fr_date(d['S0_date'])}) · "
             f"σ = {ps.fmt_pct(d['sigma'], 2)} · r = {ps.fmt_pct(d['r'], 2)} · "
             f"q = {ps.fmt_pct(d['q'], 2)} · T = {_fr_T(d['T'])} an",
             color=P["sub"], **mono)
    fig.text(HIST_X, 0.035, f"écart-type\nS(T) {ps.fmt_num(ST.std(ddof=1), 4)}\n"
             f"A    {ps.fmt_num(A.std(ddof=1), 4)}", color=P["ink"], va="bottom", **mono)
    fig.text(HIST_X, 0.89, f"N = {ps.fmt_int(d['n_paths'])}", color=P["sub"], **mono)
    ps.source(fig, f"BCE, Trésor US · p5_market.csv · pricer, seed {d['seed']}", x=0.01,
              ha="left")
    return fig


# --- figure 2 : disques asiatique / européen -----------------------------------------------------

def fig2_disks():
    rows = _rows("p4_grid_cv.csv")
    Ks = sorted({float(r["K"]) for r in rows})
    Ts = sorted({float(r["T"]) for r in rows})
    fig = ps.new_figure(FULL_PX, 270)
    _glows(fig, (0.15, 0.1, "a2", 0.3), (0.85, 0.9, "a1", 0.14))
    r_max, r_min, n_ring = 0.44, 0.07, 14
    a1, a2 = np.array(ps.hex_rgb(P["a1"])), np.array(ps.hex_rgb(P["a2"]))
    stroke = [patheffects.withStroke(linewidth=2.2, foreground=P["bg"])]
    for k, option in enumerate(("call", "put")):
        ax = fig.add_axes((0.07 + 0.5 * k, 0.09, 0.42, 0.76))
        ax.set_xlim(-0.5, len(Ks) - 0.5)
        ax.set_ylim(len(Ts) - 0.5, -0.5)
        ax.set_aspect("equal")
        ax.set_axis_off()
        for i, K in enumerate(Ks):
            ax.text(i, -0.62, f"K {ps.fmt_num(K, 0)}", ha="center", va="bottom", color=P["mut"],
                    fontfamily=ps.FONT_MONO, fontsize=6.5)
        for j, T in enumerate(Ts):
            ax.text(-0.62, j, f"T {_fr_T(T)}", ha="right", va="center", color=P["mut"],
                    fontfamily=ps.FONT_MONO, fontsize=6.5)
        for r in (x for x in rows if x["option"] == option):
            i, j, ratio = Ks.index(float(r["K"])), Ts.index(float(r["T"])), float(r["ratio"])
            rad = r_min + (r_max - r_min) * (1 - min(ratio, 1.0))
            ax.add_patch(Circle((i, j), r_max, fill=False, ec=ps.HAIR, lw=0.6))
            for g, a in ((1.5, 0.05), (1.3, 0.09)):
                ax.add_patch(Circle((i, j), rad * g, color=P["a1"], alpha=a, lw=0))
            for n in range(n_ring, 0, -1):                     # dégradé radial a1 (centre) → a2
                t = n / n_ring
                ax.add_patch(Circle((i, j), rad * t, color=(1 - t) * a1 + t * a2, alpha=0.9, lw=0))
            ax.text(i, j, ps.fmt_num(ratio, 2), ha="center", va="center", color="white",
                    fontfamily=ps.FONT_MONO, fontsize=7, fontweight="bold", path_effects=stroke)
        fig.text(0.07 + 0.5 * k, 0.94, option, color=P["ink"], fontsize=8.5, fontweight="bold")
    first = rows[0]
    fig.text(0.07, 0.015, "ratio asiatique / européen (Black-Scholes) · taille = remise",
             color=P["sub"], fontsize=6.5)
    ps.source(fig, f"p4_grid_cv.csv · S0 = {ps.fmt_num(float(first['S0']), 0)} · "
                   f"σ = {ps.fmt_pct(float(first['sigma']), 0)} · N = {ps.fmt_int(first['n_paths'])}"
                   f" · contrôle géométrique")
    return fig


# --- figure 3 : gain d'efficacité ------------------------------------------------------------------

def fig3_efficiency():
    rows = _rows("p3_vr_atm.csv")
    gains = {}
    for r in rows:
        gains.setdefault(r["estimator"], []).append(
            (float(r["T"]), r["option"], float(r["efficiency_gain_vs_plain"])))
    order = sorted(gains, key=lambda e: max(g for *_, g in gains[e]))
    Ts = sorted({T for v in gains.values() for T, *_ in v})
    size_px = dict(zip(Ts, (2.5, 4.0, 5.5)))                  # rayon (px) selon T, maquette
    area = {T: (2 * 0.75 * rad) ** 2 for T, rad in size_px.items()}   # px → pt, s = diamètre²
    all_g = [g for v in gains.values() for *_, g in v]
    x_lo, x_hi = 10 ** math.floor(math.log10(min(all_g))), 10 ** math.ceil(math.log10(max(all_g)))

    fig = ps.new_figure(COL_PX, 260)
    _glows(fig, (0.9, 0.85, "a1", 0.2), (0.1, 0.1, "a2", 0.28))
    ax = fig.add_axes((0.37, 0.25, 0.46, 0.69))
    ax.set_xscale("log")
    ax.set_xlim(x_lo, x_hi)
    ax.set_ylim(len(order) - 0.5, -0.5)
    decades = [10 ** k for k in range(round(math.log10(x_lo)), round(math.log10(x_hi)) + 1)]
    ax.xaxis.set_major_locator(FixedLocator(decades))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"×{ps.fmt_int(v)}"))
    ax.xaxis.set_minor_locator(FixedLocator([]))
    ps.style_axes(ax, grid="x")
    ax.set_yticks(range(len(order)), [ESTIMATOR_NAMES[e] for e in order])
    ax.tick_params(axis="y", pad=10)                           # marqueurs à ×1 sur le bord
    for lab in ax.get_yticklabels():
        lab.set_fontfamily(ps.FONT_SANS)
        lab.set_color(P["sub"])
        lab.set_fontsize(7)
    a2 = ps.hex_rgb(P["a2"])
    for y, est in enumerate(order):
        top = max(g for *_, g in gains[est])
        xs = np.geomspace(x_lo, max(top, x_lo * 1.1), 41)
        segs = [((xs[i], y), (xs[i + 1], y)) for i in range(len(xs) - 1)]
        alphas = np.linspace(0, 0.6, len(segs))
        ax.add_collection(LineCollection(segs, colors=[(*a2, a) for a in alphas], linewidths=2))
        for T, option, g in gains[est]:
            if option == "put":
                ax.scatter(g, y, s=area[T] * 1.9, facecolors="none", edgecolors=P["a2"],
                           linewidths=1.1, zorder=4, clip_on=False)
            else:
                ax.scatter(g, y, s=area[T] * 3, color=P["a1"], alpha=0.18, lw=0, zorder=4,
                           clip_on=False)
                ax.scatter(g, y, s=area[T], color=P["a1"], lw=0, zorder=5, clip_on=False)
        ax.annotate(f"×{ps.fmt_int(top)}", (top, y), xytext=(10, 0), textcoords="offset points",
                    va="center", color=P["ink"], fontfamily=ps.FONT_MONO, fontsize=7,
                    annotation_clip=False)
    handles = [Line2D([], [], ls="", marker="o", color=P["a1"], ms=4.5),
               Line2D([], [], ls="", marker="o", mfc="none", mec=P["a2"], ms=5)]
    labels = ["call", "put"]
    for T in Ts:
        handles.append(Line2D([], [], ls="", marker="o", color=P["mut"], ms=size_px[T] * 1.5))
        labels.append(f"T {_fr_T(T)}")
    ax.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.32, -0.11), ncol=5,
              labelcolor=P["sub"], handletextpad=0.2, columnspacing=0.9, borderaxespad=0)
    first = rows[0]
    ps.source(fig, f"p3_vr_atm.csv · K = {ps.fmt_num(float(first['K']), 0)} · "
                   f"N = {ps.fmt_int(first['n_paths'])}")
    return fig


# --- figure 4 : convergence mesurée -------------------------------------------------------------

CONV_STYLE = {          # couleur = famille (contrôle ou non), anneau = antithétique
    "plain": ("a2", True, "-"),
    "antithetic": ("a2", False, "--"),
    "control": ("a1", True, "-"),
    "antithetic_control": ("a1", False, "--"),
}
CONV_NAMES = {"plain": "sans réduction", "antithetic": "antithétique", "control": "contrôle",
              "antithetic_control": "anti + contrôle"}


def fig4_convergence():
    conv, slopes = _rows("p4_convergence.csv"), _rows("p4_convergence_slopes.csv")
    eps = max(float(r["epsilon"]) for r in _rows("p4_n_required.csv"))
    fig = ps.new_figure(COL_PX, 270)
    _glows(fig, (0.95, 0.9, "a1", 0.2), (0.05, 0.2, "a2", 0.3))
    ax = fig.add_axes((0.15, 0.33, 0.8, 0.62))
    ax.set_xscale("log")
    ax.set_yscale("log")
    handles, labels = [], []
    for s in slopes:
        est = s["estimator"]
        color, filled, ls = CONV_STYLE[est]
        pts = np.array([(float(r["n_paths"]), float(r["half_width_95"]))
                        for r in conv if r["estimator"] == est])
        x = np.geomspace(pts[:, 0].min(), pts[:, 0].max(), 50)
        ax.plot(x, np.exp(float(s["intercept"])) * x ** float(s["slope"]), color=P[color],
                lw=1.1, ls=ls, alpha=0.75, gid=f"fit:{est}")
        ax.scatter(pts[:, 0], pts[:, 1], s=14, lw=1.0, zorder=4, gid=f"points:{est}",
                   facecolors=P[color] if filled else P["bg"], edgecolors=P[color])
        handles.append(Line2D([], [], color=P[color], ls=ls, lw=1.1, marker="o", ms=3.6,
                              mfc=P[color] if filled else P["bg"], mec=P[color]))
        labels.append(f"{CONV_NAMES[est]} · pente {ps.fmt_num(float(s['slope']), 2)}")
    ax.axhline(eps, color=P["a3"], ls=(0, (4, 4)), lw=0.9, alpha=0.8)
    ax.annotate(f"±{ps.fmt_num(eps, 2)}", (1, eps), xycoords=("axes fraction", "data"),
                xytext=(0, -3), textcoords="offset points", ha="right", va="top",
                color=P["a3"], fontfamily=ps.FONT_MONO, fontsize=6.5)
    ns = sorted({float(r["n_paths"]) for r in conv})
    ax.xaxis.set_major_locator(FixedLocator(
        [10 ** k for k in range(math.ceil(math.log10(ns[0])), math.floor(math.log10(ns[-1])) + 1)]))
    ax.xaxis.set_minor_locator(FixedLocator([]))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"10{ps.sup(round(math.log10(v)))}"))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: ps.fmt_sig(v)))
    ax.yaxis.set_minor_formatter(FuncFormatter(lambda v, _: ""))
    ax.set_xlabel("N (trajectoires)", color=P["mut"], labelpad=2)
    ps.style_axes(ax)
    ax.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.45, -0.17), ncol=2,
              labelcolor=P["sub"], fontsize=6.5, handlelength=2.2, columnspacing=1.0,
              borderaxespad=0)
    first = conv[0]
    ps.source(fig, f"p4_convergence.csv · call K = {ps.fmt_num(float(first['K']), 0)}, "
                   f"T = {_fr_T(float(first['T']))} · demi-largeur de l'IC à 95 %")
    return fig


# --- figure 5 : nuage payoff arithmétique / géométrique ------------------------------------------

def scatter_data() -> dict:
    """N_SCATTER trajectoires du pricer, paramètres de la ligne call T = 1 de p3_vr_atm.csv."""
    row = next(r for r in _rows("p3_vr_atm.csv") if r["option"] == "call"
               and r["estimator"] == "control_beta_optimal" and float(r["T"]) == 1)
    S0, K, sigma, r, q, T = (float(row[k]) for k in ("S0", "K", "sigma", "r", "q", "T"))
    paths = np.concatenate(list(gbm_paths(S0, sigma, r, T, q, obs=row["obs"], n_paths=N_SCATTER,
                                          seed=int(row["seed"]))))
    disc = math.exp(-r * T)
    arith = disc * np.maximum(paths.mean(axis=1) - K, 0.0)
    geo = disc * np.maximum(np.exp(np.log(paths).mean(axis=1)) - K, 0.0)
    return dict(S0=S0, K=K, sigma=sigma, r=r, q=q, T=T, seed=int(row["seed"]), n=N_SCATTER,
                arith=arith, geo=geo, corr=float(np.corrcoef(arith, geo)[0, 1]),
                corr_p3=float(row["corr"]), n_p3=int(row["n_paths"]))


def fig5_scatter(d: dict | None = None):
    d = scatter_data() if d is None else d
    fig = ps.new_figure(COL_PX, 240)
    _glows(fig, (0.85, 0.85, "a1", 0.18), (0.1, 0.15, "a2", 0.3))
    ax = fig.add_axes((0.12, 0.17, 0.84, 0.63))
    top = max(d["arith"].max(), d["geo"].max())
    ax.plot([0, top], [0, top], color=P["mut"], lw=0.8, ls=(0, (4, 4)))
    cols = [P["a1"] if v > top / 2 else P["a2"] for v in d["arith"]]
    ax.scatter(d["geo"], d["arith"], s=4, c=cols, alpha=0.6, lw=0, zorder=3)
    ax.set_xlim(0, top)
    ax.set_ylim(0, top)
    ax.set_xlabel("payoff géométrique", color=P["mut"], labelpad=2)
    ax.set_ylabel("payoff arithmétique", color=P["mut"], labelpad=2)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: ps.fmt_num(v, 0)))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: ps.fmt_num(v, 0)))
    ps.style_axes(ax)
    mono = dict(fontfamily=ps.FONT_MONO)
    fig.text(0.12, 0.9, f"corrélation {ps.fmt_num(d['corr'], 4)}", color=P["ink"], fontsize=9,
             **mono)
    fig.text(0.12, 0.84, f"N = {ps.fmt_int(d['n'])} · P3 avec N = {ps.fmt_int(d['n_p3'])} : "
             f"{ps.fmt_num(d['corr_p3'], 4)}", color=P["sub"], fontsize=6.5, **mono)
    ps.source(fig, f"pricer, seed {d['seed']} · S0 = K = {ps.fmt_num(d['K'], 0)}, "
                   f"T = {_fr_T(d['T'])}, mensuel")
    return fig


# --- figure 6 : cas réel, prix contre σ ----------------------------------------------------------

def fig6_eurusd_sigma():
    rows = [r for r in _rows("p5_eurusd_sensitivity.csv") if r["strike_type"] == "spot"]
    measured = {r["option"]: r for r in rows if r["sigma_label"] == "mesuré"}
    s_meas = float(next(iter(measured.values()))["sigma"])
    fig = ps.new_figure(COL_PX, 260)
    _glows(fig, (0.9, 0.9, "a1", 0.2), (0.1, 0.1, "a2", 0.3))
    ax = fig.add_axes((0.13, 0.15, 0.6, 0.72))
    ax.axvline(100 * s_meas, color=P["a3"], lw=0.8, ls=(0, (2, 3)), alpha=0.8)
    style = {("asian", "call"): ("a1", "-"), ("euro", "call"): ("a2", "-"),
             ("asian", "put"): ("a1", "--"), ("euro", "put"): ("a2", "--")}
    names = {"asian": "asiatique", "euro": "européen BS"}
    ends = []                                   # étiquettes directes en bout de courbe
    for (kind, option), (color, ls) in style.items():
        sub = sorted((r for r in rows if r["option"] == option), key=lambda r: float(r["sigma"]))
        col = "asian_pct_S0" if kind == "asian" else "euro_bs_pct_S0"
        x = [100 * float(r["sigma"]) for r in sub]
        y = [float(r[col]) for r in sub]
        ax.plot(x, y, color=P[color], ls=ls, lw=1.3, marker="o", ms=2.6, gid=f"{kind}:{option}")
        ym = float(measured[option][col])
        ax.scatter([100 * s_meas], [ym], s=22, color=P["a3"], lw=0, zorder=5)
        ends.append([y[-1], x[-1], f"{names[kind]} {option}"])
        if kind == "asian":
            ax.annotate(ps.fmt_num(ym, 2), (100 * s_meas, ym), xytext=(-4, 5),
                        textcoords="offset points", ha="right", color=P["ink"],
                        fontfamily=ps.FONT_MONO, fontsize=6.5)
    lo, hi = ax.get_ylim()
    gap = (hi - lo) / 16                        # écart minimal entre deux étiquettes
    ends.sort()
    for k in range(1, len(ends)):
        ends[k][0] = max(ends[k][0], ends[k - 1][0] + gap)
    for y_lab, x_end, text in ends:
        ax.annotate(text, (x_end, y_lab), xytext=(6, 0), textcoords="offset points",
                    va="center", color=P["sub"], fontsize=6.5, annotation_clip=False)
    ax.set_xlabel("σ (%)", color=P["mut"], labelpad=2)
    ax.set_ylabel("prix (% de S0)", color=P["mut"], labelpad=2)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: ps.fmt_num(v, 0)))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: ps.fmt_num(v, 1)))
    ps.style_axes(ax)
    m = measured["call"]
    fig.text(0.13, 0.92, f"σ mesuré {ps.fmt_pct(s_meas, 2)} · K = S0 = "
             f"{ps.fmt_num(float(m['S0']), 4)} · T = {_fr_T(float(m['T']))} an",
             color=P["a3"], fontfamily=ps.FONT_MONO, fontsize=6.5)
    ps.source(fig, f"p5_eurusd_sensitivity.csv · N = {ps.fmt_int(m['n_paths'])}")
    return fig


# --- tableaux en image ---------------------------------------------------------------------------

def _table(width_px, header, aligns, cells, best=None, accent_last=False, foot=None):
    """Tableau de la maquette : en-têtes monospace discrets en capitales, filets fins, chiffres
    en monospace, première colonne en sans-serif ; ligne best surlignée (fond + barre a1)."""
    head_px, row_px = 26, 24
    H = head_px + row_px * len(cells) + (26 if foot else 8)
    fig = ps.new_figure(width_px, H)
    _glows(fig, (0.05, 0.5, "a2", 0.22), (0.95, 0.5, "a1", 0.12))
    left, right, first_w = 0.02, 0.98, 0.27
    n = len(header)
    edges = np.concatenate(([left], np.linspace(left + first_w, right, n)))

    def y(px):                                  # pixels depuis le haut → fraction de figure
        return 1 - px / H

    def put(i, yy, text, **kw):
        r = aligns[i] == "r"
        fig.text(edges[i + 1] - 0.008 if r else edges[i] + 0.008, yy, text,
                 ha="right" if r else "left", va="center", **kw)

    for i, h in enumerate(header):
        put(i, y(head_px / 2), h.upper(), color=P["mut"], fontfamily=ps.FONT_MONO, fontsize=6)
    fig.add_artist(Line2D([left, right], [y(head_px)] * 2, color="white", alpha=0.12, lw=0.6))
    for k, row in enumerate(cells):
        top = head_px + k * row_px
        if k == best:
            fig.add_artist(Rectangle((left, y(top + row_px)), right - left, row_px / H,
                                     color="white", alpha=0.045, lw=0))
            fig.add_artist(Rectangle((left, y(top + row_px)), 2 / width_px, row_px / H,
                                     color=P["a1"], lw=0))
        for i, cell in enumerate(row):
            if i == 0:
                put(i, y(top + row_px / 2), cell, fontfamily=ps.FONT_SANS, fontsize=7.5,
                    color=P["ink"] if k == best else P["sub"])
            else:
                put(i, y(top + row_px / 2), cell, fontfamily=ps.FONT_MONO, fontsize=7,
                    color=P["a1"] if accent_last and i == n - 1 else P["ink"])
        fig.add_artist(Line2D([left, right], [y(top + row_px)] * 2, color="white", alpha=0.07,
                              lw=0.6))
    if foot:
        ps.source(fig, foot, x=left, ha="left")
    return fig


def table1_estimators():
    rows = [r for r in _rows("p3_vr_atm.csv") if float(r["T"]) == 1]
    by = {(r["estimator"], r["option"]): r for r in rows}
    order = sorted({r["estimator"] for r in rows},
                   key=lambda e: float(by[(e, "call")]["efficiency_gain_vs_plain"]))

    def half(r):
        return ps.fmt_err((float(r["ci_high"]) - float(r["ci_low"])) / 2)

    cells = []
    for e in order:
        c, p = by[(e, "call")], by[(e, "put")]
        cells.append([ESTIMATOR_NAMES[e], ps.fmt_num(float(c["price"]), 4), half(c),
                      ps.fmt_num(float(p["price"]), 4), half(p),
                      f"×{ps.fmt_int(float(c['efficiency_gain_vs_plain']))} / "
                      f"×{ps.fmt_int(float(p['efficiency_gain_vs_plain']))}"])
    f = rows[0]
    foot = (f"p3_vr_atm.csv · T = 1 · K = S0 = {ps.fmt_num(float(f['K']), 0)} · "
            f"N = {ps.fmt_int(f['n_paths'])} · seed {f['seed']} · AS241")
    return _table(FULL_PX, ["Estimateur", "Call", "± IC 95 %", "Put", "± IC 95 %",
                            "Gain call / put"], "lrrrrr", cells, best=len(cells) - 1,
                  accent_last=True, foot=foot)


def table2_eurusd():
    rows = _rows("p5_eurusd.csv")
    label = {"spot": "K = S0", "forward": "K = forward 1 an"}
    cells = []
    for r in rows:
        half = (float(r["asian_ci_high"]) - float(r["asian_ci_low"])) / 2
        cells.append([f"{label[r['strike_type']]} · {r['option']}", ps.fmt_num(float(r["K"]), 4),
                      ps.fmt_num(float(r["asian_price"]), 4), ps.fmt_err(half),
                      ps.fmt_num(float(r["euro_bs_price"]), 4),
                      ps.fmt_num(float(r["ratio_asian_euro_bs"]), 2),
                      f"×{ps.fmt_int(float(r['variance_ratio']))}"])
    f = rows[0]
    foot = (f"p5_eurusd.csv · S0 = {ps.fmt_num(float(f['S0']), 4)} · "
            f"σ = {ps.fmt_pct(float(f['sigma']), 2)} · r = {ps.fmt_pct(float(f['r']), 2)} · "
            f"q = {ps.fmt_pct(float(f['q']), 2)} · N = {ps.fmt_int(f['n_paths'])} · "
            f"contrôle β optimal + antithétique · USD pour 1 EUR")
    return _table(FULL_PX, ["Cas", "K", "Asiatique", "± IC 95 %", "Européen BS", "Ratio",
                            "Variance ÷"], "lrrrrrr", cells, foot=foot)


FIGURES = {
    "fig1_eventail_eurusd": fig1_fan,
    "fig2_disques_ratio": fig2_disks,
    "fig3_gain_efficacite": fig3_efficiency,
    "fig4_convergence": fig4_convergence,
    "fig5_nuage_payoffs": fig5_scatter,
    "fig6_eurusd_sigma": fig6_eurusd_sigma,
    "tab1_estimateurs": table1_estimators,
    "tab2_eurusd": table2_eurusd,
}


def build(names=None, out_dir: Path = FIG_DIR) -> list[Path]:
    """Génère les figures demandées (toutes par défaut) ; renvoie les fichiers écrits."""
    ps.apply_style()
    written = []
    for name in names or FIGURES:
        written += ps.save(FIGURES[name](), Path(out_dir) / name)
    return written


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    unknown = [a for a in argv if a not in FIGURES]
    if unknown:
        raise SystemExit(f"figures inconnues {unknown} ; choix : {list(FIGURES)}")
    for p in build(argv or None):
        print(f"{p.relative_to(ROOT)}  {p.stat().st_size:,} octets")


if __name__ == "__main__":
    main()
