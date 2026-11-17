"""Figures du rapport (P5b, étapes 2 et 3) : scripts/p5_figures.py → results/figures/.

Chaque nombre d'une figure vient d'un CSV de results/ ou d'un calcul du pricer dans le script ;
chaque figure se régénère à l'identique (même seed) ; aucune valeur n'est codée en dur.
"""
from __future__ import annotations

import csv
import io
import math
import re
import sys
import tokenize
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402
from matplotlib.text import Text  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p5_figures as pf  # noqa: E402
from pricer import plotstyle as ps  # noqa: E402
from pricer.paths import gbm_paths  # noqa: E402

RESULTS = ROOT / "results"
FIG_DIR = RESULTS / "figures"


def _rows(name):
    with (RESULTS / name).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _texts(fig):
    return [t.get_text() for t in fig.findobj(Text) if t.get_text()]


@pytest.fixture(scope="module")
def fan():
    return pf.fan_data()


# --- fichiers ------------------------------------------------------------------------------------

# Le paquet remis au professeur ne contient que les figures du mode rendu (results/figures/rendu/) :
# les deux tests des figures internes ne s'y appliquent pas.
INTERNES = any(FIG_DIR.glob("*.png"))
needs_internal = pytest.mark.skipif(not INTERNES and pf.RENDU_DIR.is_dir(),
                                    reason="paquet de rendu : seules les figures du mode rendu y sont")


@needs_internal
def test_every_figure_has_png_300_dpi_and_pdf():
    assert pf.FIGURES, "aucune figure déclarée"
    for name in pf.FIGURES:
        png, pdf = FIG_DIR / f"{name}.png", FIG_DIR / f"{name}.pdf"
        assert png.exists() and pdf.exists(), name
        with Image.open(png) as im:
            assert im.info["dpi"] == pytest.approx((300, 300), abs=0.5)
        assert pdf.read_bytes().startswith(b"%PDF")


@needs_internal
def test_figures_regenerate_identically(tmp_path):
    written = pf.build(out_dir=tmp_path)
    assert {p.stem for p in written} == set(pf.FIGURES)
    for p in written:
        assert p.read_bytes() == (FIG_DIR / p.name).read_bytes(), p.name


# --- mode rendu : figures remises au lecteur ----------------------------------------------------------

def test_rendu_figures_exist_png_300_dpi_and_pdf():
    for name in pf.FIGURES:
        png, pdf = pf.RENDU_DIR / f"{name}.png", pf.RENDU_DIR / f"{name}.pdf"
        assert png.exists() and pdf.exists(), name
        with Image.open(png) as im:
            assert im.info["dpi"] == pytest.approx((300, 300), abs=0.5)
        assert pdf.read_bytes().startswith(b"%PDF")


def test_rendu_figures_regenerate_identically(tmp_path):
    written = pf.build(out_dir=tmp_path, rendu=True)
    assert {p.stem for p in written} == set(pf.FIGURES)
    for p in written:
        assert p.read_bytes() == (pf.RENDU_DIR / p.name).read_bytes(), p.name


def _rendu_texts(name):
    fn = pf.FIGURES[name]
    fig = fn(rendu=True)
    texts = _texts(fig)
    plt.close(fig)
    return texts


@pytest.mark.parametrize("name", sorted(pf.FIGURES))
def test_rendu_figures_say_the_source_in_clear(name):
    """Pied de figure en clair : ni nom de fichier, ni « seed », ni étape de travail ; la source
    (simulation Monte-Carlo et sa graine, ou les données officielles) est écrite."""
    joined = " ".join(_rendu_texts(name))
    assert ".csv" not in joined and "seed" not in joined and "pricer" not in joined
    assert not re.search(r"\bP[1-6][ab]?\b|prompt|cowork|claude", joined, re.I), joined
    assert "Simulation Monte-Carlo" in joined
    assert re.search(r"graine \d+", joined)
    if name in ("fig1_eventail_eurusd", "tab2_eurusd"):
        assert "Données : BCE, Trésor américain" in joined


def test_rendu_fig3_gains_at_order_of_magnitude():
    labels = _rendu_texts("fig3_gain_efficacite")
    rows = _rows("p3_vr_atm.csv")
    for est in {r["estimator"] for r in rows}:
        best = max(float(r["efficiency_gain_vs_plain"]) for r in rows if r["estimator"] == est)
        assert f"×{pf._og(best)}" in labels, est
        if best >= 100:
            assert f"×{ps.fmt_int(best)}" not in labels, est        # plus de gain à l'unité
    gains = [t for t in labels if t.startswith("×") and t not in ("×1", "×10", "×100")]
    assert all(len(re.sub(r"\D", "", t).rstrip("0")) <= 2 for t in gains), gains


def test_order_of_magnitude_helper():
    assert pf._og(4021.5) == ps.fmt_int(4000) and pf._og(5079.4) == ps.fmt_int(5100)
    assert pf._og(9124.9) == ps.fmt_int(9100) and pf._og(1349.6) == ps.fmt_int(1300)
    assert pf._og(3.86) == "3,9" and pf._og(9.96) == "10"


def test_rendu_table1_gives_variance_ratios_not_timed_gains():
    texts = _rendu_texts("tab1_estimateurs")
    rows = [r for r in _rows("p3_vr_atm.csv") if float(r["T"]) == 1.0]
    assert "VARIANCE ÷" in texts and any("variance ÷ : call / put" in t for t in texts)

    def fmt(v):
        return ps.fmt_num(v, 2) if v < 10 else ps.fmt_int(v)

    for est in {r["estimator"] for r in rows}:
        c, p = (next(float(r["var_ratio_vs_plain"]) for r in rows
                     if r["estimator"] == est and r["option"] == o) for o in ("call", "put"))
        assert f"×{fmt(c)} / ×{fmt(p)}" in texts


def test_no_hardcoded_values_in_figure_script():
    """Aucune donnée tapée : pas de seed, pas de flottant à plus de 2 chiffres significatifs, pas
    d'entier ≥ 1 000 (hors N_SCATTER = 2 000 trajectoires du nuage, fixé par le prompt)."""
    src = (ROOT / "scripts" / "p5_figures.py").read_text(encoding="utf-8")
    assert "20261117" not in src
    bad = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type != tokenize.NUMBER:
            continue
        text = tok.string.replace("_", "")
        if any(c in text for c in ".eE") and not text.lower().startswith("0x"):
            digits = text.lower().split("e")[0].replace(".", "").lstrip("0")
            if len(digits.rstrip("0")) > 2:
                bad.append((tok.start[0], tok.string))
        elif int(text, 0) >= 1000 and not tok.line.lstrip().startswith("N_SCATTER"):
            bad.append((tok.start[0], tok.string))
    assert bad == []


# --- figure 1 : éventail EUR/USD -------------------------------------------------------------------

def test_fig1_parameters_come_from_p5_market(fan):
    m = {r["name"]: r for r in _rows("p5_market.csv")}
    assert (fan["S0"], fan["sigma"], fan["r"], fan["q"]) == tuple(
        float(m[k]["value"]) for k in ("S0", "sigma_ecb", "r_usd", "q_eur"))
    assert fan["n_paths"] == int(_rows("p5_eurusd.csv")[0]["n_paths"]) == 200_000
    assert fan["seed"] == int(_rows("p5_eurusd.csv")[0]["seed"])


def test_fig1_shown_paths_and_monthly_points(fan):
    shown = fan["shown"]
    assert shown.shape[0] == pf.N_FAN_SHOWN == 200
    assert np.all(shown[:, 0] == fan["S0"])
    idx = fan["monthly_idx"]
    assert len(idx) == 12 and idx[-1] == shown.shape[1] - 1
    assert np.all(np.diff(idx) == idx[0])                      # pas régulier (21 jours sur 252)
    assert 0 <= fan["highlight"] < shown.shape[0]


def test_fig1_histograms_use_pricer_paths_not_the_shown_ones(fan):
    ST, A = fan["ST"], fan["A"]
    assert ST.size == A.size == fan["n_paths"]
    first = next(gbm_paths(fan["S0"], fan["sigma"], fan["r"], 1.0, fan["q"], obs="monthly",
                           n_paths=7, seed=fan["seed"]))
    assert np.array_equal(ST[:7], first[:, -1])
    assert np.allclose(A[:7], first.mean(axis=1), rtol=0, atol=1e-15)
    fwd = fan["S0"] * math.exp(fan["r"] - fan["q"])            # E[S_T] = forward
    assert abs(ST.mean() - fwd) < 4 * ST.std(ddof=1) / math.sqrt(ST.size)
    assert A.std() < ST.std()                                   # la moyenne disperse moins


def test_fig1_writes_calibrated_numbers(fan):
    fig = pf.fig1_fan(fan)
    txt = " ".join(_texts(fig))
    assert ps.fmt_num(fan["S0"], 4) in txt and ps.fmt_pct(fan["sigma"], 2) in txt
    assert ps.fmt_int(fan["n_paths"]) in txt
    assert ps.fmt_num(fan["ST"].std(ddof=1), 4) in txt
    assert ps.fmt_num(fan["A"].std(ddof=1), 4) in txt
    plt.close(fig)


# --- figure 2 : disques asiatique / européen -------------------------------------------------------

def test_fig2_disk_labels_are_p4_grid_ratios():
    fig = pf.fig2_disks()
    labels = _texts(fig)
    rows = _rows("p4_grid_cv.csv")
    assert len(rows) == 40
    for r in rows:
        assert ps.fmt_num(float(r["ratio"]), 2) in labels
    assert sum(1 for t in labels if t.count(",") == 1 and len(t) == 4) == 40
    plt.close(fig)


# --- figure 3 : gain d'efficacité -----------------------------------------------------------------

def test_fig3_max_gain_labels_are_p3_values():
    fig = pf.fig3_efficiency()
    labels = _texts(fig)
    rows = _rows("p3_vr_atm.csv")
    for est in {r["estimator"] for r in rows}:
        best = max(float(r["efficiency_gain_vs_plain"]) for r in rows if r["estimator"] == est)
        assert f"×{ps.fmt_int(best)}" in labels, est
    plt.close(fig)


# --- figure 4 : convergence mesurée -----------------------------------------------------------------

def test_fig4_points_are_measured_half_widths_and_slopes_written():
    fig = pf.fig4_convergence()
    conv, slopes = _rows("p4_convergence.csv"), _rows("p4_convergence_slopes.csv")
    coll = {c.get_gid(): c for c in fig.findobj(lambda o: bool(getattr(o, "get_gid", None)
                                                              and o.get_gid()))}
    texts = " ".join(_texts(fig))
    for s in slopes:
        est = s["estimator"]
        pts = [(float(r["n_paths"]), float(r["half_width_95"])) for r in conv if r["estimator"] == est]
        assert np.allclose(coll[f"points:{est}"].get_offsets(), pts, rtol=1e-15)
        x, y = coll[f"fit:{est}"].get_data()
        assert np.allclose(y, np.exp(float(s["intercept"])) * np.asarray(x) ** float(s["slope"]))
        assert f"pente {ps.fmt_num(float(s['slope']), 2)}" in texts
    eps = max(float(r["epsilon"]) for r in _rows("p4_n_required.csv"))
    assert f"±{ps.fmt_num(eps, 2)}" in texts
    plt.close(fig)


# --- figure 5 : nuage payoff arithmétique / géométrique ---------------------------------------------

def test_fig5_scatter_uses_pricer_paths_and_writes_correlation():
    d = pf.scatter_data()
    row = next(r for r in _rows("p3_vr_atm.csv") if float(r["T"]) == 1.0 and r["option"] == "call"
               and r["estimator"] == "control_beta_optimal")
    assert d["n"] == pf.N_SCATTER == 2_000 and d["arith"].size == d["geo"].size == 2_000
    assert (d["S0"], d["K"], d["sigma"], d["r"], d["q"], d["T"]) == tuple(
        float(row[k]) for k in ("S0", "K", "sigma", "r", "q", "T"))
    assert d["corr"] == pytest.approx(np.corrcoef(d["arith"], d["geo"])[0, 1], rel=1e-15)
    assert np.all(d["arith"] >= d["geo"] - 1e-12)              # A ≥ G (moyennes)
    se = d["geo"].std(ddof=1) / math.sqrt(d["n"])               # E[payoff G] = formule fermée
    assert abs(d["geo"].mean() - float(row["geometric_closed_form"])) < 4 * se
    fig = pf.fig5_scatter(d)
    assert ps.fmt_num(d["corr"], 4) in " ".join(_texts(fig))
    plt.close(fig)


# --- figure 6 : cas réel, prix contre σ --------------------------------------------------------------

def test_fig6_curves_come_from_sensitivity_csv_at_strike_s0():
    fig = pf.fig6_eurusd_sigma()
    rows = [r for r in _rows("p5_eurusd_sensitivity.csv") if r["strike_type"] == "spot"]
    lines = {l.get_gid(): l for l in fig.findobj(lambda o: bool(getattr(o, "get_gid", None)
                                                               and o.get_gid()))}
    for option in ("call", "put"):
        sub = sorted((r for r in rows if r["option"] == option), key=lambda r: float(r["sigma"]))
        for kind, col in (("asian", "asian_pct_S0"), ("euro", "euro_bs_pct_S0")):
            x, y = lines[f"{kind}:{option}"].get_data()
            assert np.allclose(x, [100 * float(r["sigma"]) for r in sub], rtol=1e-15)
            assert np.allclose(y, [float(r[col]) for r in sub], rtol=1e-15)
    measured = next(r for r in rows if r["sigma_label"] == "mesuré")
    texts = " ".join(_texts(fig))
    assert ps.fmt_pct(float(measured["sigma"]), 2) in texts
    plt.close(fig)


# --- tableaux en image --------------------------------------------------------------------------------

def test_table1_estimators_at_T1_from_p3():
    fig = pf.table1_estimators()
    texts = _texts(fig)
    rows = [r for r in _rows("p3_vr_atm.csv") if float(r["T"]) == 1.0]
    assert len(rows) == 10
    for r in rows:
        assert ps.fmt_num(float(r["price"]), 4) in texts
        assert ps.fmt_err((float(r["ci_high"]) - float(r["ci_low"])) / 2) in texts
    for est in {r["estimator"] for r in rows}:
        c, p = (next(float(r["efficiency_gain_vs_plain"]) for r in rows
                     if r["estimator"] == est and r["option"] == o) for o in ("call", "put"))
        assert f"×{ps.fmt_int(c)} / ×{ps.fmt_int(p)}" in texts
    plt.close(fig)


def test_table2_real_case_from_p5_eurusd():
    fig = pf.table2_eurusd()
    texts = _texts(fig)
    for r in _rows("p5_eurusd.csv"):
        assert ps.fmt_num(float(r["K"]), 4) in texts
        assert ps.fmt_num(float(r["asian_price"]), 4) in texts
        assert ps.fmt_err((float(r["asian_ci_high"]) - float(r["asian_ci_low"])) / 2) in texts
        assert ps.fmt_num(float(r["euro_bs_price"]), 4) in texts
        assert ps.fmt_num(float(r["ratio_asian_euro_bs"]), 2) in texts
    plt.close(fig)


def test_all_expected_figures_declared():
    assert set(pf.FIGURES) == {"fig1_eventail_eurusd", "fig2_disques_ratio", "fig3_gain_efficacite",
                               "fig4_convergence", "fig5_nuage_payoffs", "fig6_eurusd_sigma",
                               "tab1_estimateurs", "tab2_eurusd"}
