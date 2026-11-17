"""Classeur de résultats (P5b, étape 4) : scripts/p5_excel.py → results/pricing_asian_resultats.xlsx.

Onglets « Lisez-moi », « Paramètres », un onglet par CSV de results/ utile au rendu (p2 à p5, hors
détail run par run), « Figures » ; valeurs copiées des CSV (aucune formule), formats numériques,
volets figés ; aucune valeur tapée dans le script.
"""
from __future__ import annotations

import csv
import io
import sys
import tokenize
from pathlib import Path

import pytest
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p5_excel as px  # noqa: E402
from pricer.market import TREASURY_SOURCES  # noqa: E402

RESULTS = ROOT / "results"
XLSX = RESULTS / "pricing_asian_resultats.xlsx"


def _rows(path: Path):
    with path.open(encoding="utf-8") as f:
        return list(csv.reader(f))


def _same(have, want) -> bool:
    """Égalité exacte, sauf flottants : openpyxl écrit "%.16g" (16 chiffres significatifs,
    openpyxl.compat.strings.safe_string), d'où un écart relatif ≤ 5 × 10⁻¹⁶ ; un flottant entier
    (80.0) est écrit « 80 » et relu comme entier, de même valeur."""
    if isinstance(want, float):
        return (isinstance(have, (int, float)) and not isinstance(have, bool)
                and have == pytest.approx(want, rel=1e-15, abs=0))
    return have == want and type(have) is type(want)


@pytest.fixture(scope="module")
def wb():
    return load_workbook(XLSX)


def test_csv_list_is_p2_to_p5_without_run_detail():
    names = [p.name for p in px.data_csvs()]
    assert names == sorted(names)
    assert {"p2_grid.csv", "p3_vr_atm.csv", "p4_grid_cv.csv", "p4_convergence.csv",
            "p5_market.csv", "p5_eurusd.csv", "p5_eurusd_sensitivity.csv"} <= set(names)
    assert not any(n.startswith("p1_") or n.endswith("_runs.csv") for n in names)


def test_sheets(wb):
    stems = [p.stem for p in px.data_csvs()]
    assert wb.sheetnames == ["Lisez-moi", "Paramètres", *stems, "Figures"]


def test_parse_cell():
    assert px.parse_cell("20261117") == 20261117 and isinstance(px.parse_cell("12"), int)
    assert px.parse_cell("0.1") == 0.1
    assert px.parse_cell("") is None
    assert px.parse_cell("True") is True and px.parse_cell("False") is False
    assert px.parse_cell("monthly") == "monthly"
    assert px.parse_cell("0.18 0.16") == "0.18 0.16"
    assert px.parse_cell("inf") == "inf"                      # Excel ne stocke pas l'infini


def test_data_sheets_copy_csv_values_exactly(wb):
    for path in px.data_csvs():
        ws = wb[path.stem]
        rows = _rows(path)
        got = [[c.value for c in r] for r in ws.iter_rows(min_row=1, max_row=len(rows),
                                                          max_col=len(rows[0]))]
        assert got[0] == rows[0], path.name
        for want, have in zip(rows[1:], got[1:]):
            bad = [(w, h) for w, h in zip(want, have) if not _same(h, px.parse_cell(w))]
            assert bad == [], path.name
        assert ws.max_row == len(rows)
        assert ws.freeze_panes == "B2"


def test_no_formula_anywhere(wb):
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                assert c.data_type != "f", (ws.title, c.coordinate)
                assert not (isinstance(c.value, str) and c.value.startswith("=")), (ws.title,
                                                                                    c.coordinate)


def test_number_formats(wb):
    ws = wb["p3_vr_atm"]
    col = {c.value: i + 1 for i, c in enumerate(ws[1])}
    assert ws.cell(2, col["price"]).number_format == "0.0000"
    assert ws.cell(2, col["std_error"]).number_format == px.ERR_FORMAT
    assert ws.cell(2, col["seed"]).number_format == "0"
    assert ws.cell(2, col["efficiency_gain_vs_plain"]).number_format == "#,##0.0"
    assert ws.cell(2, col["time_median_s"]).number_format == "0.000"
    assert px.ERR_FORMAT == "[<0.0001]0.0E+00;0.0000"           # Q5 : scientifique sous 10^-4
    ws = wb["p5_eurusd"]
    col = {c.value: i + 1 for i, c in enumerate(ws[1])}
    assert ws.cell(2, col["asian_std_error"]).number_format == px.ERR_FORMAT
    assert ws.cell(2, col["asian_price"]).number_format == "0.0000"


def test_readme_has_method_sources_seed(wb):
    text = "\n".join(str(c.value) for row in wb["Lisez-moi"].iter_rows() for c in row if c.value)
    assert "20261117" in text                                    # seed (lue dans les CSV)
    for url in TREASURY_SOURCES:
        assert url in text
    manifest = (ROOT / "data" / "raw" / "MANIFEST.md").read_text(encoding="utf-8")
    for line in manifest.splitlines():
        if line.startswith("| `data/raw/"):
            assert line.split("|")[3].strip() in text
    assert len(px.METHOD) == 10
    for line in px.METHOD:
        assert line in text


def test_parameters_sheet(wb):
    blocks, current = {}, None
    for row in wb["Paramètres"].iter_rows(values_only=True):
        if row[0] in px.PARAM_BLOCKS:
            current = blocks.setdefault(row[0], {})
        elif current is not None and row[0] is not None:
            current.setdefault(row[0], row[1])
    theo, real = (blocks[b] for b in px.PARAM_BLOCKS)
    market = {r[0]: r for r in _rows(RESULTS / "p5_market.csv")[1:]}
    for name in market:
        assert _same(real[name], px.parse_cell(market[name][1])), name
    grid = _rows(RESULTS / "p4_grid_cv.csv")
    first = dict(zip(grid[0], grid[1]))
    for k in ("S0", "sigma", "r", "q", "n_paths", "seed"):
        assert _same(theo[k], px.parse_cell(first[k])), k


def test_figures_sheet_has_every_png(wb):
    pngs = sorted((RESULTS / "figures").glob("*.png"))
    assert len(pngs) >= 8
    assert len(wb["Figures"]._images) == len(pngs)


def test_no_hardcoded_values_in_excel_script():
    src = (ROOT / "scripts" / "p5_excel.py").read_text(encoding="utf-8")
    assert "20261117" not in src
    bad = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type != tokenize.NUMBER:
            continue
        text = tok.string.replace("_", "")
        if any(c in text for c in ".eE"):
            digits = text.lower().split("e")[0].replace(".", "").lstrip("0")
            if len(digits.rstrip("0")) > 2:
                bad.append((tok.start[0], tok.string))
        elif int(text, 0) >= 1000:
            bad.append((tok.start[0], tok.string))
    assert bad == []
