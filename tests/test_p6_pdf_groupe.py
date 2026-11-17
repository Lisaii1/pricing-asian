"""PDF de travail du groupe (scripts/p6_pdf_groupe.py) : l'oral en fiches, la grille, le dossier.

Le convertisseur Markdown maison est testé sur le Markdown de nos documents ; les PDF versionnés
sont relus (nombre de pages, texte, images) sans relancer Chrome. L'oral et la grille sont sans mot
de l'outillage, comme les documents rendus.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p6_build as pb  # noqa: E402
import p6_package as pk  # noqa: E402
import p6_pdf_groupe as pg  # noqa: E402


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace(" ", " ")).strip()


def _pdf_text(pdf: Path) -> str:
    try:
        return pb.pdf_text(pdf)
    except FileNotFoundError:
        pytest.skip("pdftotext introuvable")


# --- le convertisseur ----------------------------------------------------------------------------

def test_parse_blocks_of_our_markdown():
    md = ("# Titre\n\nUn paragraphe\nsur deux lignes : 1 000\n91. ne commence pas une liste.\n\n"
          "- point un\n  suite du point\n- point deux\n\n1. premier\n   suite\n2. second\n\n"
          "| A | B |\n|---|---|\n| x | y |\n\n![Figure](img.png)\n\n```powershell\npytest\n```\n\n---\n")
    kinds = [b.kind for b in pg.parse(md)]
    assert kinds == ["h", "p", "ul", "ol", "table", "img", "code", "hr"]
    blocks = pg.parse(md)
    assert blocks[1].text == "Un paragraphe sur deux lignes : 1 000 91. ne commence pas une liste."
    assert blocks[2].items == ["point un suite du point", "point deux"]
    assert blocks[3].items == ["premier suite", "second"]
    assert blocks[4].rows == [["A", "B"], ["x", "y"]]
    assert (blocks[5].text, blocks[5].src) == ("Figure", "img.png")
    assert (blocks[6].text, blocks[6].src) == ("pytest", "powershell")


def test_inline_markup_and_link_policy(tmp_path):
    ctx = pg.Ctx(tmp_path)
    html = pg.inline("**gras** et *italique*, `a < b` ; [grille](CONFORMITE.md), "
                     "[ancre](#a-b) et [site](https://example.org)", ctx)
    assert "<strong>gras</strong>" in html and "<em>italique</em>" in html
    assert "<code>a &lt; b</code>" in html
    assert '<span class="ref">grille</span>' in html            # fichier local : texte seul
    assert '<a href="#a-b">ancre</a>' in html and '<a href="https://example.org">' in html
    assert pg.inline("`results/*.csv` et 2 * 3", ctx) == "<code>results/*.csv</code> et 2 * 3"


def test_slug_is_the_github_anchor_used_in_our_summaries():
    assert pg.slug("2. Ce qu'on a fait, étape par étape") == "2-ce-quon-a-fait-étape-par-étape"
    assert pg.slug("A. Ce que le sujet demande") == "a-ce-que-le-sujet-demande"


def test_missing_image_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        pg.inline("![x](absente.png)", pg.Ctx(tmp_path))


def test_numbers_are_marked_outside_tags_only():
    out = pg.mark_numbers('<b class="x2">5,3242</b> ± 0,0009 et 2 447 439')
    assert '<b class="x2">' in out
    assert out.count('<span class="n">') == 3


# --- l'oral : gabarit et fiches --------------------------------------------------------------------

ORAL = ROOT / "docs" / "ORAL.md"
PARTS = 8


@pytest.fixture(scope="module")
def oral():
    md = ORAL.read_text(encoding="utf-8")
    _head, secs = pg.sections(pg.parse(md))
    parts = [(h, b) for h, b in secs
             if not h.text.startswith(("Questions probables", "Les 10 chiffres"))]
    q_sec = next(b for h, b in secs if h.text.startswith("Questions probables"))
    _intro, questions = pg.parse_questions(q_sec)
    chiffres = next(b for h, b in secs if h.text.startswith("Les 10 chiffres"))
    return md, [pg.parse_fiche(h, b) for h, b in parts], questions, chiffres


def test_oral_has_one_fiche_per_part_with_speaker_points_and_number(oral):
    _md, fiches, questions, _c = oral
    assert len(fiches) == PARTS
    numbers = {n for n, _t, _b in questions}
    for f in fiches:
        assert f.who == "[à attribuer]", f.title
        assert 3 <= len(f.dire) <= 5, f.title
        assert sum("**" in p for p in f.dire) >= 2, f.title          # mots-clés en gras
    six = [f for f in fiches if f.title not in ("Ouverture", "Conclusion")]
    assert len(six) == 6
    for f in six:
        assert f.retenir, f.title
        assert 1 <= len(f.demande) <= 2 and set(f.demande) <= numbers, f.title
    assert [len(f.images) for f in six] == [1, 1, 2, 2, 2, 0]
    assert all("/rendu/" in b.src for f in six for b in f.images)


def test_oral_speakers_are_fields_left_visible(oral):
    md = oral[0]
    tpl = (ROOT / "docs" / "templates" / "ORAL.md").read_text(encoding="utf-8")
    assert len(re.findall(r"\{\{orateur_\w+\}\}", tpl)) == 2 * PARTS      # déroulé + chaque fiche
    assert md.count("[à attribuer]") == 2 * PARTS
    assert set(pb.ORATEURS) == {"ouverture", "q1", "q2", "q3", "q4", "eurusd", "plus", "conclusion"}


def test_oral_ten_numbers_table(oral):
    rows = next(b for b in oral[3] if b.kind == "table").rows
    assert rows[0] == ["Chiffre", "Ce qu'il veut dire", "D'où il vient"]
    assert len(rows) == 1 + 10 and all(len(r) == 3 and all(r) for r in rows)
    f = pb.fields()
    assert rows[1][0] == f"{f['vr_call_T1_ctrl_prix'].text} ± {f['vr_call_T1_ctrl_demi'].text}"


def test_questions_two_or_three_per_page(oral):
    pages = pg.qr_pages(oral[2])
    assert sum(len(p) for p in pages) == len(oral[2]) == 20
    assert all(2 <= len(p) <= 3 for p in pages[:-1]) and 1 <= len(pages[-1]) <= 3


@pytest.fixture(scope="module")
def oral_html():
    return pg.build_html(ORAL, pg.oral_html)


def test_oral_html_has_no_tooling_word_and_loads_only_local_figures(oral_html):
    assert pb.forbidden_hits(pb.visible_text(oral_html, "x.html")) == []
    srcs = re.findall(r'<img src="([^"]+)"', oral_html)
    assert len(srcs) == 8 and all(s.startswith("file:///") and "/figures/rendu/" in s for s in srcs)
    assert re.findall(r"""(?:src|href)=["']https?:""", oral_html) == []
    assert oral_html.count('class="fiche"') == PARTS
    assert oral_html.count('class="box"') + oral_html.count('class="box band"') == 6


def test_oral_pdf_pages_text_and_images(oral):
    pdf = pg.ORAL_PDF
    assert pdf.is_file()
    expected = 1 + PARTS + len(pg.qr_pages(oral[2])) + 1       # garde, fiches, questions, chiffres
    assert pb.pdf_page_count(pdf) == expected
    text = _pdf_text(pdf)
    flat = _flat(text)
    assert pb.forbidden_hits(text) == []
    f = pb.fields()
    for name in ("vr_call_T1_ctrl_prix", "nreq_sans_eps01", "fx_spot_call_prix", "ratio_call_K100_T1",
                 "vr_call_T1_ctrl_corr"):
        assert _flat(f[name].text) in flat, name               # le PDF suit le .md courant
    for n, title, _b in oral[2]:
        assert _flat(re.sub(r"[`*]", "", title)) in flat, n
    assert "[à attribuer]" in flat and "Les 10 chiffres à connaître par cœur" in flat
    assert len(re.findall(rb"/Subtype\s*/Image", pdf.read_bytes())) >= 8


# --- hors du paquet de rendu -----------------------------------------------------------------------

def test_group_pdfs_and_their_code_stay_out_of_the_rendu_package():
    shipped = {rel for _src, rel in pk.code_sources()}
    assert not any("p6_pdf_groupe" in rel or rel.startswith("docs/") for rel in shipped)
    assert "p6_pdf_groupe.py" in pk.EXCLUDED_NAMES and "test_p6_pdf_groupe.py" in pk.EXCLUDED_TESTS
    assert "docs" in pk.EXCLUDED_PARTS


# --- la grille de conformité -----------------------------------------------------------------------

CONF = ROOT / "docs" / "CONFORMITE.md"


@pytest.fixture(scope="module")
def conf_html():
    return pg.build_html(CONF, pg.conformite_html)


def _conf_rows(part: str) -> list[list[str]]:
    _head, secs = pg.sections(pg.parse(CONF.read_text(encoding="utf-8")))
    body = next(b for h, b in secs if h.text.startswith(part))
    return [r for t in body if t.kind == "table" for r in t.rows[1:]]


def test_conformite_html_pills_cards_checklist(conf_html):
    rows_a, rows_b = _conf_rows("A. "), _conf_rows("B. ")
    pills = re.findall(r'<span class="pill (ok|part|no)">', conf_html)
    assert len(pills) == len(rows_a) == 15
    expected = [next(v for k, v in pg.STATUS.items() if k in r[1]) for r in rows_a]
    assert pills == expected                                   # couleur = statut de la ligne
    assert conf_html.count('class="card"') == len(rows_b) == 19
    assert conf_html.count("À l'oral") == len(rows_b)
    assert '<ul class="todo">' in conf_html and 'class="part land"' in conf_html
    assert pb.forbidden_hits(pb.visible_text(conf_html, "x.html")) == []


def test_conformite_pdf_landscape_part_a_and_text():
    pdf = pg.CONF_PDF
    raw = pdf.read_bytes()
    boxes = [tuple(round(float(x)) for x in m.groups())
             for m in re.finditer(rb"/MediaBox\s*\[\s*0 0 ([\d.]+) ([\d.]+)\s*\]", raw)]
    assert any(w > h for w, h in boxes) and any(w < h for w, h in boxes)   # paysage et portrait
    text = _pdf_text(pdf)
    flat = _flat(text)
    assert pb.forbidden_hits(text) == []
    for r in _conf_rows("B. "):                     # deux colonnes de cartes : -layout les
        start = " ".join(re.sub(r"[`*]", "", r[0]).split()[:3])     # entrelace, d'où 3 mots
        assert start in flat, r[0]
    assert "Ce qui reste à faire" in flat and "Bilan" in flat
    assert pb.pdf_page_count(pdf) >= 5


# --- le dossier du groupe ---------------------------------------------------------------------------

DOSSIER = ROOT / "docs" / "DOSSIER_GROUPE.md"


@pytest.fixture(scope="module")
def dossier_html():
    return pg.build_html(DOSSIER, pg.dossier_html)


def test_dossier_toc_links_every_section_step_and_figure(dossier_html):
    toc = re.search(r'<nav class="toc">(.*?)</nav>', dossier_html, re.S).group(1)
    targets = re.findall(r'href="#([^"]+)"', toc)
    ids = set(re.findall(r'\bid="([^"]+)"', dossier_html))
    assert targets and set(targets) <= ids
    md = DOSSIER.read_text(encoding="utf-8")
    assert len(targets) == len(re.findall(r"^#{2,3} ", md, re.M))       # chaque ## et ###
    steps = re.findall(r'<h3 class="step" id="[^"]+">(P\d[ab]?)\b', dossier_html)
    assert steps == ["P1", "P2", "P3", "P4", "P5a", "P5b", "P6"]          # une page chacune


def test_dossier_figures_with_their_explanations_and_glossary(dossier_html):
    figs = re.findall(r'<div class="fig" id="[^"]+">(.*?)</div>', dossier_html, re.S)
    assert len(figs) == 8                                    # 6 figures et 2 tableaux
    for f in figs:
        assert f.count("<img ") == 1 and f.count("<li>") == 2      # « on voit », « ça veut dire »
        assert "/results/figures/" in f
    gloss = re.search(r'<div class="gloss">(.*?)</div>', dossier_html, re.S).group(1)
    assert gloss.count("<p>") == len(re.findall(r"^\*\*", DOSSIER.read_text(encoding="utf-8")
                                                .split("## 8. Glossaire")[1], re.M)) == 17


def test_dossier_pdf_has_clickable_summary_and_its_text():
    pdf = pg.DOSSIER_PDF
    raw = pdf.read_bytes()
    md = DOSSIER.read_text(encoding="utf-8")
    assert len(re.findall(rb"/Subtype\s*/Link", raw)) >= len(re.findall(r"^#{2,3} ", md, re.M))
    assert len(re.findall(rb"/Subtype\s*/Image", raw)) >= 8
    flat = _flat(_pdf_text(pdf))
    for title in ("En une page", "Les 6 coquilles du cours", "Glossaire", "Carte du dépôt"):
        assert title in flat, title
    f = pb.fields()
    assert _flat(f["vr_call_T1_ctrl_ratio"].text) in flat
    assert pb.pdf_page_count(pdf) >= 15
