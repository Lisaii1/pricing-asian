"""Classeur version professeur : scripts/p6_excel_prof.py → results/Resultats_Pricing_Asiatique.xlsx.

Onglets attendus, valeurs recopiées des CSV (aucune formule), gains à l'ordre de grandeur identiques
au tableau 1 du rapport, en-têtes en français, aucun mot de l'outillage de travail ni nom de
fichier CSV, Alpha Vantage cité comme convenu, figures du mode rendu insérées.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import pytest
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p5_excel as px  # noqa: E402
import p6_build as pb  # noqa: E402
import p6_excel_prof as xp  # noqa: E402

RESULTS = ROOT / "results"
BY_NAME = {v: k for k, v in xp.ESTIMATORS.items() if k != "control"}


@pytest.fixture(scope="module")
def wb():
    return load_workbook(xp.OUT)


def _rows(name):
    with (RESULTS / name).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _strings(book):
    for ws in book.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str):
                    yield ws.title, c.coordinate, c.value


def _bad(value: str) -> bool:
    return bool(pb.forbidden_hits(value)
                or re.search(r"\bp\d_\w+\.csv|historique/|\bseed\b", value, re.I))


def test_group_workbook_is_kept_and_new_one_exists():
    assert xp.OUT.name == "Resultats_Pricing_Asiatique.xlsx" and xp.OUT.is_file()
    assert (RESULTS / "pricing_asian_resultats.xlsx").is_file()


def test_sheets(wb):
    assert wb.sheetnames == ["Synthèse", "Paramètres et sources", *(a[0] for a in xp.ANNEXES)]
    assert all(len(name) <= 31 for name in wb.sheetnames)


def test_no_formula_anywhere(wb):
    assert [(t, c) for t, c, v in _strings(wb) if v.startswith("=")] == []


def test_no_tooling_word_no_csv_file_name_no_seed_word(wb):
    assert [(t, c, v[:60]) for t, c, v in _strings(wb) if _bad(v)] == []
    assert not any(_bad(name) for name in wb.sheetnames)


def test_forbidden_scan_catches_a_planted_word():
    """Mutation : un mot interdit écrit dans une cellule est vu par le contrôle."""
    book = load_workbook(xp.OUT)
    book["Synthèse"]["A300"] = "vu avec Cowork, p4_grid_cv.csv"
    assert [v for _t, _c, v in _strings(book) if _bad(v)] == ["vu avec Cowork, p4_grid_cv.csv"]


def test_alpha_vantage_cited_as_agreed(wb):
    texts = [v for _t, _c, v in _strings(wb)]
    assert "Alpha Vantage, API FX_DAILY et TREASURY_YIELD, relevé du 17/11/2026" in texts


def test_sources_have_url_and_date(wb):
    ws = wb["Paramètres et sources"]
    cells = [c.value for row in ws.iter_rows() for c in row if isinstance(c.value, str)]
    urls = [v for v in cells if v.startswith("https://")]
    for host in ("data-api.ecb.europa.eu", "home.treasury.gov", "federalreserve.gov",
                 "alphavantage.co"):
        assert any(host in u for u in urls), host
    dates = [v for v in cells if re.fullmatch(r"\d{2}/\d{2}/\d{4}( \d{2}:\d{2})?", v)]
    assert len(dates) >= 6


def _synthesis_table(ws, first: str, second: str):
    """Lignes du tableau de la synthèse dont l'en-tête commence par (first, second)."""
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row):
        if row[0].value == first and row[1].value == second:
            out, r = [], row[0].row + 1
            while ws.cell(r, 1).value is not None and ws.cell(r, 2).value is not None:
                out.append([ws.cell(r, j).value for j in range(1, 11)])
                r += 1
            return out
    raise AssertionError(f"tableau {first} / {second} absent")


def test_q1_prices_are_the_csv_values_with_se_ci_n_seed(wb):
    table = _synthesis_table(wb["Synthèse"], "Option", "Estimateur")
    rows = [r for r in _rows("p3_vr_atm.csv") if float(r["T"]) == 1]
    assert len(table) == 4
    for line in table:
        r = next(x for x in rows if x["option"] == line[0] and x["estimator"] == BY_NAME[line[1]])
        assert line[2:6] == pytest.approx([float(r[k]) for k in
                                           ("price", "std_error", "ci_low", "ci_high")], rel=1e-15)
        assert line[6:8] == [int(r["n_paths"]), int(r["seed"])]


def test_q3_efficiency_is_the_order_of_magnitude_of_report_table_1(wb):
    table = _synthesis_table(wb["Synthèse"], "Estimateur", "Call")
    fields = pb.fields()
    tok = {"plain": "sans", "antithetic": "anti", "control_beta_1": "ctrl1",
           "control_beta_optimal": "ctrl", "antithetic_control": "antictrl"}
    assert len(table) == 5
    for line in table:
        est = BY_NAME[line[0]]
        assert pb.og(line[7]) == fields[f"vr_call_T1_{tok[est]}_gain_env"].text, est


def test_og_value_matches_the_report_rounding():
    for v in (1401.9, 2426.85, 635.8, 3.31, 1.0, 9611.0, 9.96):
        assert pb.og(xp.og_value(v)) == pb.og(v)


def test_annexes_copy_the_csv_columns_with_french_headers(wb):
    for name, csv_name, columns in xp.ANNEXES:
        ws = wb[name]
        header = [c.value for c in ws[1]]
        assert header == [fr for _c, fr in columns], name
        assert all("_" not in h for h in header), name
        rows = _rows(csv_name)
        assert ws.max_row == len(rows) + 1, name
        for i, r in enumerate(rows, start=2):
            for j, (col, _fr) in enumerate(columns, start=1):
                want = px.parse_cell(r[col])
                if isinstance(want, (int, float)) and not isinstance(want, bool):
                    assert ws.cell(i, j).value == pytest.approx(want, rel=1e-15), (name, col, i)


def test_annex_number_formats_are_those_of_the_group_workbook(wb):
    ws = wb["A4 Réduction de variance"]
    header = [c.value for c in ws[1]]
    assert ws.cell(2, header.index("Prix") + 1).number_format == "0.0000"
    assert ws.cell(2, header.index("Écart-type") + 1).number_format == px.ERR_FORMAT
    assert ws.cell(2, header.index("Temps médian (s)") + 1).number_format == "0.000"
    assert ws.cell(2, header.index("Graine") + 1).number_format == "0"


def test_synthesis_has_the_rendu_figures(wb):
    assert len(wb["Synthèse"]._images) == 6
    assert xp.FIG_DIR == RESULTS / "figures" / "rendu"


def test_workbook_regenerates_with_the_same_cells(tmp_path, wb):
    other = load_workbook(xp.build(tmp_path / "x.xlsx"))
    for ws in wb.worksheets:
        a = [[c.value for c in row] for row in ws.iter_rows()]
        b = [[c.value for c in row] for row in other[ws.title].iter_rows()]
        assert a == b, ws.title


def test_no_result_is_typed_in_the_script():
    """Aucun flottant à plus de 2 chiffres significatifs, aucune graine tapée."""
    src = (ROOT / "scripts" / "p6_excel_prof.py").read_text(encoding="utf-8")
    assert "20261117" not in src
    floats = re.findall(r"(?<![\w.])\d+\.\d+(?![\w.])", src)
    assert [f for f in floats if len(f.replace(".", "").strip("0")) > 2] == []
