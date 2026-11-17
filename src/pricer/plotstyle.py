"""Style « Plasma » des figures du rapport (P5b, étape 2), repris de la maquette validée par Loup.

Maquette : docs/maquettes/2026-11-17-maquette-F-nuit-profonde.html (Loup, 17/11/2026, 15:21 :
« Plasma validé pour moi »). Fond noir profond #030306, lueurs floues en arrière-plan, aucune boîte
grise (axes transparents, sans cadre), grille en pointillés discrets, texte clair.

Polices : la maquette utilise Inter et JetBrains Mono (Google Fonts), absentes de cette machine ; on
prend les polices installées avec Windows les plus proches : Segoe UI (sans-serif, texte) et
Consolas (monospace, chiffres). Les deux couvrent ⁰…⁹, ⁻, ×, −, σ, √ (vérifié avec fontTools).

Dimensions : la maquette est une page A4 de 794 × 1123 px (96 px par pouce) ; new_figure(w, h)
prend des pixels de la maquette, la sortie PNG est à 300 dpi et le PDF est vectoriel (polices
TrueType incorporées, pdf.fonttype = 42 ; métadonnées de date retirées : sortie reproductible).

Lueurs (add_glows) : taches gaussiennes calculées (aucun aléa), composées sur le fond et affichées
par imshow dans un axe de fond (zorder < 0). Pas de grain : il demanderait un bruit aléatoire.

Ce module n'utilise aucun générateur aléatoire (règle du projet pour src/).
"""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib
import numpy as np
from matplotlib import pyplot as plt

PALETTE = {
    "bg": "#030306",       # fond de page de la maquette
    "a1": "#00ffa3",       # accent 1 (Plasma)
    "a2": "#7c3aed",       # accent 2
    "a3": "#ffd60a",       # accent 3
    "neg": "#ff4d6d",      # négatif (Plasma)
    "ink": "#f4f5fb",      # texte
    "sub": "#a3a6b8",      # texte secondaire
    "mut": "#5c6075",      # texte discret, axes
}
HAIR = (1.0, 1.0, 1.0, 0.07)       # filets de la maquette : rgba(255, 255, 255, .07)
GRID_ALPHA = 0.1                   # grille : blanc à 10 % (un peu plus que l'écran, pour l'impression)
GRID_DASH = (0, (2, 4))            # pointillés de la maquette (stroke-dasharray 2 4)
FONT_SANS = "Segoe UI"
FONT_MONO = "Consolas"
PX_PER_INCH = 96                   # la maquette est dessinée en px CSS (96 par pouce)
DPI = 300

_SUPERSCRIPT = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")
NBSP = " "
MINUS = "−"


def hex_rgb(color: str) -> tuple[float, float, float]:
    """« #rrggbb » ou nom de PALETTE → (r, g, b) dans [0, 1]."""
    color = PALETTE.get(color, color).lstrip("#")
    return tuple(int(color[i:i + 2], 16) / 255 for i in (0, 2, 4))


# --- formats français --------------------------------------------------------------------------

def fmt_num(v: float, decimals: int) -> str:
    """Virgule décimale et vrai signe moins : fmt_num(−0,4963, 2) = « −0,50 »."""
    return f"{float(v):.{decimals}f}".replace(".", ",").replace("-", MINUS)


def fmt_int(v: float) -> str:
    """Entier arrondi, milliers séparés par une espace insécable : 2914,9 → « 2 915 »."""
    return f"{round(float(v)):,}".replace(",", NBSP).replace("-", MINUS)


def fmt_pct(x: float, decimals: int) -> str:
    """Fraction en pourcentage : 0,055566 → « 5,56 % »."""
    return f"{fmt_num(100 * x, decimals)}{NBSP}%"


def sup(n: int) -> str:
    """Entier en exposant Unicode : sup(−3) = « ⁻³ »."""
    return str(int(n)).translate(_SUPERSCRIPT)


def fmt_sig(v: float) -> str:
    """Graduation : nombre de décimales juste suffisant (0,001 ; 0,1 ; 1), virgule décimale."""
    v = float(v)
    decimals = max(0, -math.floor(math.log10(abs(v)))) if v else 0
    return fmt_num(v, decimals)


def fmt_err(v: float) -> str:
    """Écart-type ou demi-largeur d'IC (réponse Q5, P5b) : arrondi à 10^-4, sauf sous 10^-4 :
    notation scientifique à 2 chiffres significatifs, « 4,2 × 10⁻⁷ »."""
    v = float(v)
    if v == 0 or abs(v) >= 1e-4:
        return fmt_num(v, 4)
    exp = math.floor(math.log10(abs(v)))
    mant = round(v / 10 ** exp, 1)
    if abs(mant) >= 10:                     # 9,96 × 10⁻⁵ → 1,0 × 10⁻⁴
        mant, exp = mant / 10, exp + 1
    return f"{fmt_num(mant, 1)} × 10{str(exp).translate(_SUPERSCRIPT)}"


# --- style -------------------------------------------------------------------------------------

def apply_style() -> None:
    """Paramètres matplotlib du style Plasma (fond, polices, couleurs de texte, sorties)."""
    matplotlib.rcParams.update({
        "figure.facecolor": PALETTE["bg"],
        "savefig.facecolor": PALETTE["bg"],
        "axes.facecolor": "none",
        "axes.edgecolor": "none",
        "axes.labelcolor": PALETTE["sub"],
        "axes.titlecolor": PALETTE["ink"],
        "axes.grid": False,
        "text.color": PALETTE["ink"],
        "xtick.color": PALETTE["mut"],
        "ytick.color": PALETTE["mut"],
        "xtick.labelcolor": PALETTE["mut"],
        "ytick.labelcolor": PALETTE["mut"],
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "xtick.minor.size": 0,
        "ytick.minor.size": 0,
        "font.family": "sans-serif",
        "font.sans-serif": [FONT_SANS],
        "font.monospace": [FONT_MONO],
        "font.size": 7.5,
        "axes.labelsize": 7.5,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "legend.frameon": False,
        "legend.fontsize": 7,
        "lines.solid_capstyle": "round",
        "axes.unicode_minus": True,
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
        "savefig.dpi": DPI,
    })


def new_figure(width_px: float, height_px: float):
    """Figure de width_px × height_px pixels de la maquette (96 px par pouce)."""
    return plt.figure(figsize=(width_px / PX_PER_INCH, height_px / PX_PER_INCH))


def mono(ax) -> None:
    """Graduations en monospace (à rappeler après un changement de graduations)."""
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontfamily(FONT_MONO)


def style_axes(ax, grid: str = "both") -> None:
    """Aucun cadre, fond transparent, grille pointillée discrète, graduations en monospace."""
    ax.set_facecolor("none")
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0, pad=3, colors=PALETTE["mut"], labelcolor=PALETTE["mut"])
    mono(ax)
    if grid in ("x", "y", "both"):
        # alpha explicite : sinon grid.alpha (1) écrase l'alpha de la couleur
        ax.grid(True, axis=grid, color="white", alpha=GRID_ALPHA, linestyle=GRID_DASH,
                linewidth=0.6)
        ax.set_axisbelow(True)


def add_glows(fig, glows, resolution: int = 240):
    """Lueurs floues en arrière-plan : glows = [(cx, cy, sx, sy, couleur, opacité)], centre et
    écarts-types en fraction de la figure (y vers le haut). Pixel = fond composé avec chaque tache,
    α = opacité·exp(−((x − cx)²/(2sx²) + (y − cy)²/(2sy²))). Renvoie l'image (AxesImage)."""
    w, h = fig.get_size_inches()
    nx, ny = resolution, max(2, round(resolution * h / w))
    x = (np.arange(nx) + 0.5) / nx
    y = 1.0 - (np.arange(ny) + 0.5) / ny          # ligne 0 en haut de l'image
    X, Y = np.meshgrid(x, y)
    img = np.empty((ny, nx, 3))
    img[:] = hex_rgb(PALETTE["bg"])
    for cx, cy, sx, sy, color, opacity in glows:
        a = opacity * np.exp(-((X - cx) ** 2 / (2 * sx * sx) + (Y - cy) ** 2 / (2 * sy * sy)))
        img = img * (1 - a[..., None]) + np.asarray(hex_rgb(color)) * a[..., None]
    ax = fig.add_axes((0, 0, 1, 1), zorder=-10)
    ax.set_axis_off()
    return ax.imshow(img, extent=(0, 1, 0, 1), aspect="auto", interpolation="bilinear",
                     origin="upper")


def source(fig, text: str, x: float = 0.995, y: float = 0.012, ha: str = "right") -> None:
    """Source courte en bas (à droite par défaut), monospace discret."""
    fig.text(x, y, text, ha=ha, va="bottom", color=PALETTE["mut"], fontfamily=FONT_MONO,
             fontsize=6)


def save(fig, stem) -> tuple[Path, Path]:
    """Écrit stem.png (300 dpi) et stem.pdf (vectoriel), sans date de création ; ferme la figure."""
    stem = Path(stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    png, pdf = stem.with_suffix(".png"), stem.with_suffix(".pdf")
    fig.savefig(png, dpi=DPI, metadata={"Software": None})
    fig.savefig(pdf, metadata={"CreationDate": None, "ModDate": None, "Producer": None,
                               "Creator": None})
    plt.close(fig)
    return png, pdf
