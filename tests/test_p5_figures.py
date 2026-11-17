"""Figures du rapport (P5b, étapes 2 et 3) : scripts/p5_figures.py → results/figures/.

Chaque nombre d'une figure vient d'un CSV de results/ ou d'un calcul du pricer dans le script ;
chaque figure se régénère à l'identique (même seed) ; aucune valeur n'est codée en dur.
"""
from __future__ import annotations

import csv
import io
import math
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

def test_every_figure_has_png_300_dpi_and_pdf():
    assert pf.FIGURES, "aucune figure déclarée"
    for name in pf.FIGURES:
        png, pdf = FIG_DIR / f"{name}.png", FIG_DIR / f"{name}.pdf"
        assert png.exists() and pdf.exists(), name
        with Image.open(png) as im:
            assert im.info["dpi"] == pytest.approx((300, 300), abs=0.5)
        assert pdf.read_bytes().startswith(b"%PDF")


def test_figures_regenerate_identically(tmp_path):
    written = pf.build(out_dir=tmp_path)
    assert {p.stem for p in written} == set(pf.FIGURES)
    for p in written:
        assert p.read_bytes() == (FIG_DIR / p.name).read_bytes(), p.name


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
