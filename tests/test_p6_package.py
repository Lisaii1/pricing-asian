"""Paquet de rendu au professeur : scripts/p6_package.py → rendu/Projet_Pricing_Asiatique(.zip).

Contrôles (a) à (d) du paquet construit dans un dossier temporaire, avec mutations : un mot
interdit ou un fichier exclu ajoutés au paquet sont détectés.
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p6_package as pk  # noqa: E402


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    return pk.build(tmp_path_factory.mktemp("rendu"))


def test_rendu_folder_is_ignored_by_git():
    assert "rendu/" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_package_layout(built):
    pkg, _archive = built
    top = sorted(p.name for p in pkg.iterdir())
    assert top == ["LISEZMOI.md", "Rapport_Pricing_Asiatique.pdf", "code", "donnees", "resultats"]
    for rel in ("code/src/pricer/asian.py", "code/requirements.txt", "code/pyproject.toml",
                "code/tests/conftest.py", "code/data/raw/MANIFEST.md", "code/results/p3_vr_atm.csv",
                "code/results/figures/rendu/fig1_eventail_eurusd.png", "donnees/MANIFEST.md",
                "resultats/Resultats_Pricing_Asiatique.xlsx",
                "resultats/figures/fig3_gain_efficacite.png", "resultats/p5_eurusd.csv"):
        assert (pkg / rel).is_file(), rel
    for script in pk.SCRIPTS:
        assert (pkg / "code" / "scripts" / script).is_file(), script
    assert sorted(p.name for p in (pkg / "resultats" / "figures").iterdir()) == \
        sorted(p.name for p in pk.RENDU_FIGS.iterdir())


def test_zip_holds_exactly_the_folder(built):
    pkg, archive = built
    files = sorted(f"{pk.NAME}/{p.relative_to(pkg).as_posix()}" for p in pkg.rglob("*")
                   if p.is_file())
    with zipfile.ZipFile(archive) as z:
        assert sorted(z.namelist()) == files
        assert z.testzip() is None


def test_a_no_forbidden_word(built):
    assert pk.check_forbidden(built[0]) == []


def test_b_no_excluded_file(built):
    assert pk.check_excluded(built[0]) == []


def test_d_readme_example_reruns_identically(built):
    assert pk.check_example(built[0])


def test_readme_example_is_an_existing_result_not_a_new_price(built):
    text = (built[0] / "LISEZMOI.md").read_text(encoding="utf-8")
    price = re.search(r"^prix\s+(\S+)$", text, re.M).group(1)
    assert price == f"{float(pk.reference_row()['price']):.4f}"


def test_readme_documents_the_function_and_every_parameter(built):
    text = (built[0] / "LISEZMOI.md").read_text(encoding="utf-8")
    for title in ("## Installation", "## La fonction demandée par le sujet",
                  "## Générateurs disponibles", "## Relancer chaque résultat",
                  "## Lancer les tests"):
        assert title in text, title
    assert "pip install -r requirements.txt" in text and "python -m venv .venv" in text
    for name in ("S0", "K", "sigma", "r", "T", "q", "obs"):
        assert f"| `{name}` |" in text, name
    for method in pk.METHODS:
        assert f'rng_method="{method}"' in text
    for script in pk.SCRIPTS:
        assert f"scripts/{script}" in text
    assert "-> " not in re.search(r"```\n(price_asian\(.*?)\n```", text, re.S).group(1)


def test_every_results_csv_is_produced_by_a_listed_script():
    produced = {o for _s, _a, outs, _n in pk.RERUN for o in outs}
    assert {p.name for p in (ROOT / "results").glob("*.csv")} <= produced


def test_mutation_forbidden_word_and_excluded_file_are_caught(tmp_path):
    pkg = tmp_path / pk.NAME
    (pkg / "code" / "docs").mkdir(parents=True)
    (pkg / "code" / "docs" / "note.md").write_text("vu avec Cowork en P5b", encoding="utf-8")
    (pkg / "code" / "results" / "figures").mkdir(parents=True)
    (pkg / "code" / "results" / "figures" / "fig1.png").write_bytes(b"")
    (pkg / "code" / "CLAUDE.md").write_text("x", encoding="utf-8")
    hits = pk.check_forbidden(pkg)
    assert any("Cowork" in h for h in hits) and any("P5b" in h for h in hits)
    assert any("claude" in h.lower() for h in hits)                       # nom de fichier
    assert sorted(pk.check_excluded(pkg)) == ["code/CLAUDE.md", "code/docs",
                                              "code/docs/note.md", "code/results/figures/fig1.png"]


def test_c_pytest_passes_inside_the_package(built):
    done = pk.run_package_tests(built[0])
    out = done.stdout.decode("utf-8", errors="replace")
    assert done.returncode == 0, out[-3000:]
    assert re.search(r"\d+ passed", out) and "failed" not in out.strip().splitlines()[-1]
