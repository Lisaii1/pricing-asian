"""Classeur de résultats (P5b, étape 4) → results/pricing_asian_resultats.xlsx (openpyxl).

Onglets : « Lisez-moi » (projet, méthode en 10 lignes, sources avec URL et dates, seed, index des
onglets), « Paramètres » (actif théorique et EUR/USD), un onglet par CSV de results/ utile au rendu
(p2 à p5 ; le détail run par run p4_beta_bias_runs.csv est résumé dans p4_beta_bias), « Figures »
(PNG de results/figures/ insérés).

Les valeurs sont copiées des CSV (nombres convertis, aucune formule : rien n'est recalculé dans
Excel). Formats : prix 0,0000 ; écarts-types et demi-largeurs en scientifique à 2 chiffres sous
10^-4, 0,0000 sinon (réponse Q5) ; temps 0,000 s ; gains et ratios de variance #,##0,0 ; seeds
sans séparateur. Mise en forme sombre et sobre (Plasma : en-têtes #030306, texte #f4f5fb, filet
a1), volets figés sous l'en-tête et après la première colonne, largeurs ajustées.

Usage : .venv/Scripts/python.exe scripts/p5_excel.py
"""
from __future__ import annotations

import csv
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from openpyxl import Workbook  # noqa: E402
from openpyxl.drawing.image import Image as XLImage  # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402
from PIL import Image  # noqa: E402

from pricer.plotstyle import FONT_MONO, FONT_SANS, PALETTE  # noqa: E402
from pricer.rng import PARK_MILLER_A  # noqa: E402

RESULTS = ROOT / "results"
FIG_DIR = RESULTS / "figures"
MANIFEST = ROOT / "data" / "raw" / "MANIFEST.md"
OUT = RESULTS / "pricing_asian_resultats.xlsx"

ERR_FORMAT = "[<0.0001]0.0E+00;0.0000"
PARAM_BLOCKS = ("Actif théorique", "EUR/USD (actif réel)")
IMAGE_WIDTH_PX = 900
ROW_PX = 20                                  # hauteur d'une ligne Excel par défaut (15 pt)

METHOD = [
    "Actif : Black-Scholes avec dividende continu, dS/S = (r − q)dt + σ dW ; trajectoires "
    "simulées exactement aux dates d'observation (schéma exact du cours).",
    f"Aléa : générateur congruentiel linéaire de Park-Miller (x ← a·x mod m, a = {PARK_MILLER_A}, "
    "m = 2³¹ − 1) ; aucun générateur de bibliothèque.",
    "Normales : transformée inverse Φ⁻¹ (AS241) par défaut ; Box-Muller, Marsaglia polaire et "
    "acceptation-rejet disponibles en paramètre.",
    "Prix Monte-Carlo : moyenne des payoffs actualisés, écart-type s/√N, IC à 95 % avec "
    "z = Φ⁻¹(0,975) calculé par AS241.",
    "Asiatique : moyenne arithmétique des fixings t_k = k·T/n (mensuel par défaut) ; européen "
    "comparé à la formule fermée de Black-Scholes avec q.",
    "Variable de contrôle : asiatique à moyenne géométrique (formule fermée discrète), coefficient "
    "β optimal estimé sur l'échantillon (slide 50).",
    "Antithétiques : paires (Z, −Z) ; combinaison antithétique + contrôle sur les moyennes de paires.",
    "Analyse : grille K × T, convergence en N, N nécessaire pour une marge donnée, comparaison à "
    "temps égal, biais de β sur flux LCG disjoints.",
    "Actif réel EUR/USD (Garman-Kohlhagen) : S0 = fixing BCE, σ historique 1 an, r = Trésor "
    "américain 1 an (2·ln(1 + y/2)), q = BCE AAA 1 an (déjà continu).",
    "Ce classeur copie les CSV de results/ : aucune formule ne recalcule un prix ; prix 0,0000, "
    "écarts-types en notation scientifique sous 10⁻⁴.",
]

HEX = {k: v.lstrip("#").upper() for k, v in PALETTE.items()}
DARK = PatternFill("solid", fgColor=HEX["bg"])
HEAD_FONT = Font(name=FONT_SANS, bold=True, color=HEX["ink"], size=10)
HEAD_BORDER = Border(bottom=Side(style="medium", color=HEX["a1"]))
NUM_FONT = Font(name=FONT_MONO, size=10)
TEXT_FONT = Font(name=FONT_SANS, size=10)


# --- lecture et conversion -----------------------------------------------------------------------

def data_csvs() -> list[Path]:
    """CSV de results/ utiles au rendu : p2 à p5, sans le détail run par run."""
    return sorted(p for p in RESULTS.glob("p[2-5]_*.csv") if not p.stem.endswith("_runs"))


def parse_cell(text: str):
    """Valeur d'une cellule CSV : entier, flottant fini, booléen, None (vide) ou texte."""
    if text == "":
        return None
    if text in ("True", "False"):
        return text == "True"
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    try:
        v = float(text)
    except ValueError:
        return text
    return v if math.isfinite(v) else text


def _read(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.reader(f))


def number_format(column: str, value) -> str | None:
    """Format Excel d'une valeur numérique selon le nom de sa colonne (None : texte)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    c = column.lower()
    if "seed" in c or c == "stream_x0":
        return "0"
    if isinstance(value, int):
        return "#,##0"
    if c == "value":
        return "General"
    if "_in_" in c or c.endswith("minus_expected"):
        return "0.00"
    if re.search(r"std_error|half_width|sd_of_mean|_se$|^sd_", c):
        return ERR_FORMAT
    if "per_path" in c or c == "efficiency":
        return "0.00E+00"
    if re.search(r"time|_s$", c):
        return "0.000"
    if re.search(r"efficiency_gain|var.*ratio", c):
        return "#,##0.0"
    if "corr" in c or c == "z":
        return "0.000000"
    if "pct" in c:
        return "0.00"
    return "0.0000"


# --- mise en forme -------------------------------------------------------------------------------

def _header(ws, row: int, values) -> None:
    for j, v in enumerate(values, start=1):
        c = ws.cell(row, j, v)
        c.fill, c.font, c.border = DARK, HEAD_FONT, HEAD_BORDER
        c.alignment = Alignment(vertical="center")


def _put(ws, row: int, col: int, value, column_name: str = "") -> None:
    c = ws.cell(row, col, value)
    fmt = number_format(column_name, value)
    if fmt:
        c.number_format, c.font = fmt, NUM_FONT
    else:
        c.font = TEXT_FONT


def _widths(ws, lo: int = 8, hi: int = 40) -> None:
    for col in ws.columns:
        n = max((len(str(c.value)) for c in col if c.value is not None), default=lo)
        ws.column_dimensions[col[0].column_letter].width = min(max(n + 2, lo), hi)


# --- onglets -------------------------------------------------------------------------------------

def _manifest_sources() -> list[list[str]]:
    """[source, URL, date du relevé, fichier] depuis le tableau des fichiers de MANIFEST.md."""
    out = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if line.startswith("| `data/raw/"):
            cells = [x.strip() for x in line.split("|")]
            out.append([cells[2], cells[3], cells[4], cells[1].strip("`")])
    return out


def sheet_readme(wb, csvs) -> None:
    ws = wb.active
    ws.title = "Lisez-moi"
    ws.sheet_properties.tabColor = HEX["a1"]
    m_rows = _read(RESULTS / "p5_market.csv")
    market = {r[0]: dict(zip(m_rows[0], r)) for r in m_rows[1:]}
    seed = dict(zip(*_read(RESULTS / "p3_vr_atm.csv")[:2]))["seed"]

    def ink(**kw):
        return Font(name=FONT_SANS, color=HEX["ink"], **kw)

    def head():
        return Font(name=FONT_SANS, color=HEX["a1"], bold=True, size=11)

    rows: list[tuple] = [
        (("Projet Pricing ING4 — option asiatique et réduction de variance",
          ink(bold=True, size=16)),),
        (("Énoncé 2 · cours « Pricing Monte Carlo », ECE Paris, ING4 Finance, S1 2026 "
          "(A. W. Sanoussi Mani)", Font(name=FONT_SANS, color=HEX["sub"], size=10)),),
        (),
        (("Méthode", head()),),
    ]
    rows += [((f"{i}.", ink()), (line, ink())) for i, line in enumerate(METHOD, start=1)]
    rows += [(), (("Seed de référence", head()),
                  (f"{seed} (colonne seed des CSV de results/)", ink())),
             (), (("Sources", head()), ("URL", head()), ("Relevé", head()))]
    rows += [((s, ink()), (u, ink()), (d, ink())) for s, u, d, _ in _manifest_sources()]
    for name, label in (("r_usd", "Convention de r (Trésor)"), ("q_eur", "Convention de q (BCE)")):
        rows.append(((label, ink()),
                     (f"{market[name]['convention']} — {market[name]['note']}", ink())))
    rows += [(("Cours", ink()), ("Slides du cours « Pricing Monte Carlo » (A. W. Sanoussi Mani), "
                                  "notations et formules de référence", ink()))]
    rows += [(), (("Onglets", head()), ("Source", head()), ("Lignes", head()))]
    rows += [((p.stem, ink()), (f"results/{p.name}", ink()), (len(_read(p)) - 1, ink()))
             for p in csvs]
    rows += [(("Paramètres", ink()), ("results/p4_grid_cv.csv, results/p5_market.csv", ink())),
             (("Figures", ink()), ("results/figures/*.png (scripts/p5_figures.py)", ink())),
             (), (("Généré par scripts/p5_excel.py depuis results/ ; aucune valeur saisie à la "
                   "main.", Font(name=FONT_SANS, color=HEX["mut"], size=9)),)]
    for i, row in enumerate(rows, start=1):
        for j in range(1, 5):
            ws.cell(i, j).fill = DARK
        for j, (value, font) in enumerate(row, start=1):
            c = ws.cell(i, j, value)
            c.font = font
            c.alignment = Alignment(vertical="top", wrap_text=j == 2)
    for j, w in zip("ABCD", (26, 110, 28, 4)):
        ws.column_dimensions[j].width = w
    ws.sheet_view.showGridLines = False


def sheet_parameters(wb) -> None:
    ws = wb.create_sheet("Paramètres")
    ws.sheet_properties.tabColor = HEX["a2"]
    _header(ws, 1, ["Paramètre", "Valeur", "Unité", "Date", "Source", "Convention", "Note"])
    grid = _read(RESULTS / "p4_grid_cv.csv")
    g = dict(zip(grid[0], grid[1]))
    Ks = sorted({float(r[grid[0].index("K")]) for r in grid[1:]})
    Ts = sorted({float(r[grid[0].index("T")]) for r in grid[1:]})
    row = 2
    ws.cell(row, 1, PARAM_BLOCKS[0]).font = Font(name=FONT_SANS, bold=True)
    row += 1
    theo = [("S0", "", "spot"), ("sigma", "par an", "volatilité"), ("r", "continu, par an", ""),
            ("q", "continu, par an", "dividende continu"), ("obs", "", "fréquence d'observation"),
            ("n_paths", "trajectoires", ""), ("seed", "", "LCG Park-Miller"),
            ("rng_method", "", "normales")]
    for name, unit, note in theo:
        _put(ws, row, 1, name)
        _put(ws, row, 2, parse_cell(g[name]), name)
        for j, v in ((3, unit), (5, "p4_grid_cv.csv"), (7, note)):
            _put(ws, row, j, v)
        row += 1
    for name, values in (("K (grille)", Ks), ("T (grille)", Ts)):
        _put(ws, row, 1, name)
        _put(ws, row, 2, " · ".join(f"{v:g}" for v in values))
        _put(ws, row, 5, "p4_grid_cv.csv")
        row += 1
    row += 1
    ws.cell(row, 1, PARAM_BLOCKS[1]).font = Font(name=FONT_SANS, bold=True)
    row += 1
    market = _read(RESULTS / "p5_market.csv")
    for r in market[1:]:
        d = dict(zip(market[0], r))
        _put(ws, row, 1, d["name"])
        _put(ws, row, 2, parse_cell(d["value"]), "value")
        for j, k in ((3, "unit"), (4, "date"), (5, "source"), (6, "convention"), (7, "note")):
            _put(ws, row, j, d[k])
        row += 1
    ws.freeze_panes = "B2"
    _widths(ws, hi=60)


def sheet_data(wb, path: Path) -> None:
    ws = wb.create_sheet(path.stem)
    ws.sheet_properties.tabColor = HEX["a2"]
    rows = _read(path)
    head = rows[0]
    _header(ws, 1, head)
    for i, r in enumerate(rows[1:], start=2):
        for j, (name, text) in enumerate(zip(head, r), start=1):
            _put(ws, i, j, parse_cell(text), name)
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = ws.dimensions
    _widths(ws)


def sheet_figures(wb) -> None:
    ws = wb.create_sheet("Figures")
    ws.sheet_properties.tabColor = HEX["a1"]
    ws.column_dimensions["A"].width = 3
    row = 1
    for png in sorted(FIG_DIR.glob("*.png")):
        c = ws.cell(row, 2, f"{png.stem} — results/figures/{png.name} (et .pdf vectoriel)")
        c.font = Font(name=FONT_SANS, bold=True)
        with Image.open(png) as im:
            w, h = im.size
        img = XLImage(str(png))
        img.width, img.height = IMAGE_WIDTH_PX, round(h * IMAGE_WIDTH_PX / w)
        ws.add_image(img, f"B{row + 1}")
        row += math.ceil(img.height / ROW_PX) + 3


def build(out: Path = OUT) -> Path:
    wb = Workbook()
    wb.properties.creator = "scripts/p5_excel.py"
    csvs = data_csvs()
    sheet_readme(wb, csvs)
    sheet_parameters(wb)
    for path in csvs:
        sheet_data(wb, path)
    sheet_figures(wb)
    out.parent.mkdir(exist_ok=True)
    wb.save(out)
    return out


def main() -> None:
    out = build()
    print(f"{out.relative_to(ROOT)}  {out.stat().st_size:,} octets ; onglets : "
          f"Lisez-moi, Paramètres, {', '.join(p.stem for p in data_csvs())}, Figures")


if __name__ == "__main__":
    main()
