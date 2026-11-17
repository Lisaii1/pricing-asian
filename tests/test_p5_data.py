"""Relevés bruts de data/raw/ (P5a, étape 1) : le MANIFEST décrit exactement les fichiers présents.

Pour chaque ligne du tableau de data/raw/MANIFEST.md : le fichier existe, son sha256 et son nombre de
lignes sont ceux écrits, la première et la dernière date écrites sont bien les dates extrêmes du
fichier. Les deux relevés Alpha Vantage de Cowork y figurent avec leurs sha256 connus. Une source qui
n'a pas répondu est listée « absent », sans fichier. Le journal de tous les appels réseau
(data/raw/fetch_log.csv) est repris dans le MANIFEST.
"""
from __future__ import annotations

import csv
import hashlib
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
MANIFEST = RAW / "MANIFEST.md"
COLUMNS = ["Fichier", "Source", "URL", "Relevé", "sha256", "Lignes", "Première date",
           "Dernière date", "Colonne de date", "Statut"]


def _table():
    text = MANIFEST.read_text(encoding="utf-8").split("## Journal")[0]   # premier tableau seul
    lines = [ln for ln in text.splitlines() if ln.startswith("|")]
    head = [c.strip() for c in lines[0].strip("|").split("|")]
    assert head == COLUMNS
    rows = []
    for ln in lines[2:]:
        cells = [c.strip() for c in ln.strip("|").split("|")]
        rows.append(dict(zip(head, cells)))
    return rows


def _unquote(cell: str) -> str:
    return cell.strip("`")


def _dates(path: Path, column: str):
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        v = r[column]
        out.append(datetime.strptime(v, "%m/%d/%Y").date().isoformat() if "/" in v else v)
    return min(out), max(out)


def test_manifest_lists_both_alpha_vantage_files_with_known_hashes():
    rows = {_unquote(r["Fichier"]): r for r in _table()}
    fx = rows["data/raw/2026-11-17_alphavantage_FX_DAILY_EURUSD_full.csv"]
    ty = rows["data/raw/2026-11-17_alphavantage_TREASURY_YIELD_3month_daily_sample.csv"]
    assert _unquote(fx["sha256"]).startswith("7165537a")
    assert _unquote(ty["sha256"]).startswith("27b7e122")


@pytest.mark.parametrize("row", _table() if MANIFEST.exists() else [],
                         ids=lambda r: _unquote(r["Fichier"]))
def test_manifest_row_matches_file(row):
    if row["Statut"].startswith("absent"):
        assert _unquote(row["sha256"]) in ("", "—")
        return
    path = ROOT / _unquote(row["Fichier"])
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == _unquote(row["sha256"])
    assert data.count(b"\n") == int(row["Lignes"])
    first, last = _dates(path, _unquote(row["Colonne de date"]))
    assert (first, last) == (row["Première date"], row["Dernière date"])


def test_every_raw_file_is_in_manifest():
    listed = {_unquote(r["Fichier"]) for r in _table()}
    present = {f"data/raw/{p.name}" for p in RAW.iterdir()
               if p.name not in ("MANIFEST.md", "fetch_log.csv")}
    assert present <= listed
