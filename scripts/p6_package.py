"""Paquet de rendu au professeur → rendu/Projet_Pricing_Asiatique/ puis rendu/Projet_Pricing_Asiatique.zip.

Le dossier rendu/ est ignoré par git ; seul ce script est versionné. Contenu du paquet :

    Rapport_Pricing_Asiatique.pdf   le rapport (page de garde + 2 pages)
    LISEZMOI.md                     notice : projet, installation, la fonction demandée par le sujet
                                    (exemple exécuté, sortie recopiée par ce script), générateurs,
                                    relance de chaque résultat, tests
    code/                           projet autonome : src/pricer/, les scripts qui produisent les
                                    résultats, tests/ (garde-fou de version compris), requirements.txt,
                                    pyproject.toml, et aux chemins que lit le code : data/raw/
                                    (relevés bruts) et results/ (CSV, figures du mode rendu)
    donnees/                        relevés bruts et leur MANIFEST
    resultats/                      CSV, figures/ (mode rendu), Resultats_Pricing_Asiatique.xlsx

Exclus : dossiers et fichiers de travail du groupe (voir EXCLUDED_*), figures internes, classeur du
groupe, scripts et tests de mise en forme des documents (ils lisent des fichiers non livrés),
caches. Contrôles (verify) : (a) aucun mot de l'outillage, insensible à la casse, dans les fichiers
texte, les noms de fichiers, le texte des PDF et les cellules du classeur ; (b) aucun fichier exclu ;
(c) pytest passe dans une copie de code/ (--pytest, lent) ; (d) l'exemple du LISEZMOI se relance et
donne la même sortie.

Usage : .venv/Scripts/python.exe scripts/p6_package.py [--pytest]

Paquet pour l'équipe (interne au groupe, jamais rendu) : --equipe écrit seulement
rendu/Dossier_Equipe_Pricing_Asiatique/ puis son .zip : 0_LISEZ-MOI_EQUIPE.pdf (une page : contenu
et ordre de lecture, ce qu'on rend au professeur, le dépôt GitHub pas à pas), 1_Dossier_Groupe.pdf,
2_Oral.pdf, 3_Conformite.pdf (docs/pdf/), 4_Rapport_rendu.pdf, 5_Resultats.xlsx, figures/ (mode
rendu). Le LISEZ-MOI, l'oral et la grille sont sans mot de l'outillage ; le dossier peut en citer.
"""
from __future__ import annotations

import argparse
import csv
import inspect
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import p6_build as pb  # noqa: E402
from pricer.asian import price_asian  # noqa: E402
from pricer.normals import METHODS  # noqa: E402

NAME = "Projet_Pricing_Asiatique"
OUT_ROOT = ROOT / "rendu"
REPORT = ROOT / "rapport" / "Rapport_Pricing_Asiatique.pdf"
WORKBOOK = ROOT / "results" / "Resultats_Pricing_Asiatique.xlsx"
RENDU_FIGS = ROOT / "results" / "figures" / "rendu"

# Scripts livrés : chacun produit des résultats (script, option, fichiers produits, contenu).
RERUN = [
    ("p1_diagnostics.py", "", ["p1_rng_diagnostics.csv", "p1_qq.csv"],
     "tests statistiques des générateurs de normales"),
    ("p2_grid.py", "", ["p2_grid.csv"], "asiatique et européenne, 5 strikes × 4 maturités"),
    ("p3_vr_atm.py", "", ["p3_vr_atm.csv"], "réduction de variance à la monnaie, temps mesurés"),
    ("p4_cours.py", "", ["p4_ex77.csv", "p4_ex78.csv"], "exercices des slides 77 et 78"),
    ("p4_convergence.py", "", ["p4_convergence.csv", "p4_convergence_slopes.csv",
                               "p4_n_required.csv", "p4_equal_time.csv"],
     "convergence, N nécessaire, comparaison à temps égal"),
    ("p4_sensibilites.py", "", ["p4_beta_bias.csv", "p4_beta_bias_runs.csv",
                                "p4_rng_methods.csv", "p4_frequency.csv", "p4_grid_cv.csv"],
     "biais de β, méthodes d'aléa, fréquence, grille avec contrôle (long)"),
    ("p4_greeks.py", "", ["p4_greeks.csv"], "delta, gamma, vega par différences finies"),
    ("p5_fetch.py", "--manifest", ["data/raw/MANIFEST.md"],
     "sans option : relevés BCE et Trésor par le réseau ; --manifest : MANIFEST seul, hors ligne"),
    ("p5_market.py", "", ["p5_market.csv"], "calibration EUR/USD depuis data/raw/"),
    ("p5_eurusd.py", "", ["p5_eurusd.csv", "p5_eurusd_sensitivity.csv"], "cas réel EUR/USD"),
    ("p5_figures.py", "--rendu", ["results/figures/rendu/"], "figures du rapport"),
]
SCRIPTS = [s for s, *_ in RERUN]
EXCLUDED_TESTS = ("test_p5_excel.py", "test_p6_build.py", "test_p6_excel_prof.py",
                  "test_p6_package.py", "test_p6_pdf_groupe.py")
EXCLUDED_PARTS = {"reports", "prompts", "docs", ".venv", ".git", "historique", "__pycache__",
                  ".pytest_cache", "rapport"}
EXCLUDED_NAMES = {"CLAUDE.md", "AGENTS.md", "pricing_asian_resultats.xlsx", "p5_excel.py",
                  "p6_build.py", "p6_excel_prof.py", "p6_package.py", "p6_pdf_groupe.py",
                  *EXCLUDED_TESTS}
FORBIDDEN = [re.compile(p.pattern, re.I) for p in pb.FORBIDDEN] + [
    re.compile(r"d[ée]cision de loup", re.I), re.compile(r"agents\.md", re.I),
    re.compile(r"\blots?\s+p\d", re.I), re.compile(r"\bQ[5-9]\b")]
TEXT_SUFFIXES = {".py", ".md", ".txt", ".toml", ".csv", ".json", ".cfg", ".ini", ".html"}

PARAMS = [
    ("S0", "spot", "cours de l'actif aujourd'hui"),
    ("K", "strike", "prix d'exercice"),
    ("sigma", "volatilité", "volatilité annuelle (0.2 pour 20 %)"),
    ("r", "taux sans risque", "taux continu annuel"),
    ("T", "maturité", "en années"),
    ("q", "dividende", "taux de dividende continu (taux étranger pour le change)"),
    ("option", "type", "« call » ou « put »"),
    ("obs", "fréquence d'observation du spot (paramètre propre à l'asiatique)",
     "nombre de dates de constatation, ou « daily », « weekly », « monthly », « quarterly » : "
     "dates t_k = k·T/n, la moyenne porte sur ces n cours"),
    ("n_paths", "simulation", "nombre de trajectoires N"),
    ("seed", "simulation", "graine du générateur congruentiel linéaire (résultat reproductible)"),
    ("rng_method", "simulation", "méthode de génération des normales (voir plus bas)"),
    ("control", "réduction de variance",
     "None, ou « geometric » : option sur moyenne géométrique comme variable de contrôle"),
    ("beta", "réduction de variance",
     "« optimal » (estimé sur l'échantillon), un nombre, ou « pilot »"),
    ("antithetic", "réduction de variance", "True : trajectoires antithétiques (Z, −Z)"),
    ("confidence", "intervalle", "niveau de l'intervalle de confiance"),
    ("include_s0, average, n_pilot, batch_size", "options",
     "S0 compté dans la moyenne ; moyenne « arithmetic » ou « geometric » ; trajectoires du "
     "pilote ; taille des paquets de calcul"),
]
METHOD_NAMES = {"inverse": "générateur congruentiel linéaire + transformée inverse (AS241), "
                           "par défaut",
                "box_muller": "générateur congruentiel linéaire + Box-Muller",
                "polar": "générateur congruentiel linéaire + méthode polaire (Marsaglia)",
                "acceptance_rejection": "générateur congruentiel linéaire + acceptation-rejet"}


# --- l'exemple de la fonction ---------------------------------------------------------------------

def reference_row() -> dict:
    """Ligne « call, T = 1, contrôle β optimal » de results/p3_vr_atm.csv : l'exemple refait ce
    calcul déjà publié (aucun prix nouveau)."""
    with (ROOT / "results" / "p3_vr_atm.csv").open(encoding="utf-8") as f:
        return next(r for r in csv.DictReader(f) if r["option"] == "call"
                    and r["estimator"] == "control_beta_optimal" and float(r["T"]) == 1)


def example_code() -> str:
    r = reference_row()
    return (
        "from pricer.asian import price_asian\n"
        "\n"
        f"res = price_asian(S0={float(r['S0']):g}, K={float(r['K']):g}, "
        f"sigma={float(r['sigma']):g}, r={float(r['r']):g}, T={float(r['T']):g}, "
        f"q={float(r['q']):g},\n"
        f"                  option=\"call\", obs=\"{r['obs']}\", n_paths={int(r['n_paths'])}, "
        f"seed={int(r['seed'])},\n"
        "                  control=\"geometric\")\n"
        "print(f\"prix            {res.price:.4f}\")\n"
        "print(f\"écart-type      {res.std_error:.1e}\")\n"
        "print(f\"IC à 95 %       [{res.ci_low:.4f} ; {res.ci_high:.4f}]\")\n"
        "print(f\"trajectoires    {res.n_paths}, graine {res.seed}, {res.n_obs} dates\")\n"
        "print(f\"variance ÷      {res.variance_ratio:.0f} (β = {res.beta:.4f})\")\n")


def run_example(code_dir: Path, code: str) -> str:
    """Exécute l'exemple avec le code du dossier code_dir (src/ en tête du chemin)."""
    env = {**os.environ, "PYTHONPATH": str(code_dir / "src"), "PYTHONIOENCODING": "utf-8",
           "PYTHONDONTWRITEBYTECODE": "1"}                 # aucun __pycache__ dans le paquet
    done = subprocess.run([sys.executable, "-B", "-c", code], cwd=code_dir, env=env,
                          capture_output=True, check=True, timeout=300)
    return done.stdout.decode("utf-8").replace("\r\n", "\n")


# --- LISEZMOI ------------------------------------------------------------------------------------

def readme(example_out: str) -> str:
    sig = re.sub(r" -> .*$", "", f"price_asian{inspect.signature(price_asian)}")
    params = "\n".join(f"| `{name}` | {kind} | {what} |" for name, kind, what in PARAMS)
    methods = "\n".join(f"- `rng_method=\"{m}\"` : {METHOD_NAMES[m]} ;" for m in METHODS)
    rerun = "\n".join(
        f"| `scripts/{s}{(' ' + a) if a else ''}` | {', '.join(f'`{o}`' for o in outs)} | {note} |"
        for s, a, outs, note in RERUN)
    py = re.search(r"\(Python (\d+\.\d+)", (ROOT / "requirements.txt").read_text(encoding="utf-8"))
    return f"""# Option asiatique et réduction de variance — projet Pricing Monte-Carlo

Projet de groupe, cours « Pricing Monte-Carlo » (A. W. Sanoussi Mani), ECE Paris, ING4 Finance,
énoncé 2. Le code Python évalue par Monte-Carlo le call et le put asiatiques (moyenne arithmétique)
sous Black-Scholes avec dividende continu, les compare aux options européennes, réduit la variance
par une variable de contrôle (option sur moyenne géométrique, prix fermé) et mesure le gain de temps
et de précision ; il l'applique ensuite au change EUR/USD. Les normales viennent uniquement des
méthodes du cours (générateur congruentiel linéaire et transformations).

## Contenu

- `Rapport_Pricing_Asiatique.pdf` : le rapport (page de garde et 2 pages).
- `code/` : le projet complet et autonome (`src/pricer/`, `scripts/`, `tests/`, `requirements.txt`,
  `pyproject.toml`, et les données lues par le code : `data/raw/`, `results/`).
- `donnees/` : les relevés bruts de marché (BCE, Trésor américain, Alpha Vantage) et leur
  `MANIFEST.md` (source, URL, date de relevé, empreinte sha256 de chaque fichier).
- `resultats/` : les résultats (CSV), les figures du rapport (`figures/`, PNG et PDF) et le classeur
  `Resultats_Pricing_Asiatique.xlsx` (onglet « Synthèse » lisible sans le code).

## Installation

Python {py.group(1) if py else "3"} sous Windows, depuis le dossier `code/` :

```
python -m venv .venv
.venv\\Scripts\\pip install -r requirements.txt
```

Toutes les versions sont épinglées dans `requirements.txt`. Les tests vérifient au démarrage que
numpy, scipy et pytest ont exactement ces versions ; sinon ils s'arrêtent avec un message.

## La fonction demandée par le sujet

`pricer.asian.price_asian` (fichier `code/src/pricer/asian.py`) :

```
{sig}
```

| Paramètre | Rôle | Sens |
|---|---|---|
{params}

Elle renvoie un `MCResult` : `price`, `std_error` (écart-type de l'estimateur), `ci_low` et
`ci_high` (intervalle de confiance), `n_paths`, `seed`, et avec le contrôle `beta`, `corr`,
`variance_ratio`. La fonction `price_european_mc` a les mêmes paramètres pour l'option européenne.

Exemple, à lancer depuis `code/` avec `.venv\\Scripts\\python`, `src` étant dans le chemin Python
(`set PYTHONPATH=src`) :

```python
{example_code().rstrip()}
```

Sortie obtenue :

```
{example_out.rstrip()}
```

## Générateurs disponibles

Uniformes : générateur congruentiel linéaire de Park-Miller (`pricer.rng.LCG`). Normales
(`pricer.normals.normals`) :

{methods}

aucune autre source d'aléa (ni `numpy.random`, ni `random`, ni SciPy dans `src/`, ce qu'un test
vérifie).

## Relancer chaque résultat

Depuis `code/`, avec `.venv\\Scripts\\python` ; chaque script réécrit ses fichiers dans `results/`
(même graine, donc mêmes prix ; seuls les temps de calcul mesurés changent d'une machine à l'autre).

| Commande | Produit | Contenu |
|---|---|---|
{rerun}

Le rapport PDF et le classeur Excel mettent en forme ces CSV et ces figures.

## Lancer les tests

Depuis `code/` :

```
.venv\\Scripts\\python -m pytest -q
```

Les quelques tests qui comparent le code à des fichiers de travail non livrés (figures de travail,
maquette graphique) sont sautés ; tous les autres doivent passer.
"""


# --- construction --------------------------------------------------------------------------------

def _copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def code_sources() -> list[tuple[Path, str]]:
    """(fichier du dépôt, chemin dans code/)."""
    out = [(p, f"src/pricer/{p.name}") for p in sorted((ROOT / "src" / "pricer").glob("*.py"))]
    out += [(ROOT / "scripts" / s, f"scripts/{s}") for s in SCRIPTS]
    out += [(p, f"tests/{p.name}") for p in sorted((ROOT / "tests").glob("*.py"))
            if p.name not in EXCLUDED_TESTS]
    out += [(ROOT / n, n) for n in ("requirements.txt", "pyproject.toml")]
    out += [(p, f"data/raw/{p.name}") for p in sorted((ROOT / "data" / "raw").iterdir())
            if p.is_file()]
    out += [(p, f"results/{p.name}") for p in sorted((ROOT / "results").glob("*.csv"))]
    out += [(p, f"results/figures/rendu/{p.name}") for p in sorted(RENDU_FIGS.iterdir())]
    return out


def build(out_root: Path = OUT_ROOT) -> tuple[Path, Path]:
    """Écrit out_root/Projet_Pricing_Asiatique/ et out_root/Projet_Pricing_Asiatique.zip."""
    pkg = out_root / NAME
    if pkg.exists():
        shutil.rmtree(pkg)
    _copy(REPORT, pkg / REPORT.name)
    for src, rel in code_sources():
        _copy(src, pkg / "code" / rel)
    for p in sorted((ROOT / "data" / "raw").iterdir()):
        _copy(p, pkg / "donnees" / p.name)
    for p in sorted((ROOT / "results").glob("*.csv")):
        _copy(p, pkg / "resultats" / p.name)
    for p in sorted(RENDU_FIGS.iterdir()):
        _copy(p, pkg / "resultats" / "figures" / p.name)
    _copy(WORKBOOK, pkg / "resultats" / WORKBOOK.name)
    out = run_example(pkg / "code", example_code())
    (pkg / "LISEZMOI.md").write_text(readme(out), encoding="utf-8", newline="\n")
    archive = out_root / f"{NAME}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(pkg.rglob("*")):
            if p.is_file():
                z.write(p, f"{NAME}/{p.relative_to(pkg).as_posix()}")
    return pkg, archive


# --- paquet pour l'équipe (interne au groupe, jamais rendu au professeur) ------------------------

EQUIPE = "Dossier_Equipe_Pricing_Asiatique"
GITHUB = "https://github.com/Lisaii1/pricing-asian.git"      # dépôt privé : accès sur invitation


def equipe_files() -> list[tuple[str, Path]]:
    """(nom dans le paquet, fichier du dépôt), dans l'ordre de lecture ; le LISEZ-MOI est écrit à
    part. Les PDF du groupe viennent de docs/pdf/ (p6_build.py --pdf-groupe)."""
    import p6_pdf_groupe as pg
    return [("1_Dossier_Groupe.pdf", pg.DOSSIER_PDF), ("2_Oral.pdf", pg.ORAL_PDF),
            ("3_Conformite.pdf", pg.CONF_PDF), ("4_Rapport_rendu.pdf", REPORT),
            ("5_Resultats.xlsx", WORKBOOK)]


def count_tests() -> int:
    """Nombre de tests que pytest trouve dans le dépôt (collecte seule, rien n'est exécuté)."""
    done = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q",
                           "-p", "no:cacheprovider"], cwd=ROOT, capture_output=True, timeout=600,
                          env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    out = done.stdout.decode("utf-8", errors="replace")
    return int(re.search(r"(\d+) tests? collected", out).group(1))


def lisez_moi_equipe_html(n_tests: int) -> str:
    """Une page : contenu et ordre de lecture, ce qu'on rend au professeur, le dépôt GitHub."""
    import p6_pdf_groupe as pg
    date = pb.fields()["date_rendu"].text
    py = re.search(r"\(Python (\d+\.\d+)", (ROOT / "requirements.txt").read_text(encoding="utf-8"))
    rows = [
        ("1_Dossier_Groupe.pdf", "tout ce qu'on a fait, étape par étape, et pourquoi ; à lire en "
                                 "premier (sommaire cliquable, glossaire à la fin)"),
        ("2_Oral.pdf", "les fiches pour apprendre la soutenance : une par partie (figure, chiffre à "
                       "retenir, phrases à dire), 20 questions probables, les 10 chiffres par cœur"),
        ("3_Conformite.pdf", "le sujet exigence par exigence : fait ou partiel, où, la preuve ; nos "
                             "ajouts avec deux phrases d'oral chacun ; ce qui reste à faire"),
        ("4_Rapport_rendu.pdf", "le rapport tel qu'il sera rendu (page de garde et 2 pages)"),
        ("5_Resultats.xlsx", "le classeur de résultats remis au professeur (onglet « Synthèse »)"),
        ("figures/", "les figures et tableaux du rapport, en PNG"),
    ]
    steps = [
        ("Accepter l'invitation reçue par mail", "accès au dépôt privé sur GitHub"),
        (f"git clone {GITHUB}", ""),
        ("cd pricing-asian", ""),
        ("python -m venv .venv", f"Python {py.group(1) if py else '3'}, une seule fois"),
        (r".venv\Scripts\pip install -r requirements.txt", "versions exactes, une seule fois"),
        (r".venv\Scripts\python -m pytest -q", "lance tous les tests, environ une minute"),
    ]
    css = """
.one{padding:0 14mm}
.one h1{font:800 30px/1.1 var(--sans);letter-spacing:-.02em;margin:8px 0 4px}
.one h2{font:600 10px var(--mono);letter-spacing:.2em;text-transform:uppercase;color:var(--a1);
  margin:7mm 0 2.5mm}
.one p{font-size:12px;margin:0 0 2mm}
.one td{font-size:11.5px;padding:5px 8px}
.one td:first-child{font-family:var(--mono);color:var(--a1);white-space:nowrap}
.one ol{margin:0;padding-left:22px}
.one li{font-size:12px;margin:0 0 2.2mm}
.one li code{font-size:11.5px}
.one li span{color:var(--sub);font-size:11px}
.see{border:1.5px solid var(--a1);border-radius:9px;padding:8px 12px;margin-top:3mm;
  background:rgba(0,255,163,.07);font-size:12px}
"""
    body = (
        '<section class="one"><div class="eyebrow"><span><b>●</b>&nbsp; Dossier de l\'équipe · '
        "à lire en premier</span><span>ECE Paris · ING4 Finance</span></div>"
        "<h1>L'option asiatique pricée par Monte-Carlo</h1>"
        f"<p>Projet Pricing Monte-Carlo, énoncé 2. Rendu le {pg.esc(date)}. Ce dossier rassemble "
        "tout ce qu'il faut pour comprendre le projet et préparer la soutenance, sans rien "
        "installer.</p>"
        "<h2>Ce que contient ce dossier, dans l'ordre de lecture</h2><table><tbody>"
        + "".join(f"<tr><td>{pg.esc(n)}</td><td>{pg.esc(w)}</td></tr>" for n, w in rows)
        + "</tbody></table>"
        "<h2>Ce qu'on rend au professeur</h2>"
        f"<p>Une archive <code>{NAME}.zip</code> : le rapport PDF (page de garde et 2 pages), le "
        "code Python complet avec ses tests, les données de marché brutes, les résultats (fichiers "
        "CSV, figures, classeur Excel) et une notice d'installation. Le dossier, les fiches d'oral "
        "et la grille sont nos documents de travail : ils ne font pas partie du rendu.</p>"
        "<h2>Pour tout voir en détail : GitHub</h2>"
        "<p>Le code, les résultats et l'historique de chaque modification sont sur GitHub. Dans un "
        "terminal Windows (PowerShell), une fois l'invitation acceptée :</p><ol>"
        + "".join(f"<li><code>{pg.esc(c)}</code>{' <span>— ' + pg.esc(w) + '</span>' if w else ''}"
                  "</li>" if i else f"<li><b>{pg.esc(c)}</b> <span>— {pg.esc(w)}</span></li>"
                  for i, (c, w) in enumerate(steps))
        + "</ol>"
        f'<div class="see"><b>Ce qu\'on doit voir :</b> des lignes de points, puis une dernière '
        f"ligne <code>{n_tests} passed</code>, sans aucun <code>failed</code>. Si un outil manque "
        "sur la machine (par exemple pdftotext, livré avec Git pour Windows), quelques tests "
        "s'affichent <code>skipped</code> : c'est prévu.</div></section>")
    return pg.page("Dossier de l'équipe", "Dossier de l'équipe · lisez-moi", css, body)


def build_equipe(out_root: Path = OUT_ROOT, n_tests: int | None = None) -> tuple[Path, Path]:
    """Écrit out_root/Dossier_Equipe_Pricing_Asiatique/ et son .zip (le paquet de rendu au
    professeur n'est pas touché)."""
    pkg = out_root / EQUIPE
    if pkg.exists():
        shutil.rmtree(pkg)
    pkg.mkdir(parents=True)
    for name, src in equipe_files():
        _copy(src, pkg / name)
    for p in sorted(RENDU_FIGS.glob("*.png")):
        _copy(p, pkg / "figures" / p.name)
    html = pkg.parent / f"{EQUIPE}_lisez-moi.html"
    html.write_text(lisez_moi_equipe_html(count_tests() if n_tests is None else n_tests),
                    encoding="utf-8")
    try:
        pb.build_pdf(html, pkg / "0_LISEZ-MOI_EQUIPE.pdf")
    finally:
        html.unlink()
    archive = out_root / f"{EQUIPE}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(pkg.rglob("*")):
            if p.is_file():
                z.write(p, f"{EQUIPE}/{p.relative_to(pkg).as_posix()}")
    return pkg, archive


def equipe_listing(pkg: Path, archive: Path) -> str:
    """Contenu dans l'ordre, nombre de pages des PDF, taille de chaque fichier et de l'archive."""
    def size(p: Path) -> str:
        return f"{p.stat().st_size:,}".replace(",", " ") + " octets"

    lines = []
    for p in sorted(pkg.rglob("*")):
        if p.is_file():
            pages = f", {pb.pdf_page_count(p)} p." if p.suffix == ".pdf" else ""
            lines.append(f"{p.relative_to(pkg).as_posix()}  ({size(p)}{pages})")
    lines.append(f"{archive.name} : {size(archive)}")
    return "\n".join(lines)


# --- contrôles -----------------------------------------------------------------------------------

def forbidden_hits(text: str) -> list[str]:
    return [m.group(0) for pattern in FORBIDDEN for m in pattern.finditer(text)]


def check_forbidden(pkg: Path) -> list[str]:
    """(a) Mots de l'outillage : textes, noms de fichiers, texte des PDF, cellules du classeur."""
    from openpyxl import load_workbook
    bad = []
    for p in sorted(pkg.rglob("*")):
        rel = p.relative_to(pkg).as_posix()
        bad += [f"{rel} (nom) : {h}" for h in forbidden_hits(rel)]
        if not p.is_file():
            continue
        if p.suffix.lower() in TEXT_SUFFIXES:
            text = p.read_bytes().decode("utf-8", errors="replace")
            bad += [f"{rel} : {h}" for h in forbidden_hits(text)]
        elif p.suffix.lower() == ".pdf":
            text = pb.pdf_text(p)
            bad += [f"{rel} (texte du PDF) : {h}" for h in forbidden_hits(text)]
            bad += [f"{rel} (texte du PDF) : {h}" for h in re.findall(r"\w+\.csv", text)]
        elif p.suffix.lower() == ".xlsx":
            book = load_workbook(p)
            for ws in book.worksheets:
                bad += [f"{rel} (onglet) : {h}" for h in forbidden_hits(ws.title)]
                for row in ws.iter_rows():
                    for c in row:
                        if isinstance(c.value, str):
                            bad += [f"{rel} {ws.title}!{c.coordinate} : {h}"
                                    for h in forbidden_hits(c.value)]
    return bad


def check_excluded(pkg: Path) -> list[str]:
    """(b) Aucun fichier exclu ; figures de results/ : mode rendu seulement."""
    bad = []
    for p in pkg.rglob("*"):
        rel = p.relative_to(pkg)
        if set(rel.parts) & EXCLUDED_PARTS or p.name in EXCLUDED_NAMES:
            bad.append(rel.as_posix())
        elif rel.parts[:3] == ("code", "results", "figures") and p.is_file() \
                and rel.parts[3] != "rendu":
            bad.append(rel.as_posix())
    return bad


def check_example(pkg: Path) -> bool:
    """(d) L'exemple du LISEZMOI, relancé avec le code du paquet, redonne la sortie écrite."""
    text = (pkg / "LISEZMOI.md").read_text(encoding="utf-8")
    code = re.search(r"```python\n(.*?)```", text, re.S).group(1)
    written = re.search(r"Sortie obtenue :\n\n```\n(.*?)```", text, re.S).group(1)
    return run_example(pkg / "code", code).rstrip() == written.rstrip()


def run_package_tests(pkg: Path) -> subprocess.CompletedProcess:
    """(c) pytest dans une copie temporaire de code/, avec l'interpréteur courant (venv du projet)."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        work = Path(tmp) / "code"
        shutil.copytree(pkg / "code", work)
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        env["PYTHONIOENCODING"] = "utf-8"
        return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
                              cwd=work, env=env, capture_output=True, timeout=1800)


def verify(pkg: Path, with_pytest: bool = False) -> dict:
    report = {"a_mots_interdits": check_forbidden(pkg), "b_fichiers_exclus": check_excluded(pkg),
              "d_exemple_identique": check_example(pkg)}
    if with_pytest:
        done = run_package_tests(pkg)
        out = done.stdout.decode("utf-8", errors="replace").strip().splitlines()
        report["c_pytest"] = (done.returncode, out[-1] if out else "")
    return report


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pytest", action="store_true", help="lance aussi pytest dans le paquet")
    parser.add_argument("--equipe", action="store_true",
                        help="écrit seulement le paquet pour l'équipe (le rendu n'est pas touché)")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if args.equipe:
        pkg, archive = build_equipe()
        print(f"écrit {pkg.relative_to(ROOT)} et {archive.relative_to(ROOT)}")
        print(equipe_listing(pkg, archive))
        hits = [f"{n} : {h}" for n in ("0_LISEZ-MOI_EQUIPE.pdf", "2_Oral.pdf", "3_Conformite.pdf")
                for h in forbidden_hits(pb.pdf_text(pkg / n))]
        print(f"mots de l'outillage (LISEZ-MOI, oral, grille) : {hits}")
        return
    pkg, archive = build()
    files = [p for p in pkg.rglob("*") if p.is_file()]
    print(f"écrit {pkg.relative_to(ROOT)} ({len(files)} fichiers) et {archive.relative_to(ROOT)} "
          f"({archive.stat().st_size:,} octets)")
    for key, value in verify(pkg, args.pytest).items():
        print(f"{key} : {value}")


if __name__ == "__main__":
    main()
