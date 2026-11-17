"""Dossier du groupe, texte de l'oral et rapport (P6) : scripts/p6_build.py.

Règle des chiffres : les textes sont des gabarits à champs {{nom}} ; aucun nombre décimal n'est
tapé dans un gabarit, chaque champ vient d'un CSV de results/ (ou de CLAUDE.md / requirements.txt
pour les décisions et les versions). Les fichiers produits se régénèrent à l'identique.

Documents rendus au professeur (docs/ORAL.md, rapport/*.html, texte du PDF) : aucun mot de
l'outillage de travail (décision de Loup, 17/11/2026, 19:19).
"""
from __future__ import annotations

import csv
import io
import re
import subprocess
import sys
import tokenize
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p6_build as pb  # noqa: E402
from pricer.plotstyle import fmt_err, fmt_int, fmt_num  # noqa: E402

RESULTS = ROOT / "results"
OUTPUTS = sorted(pb.DOCUMENTS)
RENDUS = sorted(pb.RENDUS)
NAMES = ["Zoe HUBERT", "Arthur LOURENCO", "Matthieu DEHNEL", "Pierre DUPLESSIS",
         "Charlotte PONTCHATEAU", "Thomas GALLOIS", "Sacha BEAUQUESNES"]


def _rows(name: str) -> list[dict]:
    with (RESULTS / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _one(file: str, /, **where) -> dict:
    hits = [r for r in _rows(file)
            if all(r[k] == v if isinstance(v, str) else float(r[k]) == float(v)
                   for k, v in where.items())]
    assert len(hits) == 1, (file, where, len(hits))
    return hits[0]


@pytest.fixture(scope="module")
def fields():
    return pb.fields()


@pytest.fixture(scope="module")
def rendered():
    return pb.render_all()


# --- la mécanique des champs ---------------------------------------------------------------------

def test_render_replaces_fields_and_refuses_unknown_ones():
    table = {"a": pb.Field("a", "1,5", "test")}
    text, used = pb.render("x = {{a}} ; y = {{ a }}", table)
    assert text == "x = 1,5 ; y = 1,5" and used == ["a"]
    with pytest.raises(KeyError, match="inconnu"):
        pb.render("{{absent}}", table)


def test_decimal_detector():
    assert pb.decimals("prix 5,3242 ; pente −0.50 ; N = 200 000 ; slide 77 ; 17/11/2026 ; "
                       "4,2 × 10⁻⁷") == ["5,3242", "0.50", "4,2"]
    assert pb.decimals("Python 3.13.1") == ["3.13"]
    assert pb.decimals("aucun chiffre : A4, K = 100, 10^-4") == []


def test_visible_text_of_html_ignores_style_and_script_but_keeps_alt():
    html = ('<html><head><style>p{font:12.5px x}</style><title>T 1,5</title></head><body>'
            '<!-- 9,9 --><p class="a">prix 2,5</p><img alt="fig 3,5" src="a.png">'
            '<script>var x=4.5</script></body></html>')
    assert pb.decimals(pb.visible_text(html, "x.html")) == ["1,5", "2,5", "3,5"]
    assert pb.visible_text("a 1,5", "x.md") == "a 1,5"


@pytest.mark.parametrize("value, text", [
    (1349.6, "1 300"), (1454.2, "1 500"), (2426.8, "2 400"), (9611.0, "9 600"), (409.13, "410"),
    (3.28, "3,3"), (0.3126, "0,31"), (9.96, "10"), (0.0996, "0,10"), (37.0, "37"), (0.0, "0"),
])
def test_order_of_magnitude_is_two_significant_digits(value, text):
    assert pb.og(value).replace(" ", " ") == text


def test_signed_and_dates():
    assert pb.signed(1.0039, 2) == "+1,00" and pb.signed(-1.4531, 2) == "−1,45"
    assert pb.fr_date("2026-11-17") == "17/11/2026"


# --- les champs viennent des CSV ----------------------------------------------------------------

def test_every_field_has_a_text_and_a_source(fields):
    assert len(fields) > 300
    for f in fields.values():
        assert f.text.strip() and f.source.strip(), f.name
        assert not re.search(r"\b(nan|inf)\b", f.text.lower()), (f.name, f.text)


def test_fields_match_the_csv_read_independently(fields):
    """Relecture indépendante (csv.DictReader, sans passer par p6_build) de champs de chaque CSV."""
    t = fields
    r = _one("p3_vr_atm.csv", T=1, option="call", estimator="control_beta_optimal")
    assert t["vr_call_T1_ctrl_prix"].text == fmt_num(float(r["price"]), 4)
    assert t["vr_call_T1_ctrl_se"].text == fmt_err(float(r["std_error"]))
    assert t["vr_call_T1_ctrl_ratio"].text == fmt_int(float(r["var_ratio_vs_plain"]))
    assert t["vr_call_T1_ctrl_gain"].text == fmt_int(float(r["efficiency_gain_vs_plain"]))
    assert "p3_vr_atm.csv" in t["vr_call_T1_ctrl_prix"].source

    r = _one("p2_grid.csv", K=100, T=1, option="call")
    assert t["p2_call_T1_asiat"].text == fmt_num(float(r["asian_price"]), 4)
    assert t["p2_call_T1_bs"].text == fmt_num(float(r["euro_bs_price"]), 4)

    r = _one("p4_grid_cv.csv", K=100, T=1, option="call")
    assert t["ratio_call_K100_T1"].text == fmt_num(float(r["ratio"]), 2)
    assert t["ratio_call_K100_T1_4"].text == fmt_num(float(r["ratio"]), 4)
    assert t["th_sigma"].text == fmt_num(float(r["sigma"]), 2)
    assert t["seed"].text == r["seed"] == "20261117"

    r = _one("p4_convergence_slopes.csv", estimator="plain")
    assert t["pente_sans"].text == fmt_num(float(r["slope"]), 4)
    assert t["pente_theo"].text == fmt_num(float(r["expected_slope"]), 1)

    r = _one("p4_n_required.csv", estimator="control", epsilon=0.01)
    assert t["nreq_ctrl_eps01"].text == fmt_int(float(r["n_required"]))
    assert t["eps_01"].text == "0,01"

    r = _one("p4_beta_bias.csv", beta_mode="pilot")
    assert t["biais_pilot_sd"].text == pb.signed(float(r["bias_in_sd_of_mean"]), 2) == "−1,45"
    assert t["biais_runs"].text == fmt_int(float(r["n_seeds"]))

    r = _one("p5_market.csv", name="S0")
    assert t["fx_S0"].text == fmt_num(float(r["value"]), 4)
    assert t["fx_S0_date"].text == pb.fr_date(r["date"])

    r = _one("p5_eurusd.csv", strike_type="spot", option="call")
    assert t["fx_spot_call_prix"].text == fmt_num(float(r["asian_price"]), 4)
    assert t["fx_spot_call_se"].text == fmt_err(float(r["asian_std_error"]))
    half = (float(r["asian_ci_high"]) - float(r["asian_ci_low"])) / 2
    assert t["fx_spot_call_demi"].text == fmt_err(half)
    assert t["fx_spot_prime_eur"].text == fmt_int(float(r["hedge_cost_eur"]))

    r = _one("p1_rng_diagnostics.csv", method="acceptance_rejection")
    assert t["p1_rejet_unif"].text == fmt_num(float(r["uniforms_per_normal"]), 2)


def test_rounding_rules_of_the_lot(fields):
    """Prix à 10^-4 ; écarts-types sous 10^-4 en notation scientifique à 2 chiffres ; gains
    d'efficacité à l'ordre de grandeur (2 chiffres significatifs, moyenne des deux mesures)."""
    assert re.fullmatch(r"\d,\d{4}", fields["vr_call_T1_ctrl_prix"].text)
    assert re.fullmatch(r"\d,\d × 10⁻⁷", fields["fx_spot_call_se"].text)
    now = float(_one("p3_vr_atm.csv", T=1, option="call",
                     estimator="control_beta_optimal")["efficiency_gain_vs_plain"])
    before = float(next(r for r in pb.history("p3_vr_atm_mesure1.csv")
                        if float(r["T"]) == 1 and r["option"] == "call"
                        and r["estimator"] == "control_beta_optimal")["efficiency_gain_vs_plain"])
    assert fields["vr_call_T1_ctrl_gain_env"].text == pb.og((now + before) / 2)
    assert fields["vr_call_T1_ctrl_gain_env"].text.replace(" ", " ") == "1 400"
    assert fields["vr_call_T1_ctrl_gain1"].text == fmt_int(before)


def test_dispersion_between_the_two_time_measurements(fields):
    now = {(r["T"], r["option"], r["estimator"]): float(r["efficiency_gain_vs_plain"])
           for r in _rows("p3_vr_atm.csv")}
    rel = [now[(r["T"], r["option"], r["estimator"])] / float(r["efficiency_gain_vs_plain"]) - 1
           for r in pb.history("p3_vr_atm_mesure1.csv") if r["estimator"] != "plain"]
    assert fields["disp_min"].text == pb.signed(100 * min(rel), 0) + " %"
    assert fields["disp_max"].text == pb.signed(100 * max(rel), 0) + " %"
    assert (fields["disp_min"].text, fields["disp_max"].text) == ("−15 %", "+37 %")


@pytest.mark.parametrize("name, commit, path", pb.HISTORY)
def test_history_files_are_the_bytes_of_their_commit(name, commit, path):
    """results/historique/ : anciennes mesures recopiées de l'historique git, octet pour octet."""
    try:
        blob = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT, capture_output=True,
                              check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("historique git indisponible (archive sans .git)")
    have = (RESULTS / "historique" / name).read_bytes()
    assert have.replace(b"\r\n", b"\n") == blob.replace(b"\r\n", b"\n")


def test_group_names_are_those_given_by_loup(fields):
    assert [fields[f"membre_{i}"].text for i in range(1, 8)] == NAMES
    assert fields["loup"].text == "[Loup — nom]"


def test_no_result_is_typed_in_the_build_script():
    """Dans p6_build.py : aucun flottant littéral à plus de 2 chiffres significatifs (les
    résultats viennent des CSV ; restent les sélecteurs de lignes : T = 0.25, ε = 0.01…)."""
    src = (ROOT / "scripts" / "p6_build.py").read_text(encoding="utf-8")
    bad = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.NUMBER and re.search(r"[.eE]", tok.string):
            digits = re.sub(r"[eE].*$", "", tok.string).replace(".", "").replace("_", "")
            if len(digits.strip("0")) > 2:
                bad.append((tok.start[0], tok.string))
    assert bad == []


# --- les gabarits et les fichiers produits ------------------------------------------------------

def test_documents_are_declared_with_their_templates():
    expected = {"docs/DOSSIER_GROUPE.md": "docs/templates/DOSSIER_GROUPE.md",
                "docs/ORAL.md": "docs/templates/ORAL.md",
                "docs/CONFORMITE.md": "docs/templates/CONFORMITE.md",
                "rapport/rapport.html": "rapport/rapport_template.html"}
    assert pb.DOCUMENTS and set(pb.DOCUMENTS.items()) <= set(expected.items())
    assert set(pb.RENDUS) == set(pb.DOCUMENTS) - {"docs/DOSSIER_GROUPE.md"}


@pytest.mark.parametrize("out", OUTPUTS)
def test_template_has_no_decimal_number_outside_fields(out):
    template = (ROOT / pb.DOCUMENTS[out]).read_text(encoding="utf-8")
    bare = pb.PLACEHOLDER.sub("", pb.visible_text(template, out))
    assert pb.decimals(bare) == []


@pytest.mark.parametrize("out", OUTPUTS)
def test_template_fields_are_known(out, fields):
    template = (ROOT / pb.DOCUMENTS[out]).read_text(encoding="utf-8")
    names = set(pb.PLACEHOLDER.findall(template))
    assert names, "gabarit sans aucun champ"
    assert names <= set(fields), sorted(names - set(fields))


@pytest.mark.parametrize("out", OUTPUTS)
def test_output_is_regenerated_identically(out, rendered):
    text, _used = rendered[out]
    assert (ROOT / out).read_text(encoding="utf-8") == text
    assert "{{" not in text and not pb.PLACEHOLDER.search(text)      # « }} » existe dans le CSS


@pytest.mark.parametrize("out", OUTPUTS)
def test_every_decimal_number_of_the_output_comes_from_a_field(out, rendered, fields):
    _text, used = rendered[out]
    allowed = {d for name in used for d in pb.decimals(fields[name].text)}
    found = pb.decimals(pb.visible_text((ROOT / out).read_text(encoding="utf-8"), out))
    assert found, "aucun nombre décimal : le document ne cite aucun résultat"
    assert sorted(set(found) - allowed) == []


@pytest.mark.parametrize("out", OUTPUTS)
def test_links_to_figures_exist(out):
    text = (ROOT / out).read_text(encoding="utf-8")
    links = re.findall(r"""(?:\]\(|src=["'])(\.\./[^)"']+)""", text)
    assert links, "aucune figure liée"
    for rel in links:
        assert ((ROOT / out).parent / rel).resolve().is_file(), (out, rel)


def test_dossier_has_the_sections_asked_for():
    text = (ROOT / "docs/DOSSIER_GROUPE.md").read_text(encoding="utf-8")
    for title in ("En une page", "Ce qu'on a fait, étape par étape", "Les 6 coquilles du cours",
                  "Les résultats", "Limites et choix assumés", "Relancer le projet",
                  "Carte du dépôt", "Glossaire"):
        assert re.search(rf"^## .*{re.escape(title)}", text, re.M), title
    for step in ("P1", "P2", "P3", "P4", "P5a", "P5b"):
        assert re.search(rf"^### {step}\b", text, re.M), step
    for png in sorted((RESULTS / "figures").glob("*.png")):
        assert f"../results/figures/{png.name}" in text, png.name
    for term in ("LCG", "Seed", "Transformée inverse", "Box-Muller", "Acceptation-rejet",
                 "Mouvement brownien géométrique", "Option asiatique", "Moyenne géométrique",
                 "Estimateur Monte-Carlo", "IC", "Variable de contrôle", "β", "Antithétique",
                 "Efficacité", "Garman-Kohlhagen", "Forward", "Greeks"):
        assert re.search(rf"^\*\*{re.escape(term)}", text, re.M), term


# --- grille de conformité au sujet ---------------------------------------------------------------

CONFORMITE = ROOT / "docs" / "CONFORMITE.md"
SUBJECT = ROOT / "docs" / "2026-S1_ProjetPricing.pdf"
STATUSES = ("✅", "⚠️", "❌")
PARTS = ("A. Ce que le sujet demande", "B. Ce qu'on a fait en plus", "C. Ce qui reste à faire")
needs_conformite = pytest.mark.skipif("docs/CONFORMITE.md" not in pb.DOCUMENTS, reason="étape 1")


def _part(text: str, i: int) -> str:
    start = re.search(rf"^## {re.escape(PARTS[i])}.*$", text, re.M)
    assert start, PARTS[i]
    end = (re.search(rf"^## {re.escape(PARTS[i + 1])}", text[start.end():], re.M)
           if i + 1 < len(PARTS) else re.search(r"^## ", text[start.end():], re.M))
    return text[start.end():start.end() + end.start()] if end else text[start.end():]


def _table(section: str) -> list[list[str]]:
    """Lignes des tableaux Markdown d'une section (en-têtes et séparateurs ôtés), cellules
    nettoyées. Une section peut contenir plusieurs tableaux : chaque ligne suivie d'un séparateur
    est un en-tête."""
    rows: list[list[str]] = []
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        if re.match(r"\|\s*:?-", line):
            rows.pop()                          # la ligne précédente était l'en-tête
            continue
        rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows


def _quotes(cell: str) -> list[str]:
    return re.findall(r"«\s*(.+?)\s*»", cell)


def _squash(text: str) -> str:
    """Pour comparer une citation au texte extrait du PDF : sans blancs ni traits d'union (le PDF
    coupe « Acceptation-Rejet » en fin de ligne)."""
    return re.sub(r"[\s\-‐]", "", text)


@pytest.fixture(scope="module")
def conformite():
    return CONFORMITE.read_text(encoding="utf-8")


@needs_conformite
def test_conformite_has_the_three_parts(conformite):
    for i, title in enumerate(PARTS):
        assert re.search(rf"^## {re.escape(title)}", conformite, re.M), title
        assert _part(conformite, i).strip(), title


@needs_conformite
def test_conformite_part_a_one_row_per_requirement_with_one_status(conformite):
    rows = _table(_part(conformite, 0))
    assert len(rows) >= 14
    counts = dict.fromkeys(STATUSES, 0)
    for row in rows:
        assert len(row) == 5 and all(row), row[0][:60]
        assert _quotes(row[0]), row[0][:60]
        found = [s for s in STATUSES if s in row[1]]
        assert len(found) == 1, row[1]
        counts[found[0]] += 1
    quoted = " ".join(q for row in rows for q in _quotes(row[0]))
    for must in ("groupes de 7 à 10", "Date limite", "Choix entre", "VBA Excel ou python",
                 "L’interface du code", "fréquence de constatation", "Générateur congruentiel",
                 "actifs réels et théoriques", "2 pages maximum", "dynamique Black-Scholes",
                 "(call et put) asiatique", "mêmes caractéristiques", "variable de contrôle",
                 "gain de temps/précision"):
        assert must in quoted, must
    bilan = re.search(r"Bilan : (\d+) exigences ; (\d+) ✅ faites?, (\d+) ⚠️ partielles?, "
                      r"(\d+) ❌ non faites?\.", conformite)
    assert bilan, "ligne « Bilan » absente"
    assert [int(g) for g in bilan.groups()] == [len(rows), *counts.values()]


@needs_conformite
def test_conformite_quotes_are_word_for_word_in_the_subject(conformite):
    try:
        subject = _squash(pb.pdf_text(SUBJECT))
    except FileNotFoundError:
        pytest.skip("pdftotext introuvable : texte du sujet non extrait")
    for row in _table(_part(conformite, 0)):
        for quote in _quotes(row[0]):
            for piece in quote.split("[…]"):
                assert _squash(piece) in subject, piece


def test_quote_check_catches_a_paraphrase():
    try:
        subject = _squash(pb.pdf_text(SUBJECT))
    except FileNotFoundError:
        pytest.skip("pdftotext introuvable")
    assert _squash("Analyser le gain de temps/précision que vous observez.") in subject
    assert _squash("Analyser le gain de temps et de précision") not in subject


@needs_conformite
def test_conformite_part_b_rows_are_complete(conformite):
    rows = _table(_part(conformite, 1))
    assert len(rows) >= 15
    for row in rows:
        assert len(row) == 5 and all(row), row[0][:60]
        oral = re.sub(r"`[^`]*`", "", row[4])
        assert len(re.findall(r"[.?!](?=\s|$)", oral)) == 2, row[0]   # deux phrases


@needs_conformite
def test_conformite_part_c_is_a_short_list(conformite):
    items = re.findall(r"^- ", _part(conformite, 2), re.M)
    assert 3 <= len(items) <= 10


@needs_conformite
def test_conformite_cites_tests_that_exist(conformite):
    cited = re.findall(r"(test_\w+\.py)::(test_\w+)", conformite)
    assert len(cited) >= 25
    for file, name in cited:
        source = (ROOT / "tests" / file).read_text(encoding="utf-8")
        assert re.search(rf"^def {name}\(", source, re.M), f"{file}::{name}"


@needs_conformite
def test_conformite_cites_code_and_files_that_exist(conformite):
    import importlib
    names = re.findall(r"`(pricer\.\w+)\.(\w+)`", conformite)
    assert len(names) >= 10
    for module, name in names:
        assert hasattr(importlib.import_module(module), name), f"{module}.{name}"
    for csv_name in set(re.findall(r"\b(\w+\.csv)\b", conformite)):
        assert any((d / csv_name).is_file() for d in (RESULTS, RESULTS / "historique",
                                                     ROOT / "data" / "raw")), csv_name


@needs_conformite
@pytest.mark.parametrize("doc", ["docs/DOSSIER_GROUPE.md", "docs/ORAL.md"])
def test_dossier_and_oral_link_to_the_grid_at_the_top(doc):
    head = "\n".join((ROOT / doc).read_text(encoding="utf-8").splitlines()[:12])
    assert "](CONFORMITE.md)" in head
    assert "docs/CONFORMITE.md" in (ROOT / "docs/DOSSIER_GROUPE.md").read_text(encoding="utf-8")


@needs_conformite
def test_oral_has_the_one_minute_section_on_what_we_did_beyond():
    text = (ROOT / "docs/ORAL.md").read_text(encoding="utf-8")
    m = re.search(r"^## Ce qu'on a fait en plus, en 1 minute\n(.*?)^## ", text, re.M | re.S)
    assert m, "section « Ce qu'on a fait en plus, en 1 minute » absente"
    spoken = " ".join(re.findall(r"«(.*?)»", m.group(1), re.S))
    words = len(re.findall(r"\w+", spoken))
    assert 110 <= words <= 155, words                 # environ une minute à 140 mots par minute
    assert "| Ce qu'on a fait en plus | 1 min |" in text      # ligne du déroulé
    assert len(re.findall(r"^## .*en plus", text, re.M)) == 1


def test_conformite_fields_read_independently(fields):
    rows = _rows("p4_grid_cv.csv")
    strikes = sorted({float(r["K"]) for r in rows})
    maturities = sorted({float(r["T"]) for r in rows})
    assert fields["grid_strikes"].text == ", ".join(fmt_int(k) for k in strikes)
    assert fields["grid_maturites"].text == " ; ".join(pb.plain(t) for t in maturities)
    assert fields["grid_n_strikes"].text == str(len(strikes))
    assert fields["grid_n_maturites"].text == str(len(maturities))
    assert fields["n_membres"].text == str(len(NAMES) + 1)          # les 7 noms et Loup
    crn = _one("p4_greeks.csv", kind="asian", option="call", K=100, crn="True", control="geometric")
    sans = _one("p4_greeks.csv", kind="asian", option="call", K=100, crn="False",
                control="geometric")
    assert fields["gk_delta_crn_div"].text == pb.og(float(sans["delta_se"]) / float(crn["delta_se"]))


# --- documents rendus au professeur --------------------------------------------------------------

def test_forbidden_detector_catches_each_word():
    for bad in ("vu avec Cowork", "selon Claude", "le prompt", "lot P3", "en P5b", "tranché par",
                "voir reports/x.md", "dans prompts/", "CLAUDE.md", "claude code", "(P4)"):
        assert pb.forbidden_hits(bad), bad
    assert pb.forbidden_hits("Nous avons pricé l'option. P(accepter) = 1/c, fig. 1, K = 100.") == []


@pytest.mark.parametrize("out", RENDUS)
def test_rendered_documents_never_mention_our_tooling(out):
    for path in (ROOT / out, ROOT / pb.DOCUMENTS[out]):
        assert pb.forbidden_hits(path.read_text(encoding="utf-8")) == [], path.name


@pytest.mark.skipif("docs/ORAL.md" not in pb.DOCUMENTS, reason="étape 2")
def test_oral_is_in_the_first_person_plural_and_covers_the_questions():
    text = (ROOT / "docs/ORAL.md").read_text(encoding="utf-8")
    assert len(re.findall(r"\b[Nn]ous\b", text)) >= 30
    assert len(re.findall(r"^### \d+\. ", text, re.M)) >= 12
    for part in ("Q1", "Q2", "Q3", "Q4", "EUR/USD", "en plus", "Questions probables"):
        assert re.search(rf"^## .*{re.escape(part)}", text, re.M), part
    assert len(re.findall(r"^\*\*Ce qu'on montre", text, re.M)) >= 6
    assert len(re.findall(r"^\*\*Ce qu'on dit", text, re.M)) >= 6
    assert len(re.findall(r"^\*\*Le chiffre à retenir", text, re.M)) >= 6


# --- rapport HTML et PDF -------------------------------------------------------------------------

needs_report = pytest.mark.skipif("rapport/rapport.html" not in pb.DOCUMENTS, reason="étape 3")


@needs_report
def test_report_html_loads_nothing_from_the_network():
    html = (ROOT / "rapport/rapport.html").read_text(encoding="utf-8")
    assert re.findall(r"""(?:src|href)\s*=\s*["']\s*(?:https?:)?//""", html) == []
    assert "@import" not in html and "url(http" not in html
    assert "github.com" not in html.lower()


@needs_report
def test_report_has_a_cover_and_two_pages():
    html = (ROOT / "rapport/rapport.html").read_text(encoding="utf-8")
    assert len(re.findall(r'<section class="page[ "]', html)) == 3
    for name in (*NAMES, "[Loup — nom]", "Projet Pricing Monte-Carlo, énoncé 2", "ECE Paris",
                 "ING4", "A. W. Sanoussi Mani"):
        assert name in html, name
    for source in ("ours", "olycopié", "BCE", "Trésor", "FEDS 2006-28", "Alpha Vantage"):
        assert source in html, source
    assert "Segoe UI" in html and "Consolas" in html
    assert "JetBrains" not in html and "fonts.googleapis" not in html


@needs_report
def test_pdf_has_a_cover_and_two_pages():
    assert pb.PDF.is_file()
    assert pb.pdf_page_count(pb.PDF) == 3


@needs_report
def test_pdf_text_has_the_names_no_tooling_word_and_the_figures_of_the_html():
    try:
        text = pb.pdf_text(pb.PDF)
    except FileNotFoundError:
        pytest.skip("pdftotext introuvable : texte du PDF non extrait")
    flat = re.sub(r"\s+", " ", text)
    assert pb.forbidden_hits(text) == []
    for name in (*NAMES, "[Loup — nom]", "A. W. Sanoussi Mani"):
        assert name in flat, name
    f = pb.fields()
    for name in ("vr_call_T1_ctrl_prix", "fx_spot_call_prix", "ratio_call_K100_T1_4"):
        assert f[name].text in flat, name          # le PDF est bien celui du rapport.html courant


@needs_report
def test_pdf_prints_the_dark_background_and_the_four_figures():
    """« Fonds imprimés » : chaque page commence par un rectangle plein #030306 de la taille de la
    page (794 × 1123 px), et le PDF contient les 4 figures retenues (images)."""
    raw = pb.PDF.read_bytes()
    pages = 0
    for m in re.finditer(rb"stream\r?\n", raw):
        try:
            data = zlib.decompress(raw[m.end():raw.find(b"endstream", m.end())])
        except zlib.error:
            continue
        if re.match(rb"[^B]*?\.0118 \.0118 \.0235 rg\s+(?:/\w+ gs\s+)?0 0 794 1123 re\s+f\b", data):
            pages += 1
    assert pages == 3
    assert len(re.findall(rb"/Subtype\s*/Image", raw)) == 4
    html = (ROOT / "rapport/rapport.html").read_text(encoding="utf-8")
    assert re.findall(r'src="\.\./results/figures/(\w+)\.png"', html) == [
        "fig1_eventail_eurusd", "fig2_disques_ratio", "fig4_convergence", "fig3_gain_efficacite"]


def test_page_count_reader_on_a_minimal_pdf(tmp_path):
    raw = (b"%PDF-1.4\n1 0 obj<</Type /Pages /Kids [2 0 R 3 0 R] /Count 2>>endobj\n"
           b"2 0 obj<</Type /Page /Parent 1 0 R>>endobj\n3 0 obj<</Type/Page/Parent 1 0 R>>endobj\n")
    p = tmp_path / "x.pdf"
    p.write_bytes(raw)
    assert pb.pdf_page_count(p) == 2
