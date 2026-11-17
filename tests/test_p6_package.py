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


def test_readme_lists_the_six_course_typos_one_line_each(built):
    """Le rapport renvoie au LISEZMOI pour les coquilles du cours : la section doit y être."""
    text = (built[0] / "LISEZMOI.md").read_text(encoding="utf-8")
    section = text.split("## Coquilles relevées dans le support de cours", 1)[1]
    rows = [line for line in section.splitlines() if line.startswith("| ")][1:]
    assert [r.split(" | ")[0].lstrip("| ").split(",")[0] for r in rows] ==         ["9", "23", "24", "24", "76", "76"]
    assert all(r.count(" | ") == 2 for r in rows)          # slide, ce qui est écrit, forme correcte
    assert "V = 2U − 1" in section and "1 + d1 t + d2 t² + d3 t³" in section


def test_report_points_to_the_readme_not_to_an_oral_defence():
    """Pas de soutenance prévue : le rapport renvoie à un document qui est dans le rendu."""
    for name in ("rapport_template.html", "rapport.html"):
        html = (ROOT / "rapport" / name).read_text(encoding="utf-8")
        assert "soutenance" not in html.lower(), name
        assert "sont détaillées dans le LISEZMOI du code." in html, name


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


# --- paquet pour l'équipe (--equipe) ---------------------------------------------------------------

EQUIPE_ORDER = ["0_LISEZ-MOI_EQUIPE.pdf", "1_Dossier_Groupe.pdf", "2_Oral.pdf", "3_Conformite.pdf",
                "4_Rapport_rendu.pdf", "5_Resultats.xlsx", "figures"]


@pytest.fixture(scope="module")
def equipe(tmp_path_factory):
    if pk.pb.find_browser() is None:
        pytest.skip("ni Chrome ni Edge : LISEZ-MOI non produit")
    out = tmp_path_factory.mktemp("equipe")
    return out, *pk.build_equipe(out, n_tests=704)


def test_equipe_content_and_reading_order(equipe):
    out, pkg, archive = equipe
    assert sorted(p.name for p in out.iterdir()) == [pk.EQUIPE, f"{pk.EQUIPE}.zip"]  # rien d'autre
    assert sorted(p.name for p in pkg.iterdir()) == EQUIPE_ORDER
    figs = sorted(p.name for p in (pkg / "figures").iterdir())
    assert figs == sorted(p.name for p in pk.RENDU_FIGS.glob("*.png")) and len(figs) == 8
    for name, src in pk.equipe_files():
        assert (pkg / name).read_bytes() == src.read_bytes(), name
    assert pk.REPORT in [s for _n, s in pk.equipe_files()]          # le PDF rendu, tel quel


def test_equipe_zip_opens_and_holds_exactly_the_folder(equipe):
    _out, pkg, archive = equipe
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        names = sorted(z.namelist())
    assert names == sorted(f"{pk.EQUIPE}/{p.relative_to(pkg).as_posix()}"
                           for p in pkg.rglob("*") if p.is_file())
    listing = pk.equipe_listing(pkg, archive)
    size = f"{archive.stat().st_size:,}".replace(",", " ")
    assert listing.splitlines()[-1] == f"{archive.name} : {size} octets"     # taille rapportée
    assert listing.splitlines()[0].startswith("0_LISEZ-MOI_EQUIPE.pdf") and ", 1 p.)" in listing


def test_equipe_readme_one_page_github_steps_and_no_tooling_word(equipe):
    _out, pkg, _archive = equipe
    readme = pkg / "0_LISEZ-MOI_EQUIPE.pdf"
    assert pk.pb.pdf_page_count(readme) == 1
    try:
        texts = {n: pk.pb.pdf_text(pkg / n) for n in ("0_LISEZ-MOI_EQUIPE.pdf", "2_Oral.pdf",
                                                       "3_Conformite.pdf")}
    except FileNotFoundError:
        pytest.skip("pdftotext introuvable")
    for name, text in texts.items():
        assert pk.forbidden_hits(text) == [], name
    flat = re.sub(r"\s+", " ", texts["0_LISEZ-MOI_EQUIPE.pdf"])
    for step in ("Accepter l'invitation reçue par mail", f"git clone {pk.GITHUB}", "cd pricing-asian",
                 "python -m venv .venv", r".venv\Scripts\pip install -r requirements.txt",
                 r".venv\Scripts\python -m pytest -q", "704 passed", f"{pk.NAME}.zip"):
        assert step in flat, step
    for name in EQUIPE_ORDER[1:]:                         # il ne se cite pas lui-même
        assert name in flat, name


def test_count_tests_reads_the_pytest_collection():
    assert pk.count_tests() > 700
