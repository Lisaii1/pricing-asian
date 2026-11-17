"""Style Plasma des figures : pricer.plotstyle.

Palette et fond repris de la maquette « nuit profonde » retenue par le groupe
(17/11/2026), polices Windows installées, formats français, lueurs
gaussiennes en arrière-plan, axes sans boîte, sorties PNG 300 dpi et PDF vectoriel reproductibles.
"""
from __future__ import annotations

import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from PIL import Image  # noqa: E402

from pricer import plotstyle as ps  # noqa: E402

MAQUETTE = (Path(__file__).resolve().parents[1] / "docs" / "maquettes"
            / "2026-11-17-maquette-F-nuit-profonde.html")


def _css_vars(selector_line: str) -> dict:
    return dict(re.findall(r"--(\w+):(#[0-9a-fA-F]{6})", selector_line))


@pytest.mark.skipif(not MAQUETTE.exists(), reason="maquette de travail non livrée avec le code")
def test_palette_matches_validated_maquette():
    lines = MAQUETTE.read_text(encoding="utf-8").splitlines()
    root = _css_vars(next(l for l in lines if l.startswith(":root{")))
    plasma = _css_vars(next(l for l in lines if "body[data-p=plasma]" in l))
    assert ps.PALETTE["a1"] == plasma["a1"] == "#00ffa3"
    assert ps.PALETTE["a2"] == plasma["a2"] == "#7c3aed"
    assert ps.PALETTE["a3"] == plasma["a3"] == "#ffd60a"
    assert ps.PALETTE["neg"] == plasma["neg"]
    for k in ("ink", "sub", "mut"):
        assert ps.PALETTE[k] == root[k]
    page_bg = re.search(r"\.page\{[^}]*background:(#[0-9a-fA-F]{6})", "\n".join(lines)).group(1)
    assert ps.PALETTE["bg"] == page_bg == "#030306"


def test_fonts_are_installed_without_fallback():
    for family in (ps.FONT_SANS, ps.FONT_MONO):
        path = font_manager.findfont(font_manager.FontProperties(family=family),
                                     fallback_to_default=False)
        assert Path(path).exists()


def test_french_number_formats():
    assert ps.fmt_num(5.324176, 4) == "5,3242"
    assert ps.fmt_num(-0.4963, 2) == "−0,50"              # vrai signe moins
    assert ps.fmt_int(2914.9) == "2 915"            # espace insécable des milliers
    assert ps.fmt_int(200_000) == "200 000"
    assert ps.fmt_pct(0.055566, 2) == "5,56 %"


def test_error_format_is_scientific_below_1e_4():
    # convention du projet : écarts-types et demi-largeurs sous 10^-4 en scientifique, 2 chiffres
    assert ps.fmt_err(4.2e-7) == "4,2 × 10⁻⁷"
    assert ps.fmt_err(2.4672e-07) == "2,5 × 10⁻⁷"
    assert ps.fmt_err(9.96e-5) == "1,0 × 10⁻⁴"
    assert ps.fmt_err(0.00047) == "0,0005"                # sinon arrondi à 10^-4
    assert ps.fmt_err(0.0179) == "0,0179"


def test_superscript_and_significant_tick_formats():
    assert ps.sup(-3) == "⁻³" and ps.sup(6) == "⁶"
    assert ps.fmt_sig(0.001) == "0,001"                   # graduations log : chiffres utiles
    assert ps.fmt_sig(0.1) == "0,1"
    assert ps.fmt_sig(1.0) == "1"


def test_axes_have_no_box_transparent_face_and_dashed_grid():
    ps.apply_style()
    fig, ax = plt.subplots()
    ps.style_axes(ax)
    assert not any(s.get_visible() for s in ax.spines.values())
    assert ax.get_facecolor()[3] == 0                     # aucune boîte grise
    fig.canvas.draw()
    grid = [l for l in ax.get_xgridlines() + ax.get_ygridlines() if l.get_visible()]
    assert grid and all(l.get_linestyle() not in ("-", "solid") for l in grid)
    plt.close(fig)


def test_glows_are_gaussian_background_image_with_low_opacity():
    ps.apply_style()
    fig = ps.new_figure(400, 200)
    img = ps.add_glows(fig, [(0.2, 0.8, 0.3, 0.3, "a2", 0.35)])
    assert img.axes.get_zorder() < 0 and not img.axes.axison
    arr = np.asarray(img.get_array(), dtype=float)
    assert arr.ndim == 3 and arr.shape[2] == 3
    bg, a2 = np.array(ps.hex_rgb(ps.PALETTE["bg"])), np.array(ps.hex_rgb(ps.PALETTE["a2"]))
    # pixel = fond + α·(couleur − fond), α = 0,35·gaussienne ≤ 0,35
    alpha = (arr - bg) / (a2 - bg)
    assert alpha.max() <= 0.35 + 1e-9 and alpha.min() >= -1e-9
    assert alpha.max() > 0.3                               # centre de la tache
    plt.close(fig)


def test_new_figure_size_is_maquette_pixels_at_96_per_inch():
    fig = ps.new_figure(534, 300)
    assert tuple(fig.get_size_inches()) == pytest.approx((534 / 96, 300 / 96))
    plt.close(fig)


def test_save_writes_png_300_dpi_and_vector_pdf_reproducibly(tmp_path):
    ps.apply_style()

    def make():
        fig = ps.new_figure(340, 200)
        ax = fig.add_axes((0.1, 0.1, 0.8, 0.8))
        ps.style_axes(ax)
        ax.plot([1, 2, 3], [1, 4, 9], color=ps.PALETTE["a1"])
        ax.set_title("σ = 5,56 %")
        return fig

    png, pdf = ps.save(make(), tmp_path / "a" / "x")
    png2, pdf2 = ps.save(make(), tmp_path / "b" / "x")
    assert (png.suffix, pdf.suffix) == (".png", ".pdf")
    with Image.open(png) as im:
        assert im.info["dpi"] == pytest.approx((300, 300), abs=0.5)
        assert im.size == (round(340 / 96 * 300), round(200 / 96 * 300))
    raw = pdf.read_bytes()
    assert raw.startswith(b"%PDF") and b"CreationDate" not in raw
    assert b"/Type3" not in raw                            # polices TrueType incorporées (42)
    assert png.read_bytes() == png2.read_bytes()
    assert raw == pdf2.read_bytes()
