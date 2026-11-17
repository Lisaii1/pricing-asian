"""Classeur de résultats, version professeur → results/Resultats_Pricing_Asiatique.xlsx (openpyxl).

Le classeur du groupe (scripts/p5_excel.py → results/pricing_asian_resultats.xlsx) reste tel quel.
Celui-ci se lit sans le code, en français :

    Synthèse                réponses chiffrées aux questions 1 à 4 du sujet et au cas EUR/USD, en
                            petits tableaux, avec les figures du mode rendu (results/figures/rendu/)
    Paramètres et sources   actif théorique et EUR/USD ; sources officielles, URL, date de relevé
    A1 … A16                annexes : un onglet par tableau utile, en-têtes en français, seulement
                            les colonnes qui servent

Règles du classeur du groupe inchangées : valeurs copiées des CSV de results/ (aucune formule,
aucun nombre tapé) ; prix 0,0000 ; écarts-types et demi-largeurs en scientifique à 2 chiffres sous
10^-4 ; temps 0,000 s. Gains d'efficacité de la synthèse : à l'ordre de grandeur, comme le
tableau 1 du rapport (moyenne des deux mesures du temps, results/p3_vr_atm.csv et
results/historique/p3_vr_atm_mesure1.csv, arrondie à 2 chiffres significatifs).

Usage : .venv/Scripts/python.exe scripts/p6_excel_prof.py
"""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from openpyxl import Workbook  # noqa: E402
from openpyxl.drawing.image import Image as XLImage  # noqa: E402
from openpyxl.styles import Alignment, Font  # noqa: E402
from PIL import Image  # noqa: E402

import p5_excel as px  # noqa: E402
from p6_build import GROUP  # noqa: E402
from pricer.market import TREASURY_SOURCES  # noqa: E402
from pricer.plotstyle import FONT_MONO, FONT_SANS, fmt_int, fmt_num, fmt_pct  # noqa: E402
from pricer.rng import PARK_MILLER_A  # noqa: E402

RESULTS = ROOT / "results"
FIG_DIR = RESULTS / "figures" / "rendu"
HISTORY = RESULTS / "historique" / "p3_vr_atm_mesure1.csv"
OUT = RESULTS / "Resultats_Pricing_Asiatique.xlsx"

ALPHA_VANTAGE = "Alpha Vantage, API FX_DAILY et TREASURY_YIELD, relevé du 17/11/2026"
ALPHA_VANTAGE_URL = "https://www.alphavantage.co/documentation/"
IMAGE_COL, IMAGE_WIDTH_PX, ROW_PX = "K", 560, 20
NOTE_COLOR = "555A6E"

ESTIMATORS = {"plain": "Sans réduction", "antithetic": "Antithétique",
              "control_beta_1": "Contrôle, β = 1", "control_beta_optimal": "Contrôle, β optimal",
              "control": "Contrôle, β optimal", "antithetic_control": "Antithétique + contrôle"}
METHODS = {"inverse": "Transformée inverse (AS241)", "inverse_as241": "Transformée inverse (AS241)",
           "inverse_hastings": "Transformée inverse (Hastings)", "box_muller": "Box-Muller",
           "polar": "Polaire (Marsaglia)", "acceptance_rejection": "Acceptation-rejet"}
STRIKES = {"spot": "K = S0", "forward": "K = forward 1 an"}
OBS = {"monthly": "mensuelle", "weekly": "hebdomadaire", "daily": "quotidienne",
       "quarterly": "trimestrielle"}
WORDS = {**ESTIMATORS, **METHODS, **STRIKES, **OBS, "geometric": "géométrique", "pilot": "pilote",
         "asian": "asiatique", "european": "européenne", "slide77": "slide 77",
         "slide78": "slide 78"}

# Annexes : (onglet, CSV, [(colonne du CSV, en-tête en français)])
ANNEXES = [
    ("A1 Générateurs", "p1_rng_diagnostics.csv", [
        ("method", "Méthode"), ("n", "Nombre de normales"), ("seed", "Graine"),
        ("mean", "Moyenne"), ("variance", "Variance"), ("skewness", "Asymétrie"),
        ("excess_kurtosis", "Excès de kurtosis"), ("ks_pvalue", "p-valeur de Kolmogorov-Smirnov"),
        ("uniforms_per_normal", "Uniformes par normale"), ("acceptance_rate", "Taux d'acceptation"),
        ("acceptance_theoretical", "Taux d'acceptation théorique"),
        ("time_median_s", "Temps médian (s)")]),
    ("A2 Prix sans réduction", "p2_grid.csv", [
        ("option", "Option"), ("K", "Strike K"), ("T", "Maturité T (ans)"),
        ("asian_price", "Asiatique"), ("asian_std_error", "Écart-type"),
        ("asian_ci_low", "IC 95 % bas"), ("asian_ci_high", "IC 95 % haut"),
        ("euro_mc_price", "Européenne (Monte-Carlo)"), ("euro_mc_std_error", "Écart-type (euro.)"),
        ("euro_bs_price", "Européenne (Black-Scholes)"),
        ("euro_mc_minus_bs_in_se", "Écart MC − BS (en écarts-types)"),
        ("ratio_asian_over_euro_bs", "Ratio asiatique / européenne"), ("n_paths", "N"),
        ("seed", "Graine")]),
    ("A3 Grille avec contrôle", "p4_grid_cv.csv", [
        ("option", "Option"), ("K", "Strike K"), ("T", "Maturité T (ans)"),
        ("price", "Asiatique"), ("std_error", "Écart-type"), ("ci_low", "IC 95 % bas"),
        ("ci_high", "IC 95 % haut"), ("euro_bs_price", "Européenne (Black-Scholes)"),
        ("ratio", "Ratio asiatique / européenne"), ("ratio_ci_low", "Ratio, IC bas"),
        ("ratio_ci_high", "Ratio, IC haut"), ("beta", "β"), ("corr", "Corrélation"),
        ("variance_ratio", "Variance ÷"), ("n_paths", "N"), ("seed", "Graine")]),
    ("A4 Réduction de variance", "p3_vr_atm.csv", [
        ("option", "Option"), ("T", "Maturité T (ans)"), ("estimator", "Estimateur"),
        ("price", "Prix"), ("std_error", "Écart-type"), ("ci_low", "IC 95 % bas"),
        ("ci_high", "IC 95 % haut"), ("beta", "β"), ("corr", "Corrélation"),
        ("geometric_closed_form", "Géométrique (formule fermée)"),
        ("var_ratio_vs_plain", "Variance ÷"), ("time_median_s", "Temps médian (s)"),
        ("efficiency_gain_vs_plain", "Gain d'efficacité (une mesure du temps)"),
        ("n_paths", "N"), ("seed", "Graine")]),
    ("A5 Convergence", "p4_convergence.csv", [
        ("estimator", "Estimateur"), ("n_paths", "N"), ("price", "Prix"),
        ("std_error", "Écart-type"), ("half_width_95", "Demi-largeur IC 95 %"),
        ("ci_low", "IC 95 % bas"), ("ci_high", "IC 95 % haut"), ("seed", "Graine")]),
    ("A6 Pentes", "p4_convergence_slopes.csv", [
        ("estimator", "Estimateur"), ("n_points", "Points"), ("n_min", "N min"),
        ("n_max", "N max"), ("slope", "Pente mesurée"), ("slope_std_error", "Écart-type de la pente"),
        ("expected_slope", "Pente attendue")]),
    ("A7 N nécessaire", "p4_n_required.csv", [
        ("estimator", "Estimateur"), ("epsilon", "Marge ε"), ("sigma_hat", "σ̂ des gains"),
        ("sigma_hat_n_paths", "N de l'estimation de σ̂"), ("n_required", "N nécessaire"),
        ("time_estimated_s", "Temps estimé (s)"), ("seed", "Graine")]),
    ("A8 Temps égal", "p4_equal_time.csv", [
        ("estimator", "Estimateur"), ("budget_s", "Budget (s)"), ("n_paths", "N atteint"),
        ("time_s", "Temps mesuré (s)"), ("price", "Prix"), ("std_error", "Écart-type"),
        ("half_width_95", "Demi-largeur IC 95 %"), ("seed", "Graine")]),
    ("A9 Biais de β", "p4_beta_bias.csv", [
        ("beta_mode", "β"), ("n_seeds", "Répétitions"), ("n_paths", "N par répétition"),
        ("n_pilot", "N du pilote"), ("mean_price", "Prix moyen"), ("ref_price", "Référence"),
        ("ref_std_error", "Écart-type de la référence"), ("ref_n_paths", "N de la référence"),
        ("bias", "Biais"), ("bias_in_sd_of_mean", "Biais (en écarts-types)"),
        ("ci95_coverage", "Couverture de l'IC 95 %"), ("mean_beta", "β moyen")]),
    ("A10 Méthodes d'aléa", "p4_rng_methods.csv", [
        ("rng_method", "Méthode"), ("control", "Contrôle"), ("price", "Prix"),
        ("std_error", "Écart-type"), ("ci_low", "IC 95 % bas"), ("ci_high", "IC 95 % haut"),
        ("uniforms_per_normal", "Uniformes par normale"), ("time_median_s", "Temps médian (s)"),
        ("minus_ref_in_se", "Écart à la référence (en écarts-types)"), ("n_paths", "N"),
        ("seed", "Graine")]),
    ("A11 Fréquence", "p4_frequency.csv", [
        ("option", "Option"), ("n_obs", "Observations"), ("price", "Asiatique"),
        ("std_error", "Écart-type"), ("geometric_exact", "Géométrique discrète (exacte)"),
        ("geometric_continuous", "Géométrique continue"),
        ("euro_bs_price", "Européenne (Black-Scholes)"),
        ("ratio_to_euro_bs", "Ratio asiatique / européenne"), ("n_paths", "N"),
        ("seed", "Graine")]),
    ("A12 Exercice slide 77", "p4_ex77.csv", [
        ("option", "Option"), ("K", "Strike K"), ("geometric_exact", "Géométrique (exacte)"),
        ("arithmetic_reference", "Référence arithmétique"), ("mc_price", "Monte-Carlo"),
        ("mc_std_error", "Écart-type MC"), ("cv_price", "Avec contrôle"),
        ("cv_std_error", "Écart-type contrôle"), ("variance_ratio", "Variance ÷"),
        ("ref_in_mc_ci99", "Référence dans l'IC 99 % (MC)"),
        ("ref_in_cv_ci99", "Référence dans l'IC 99 % (contrôle)"), ("n_paths", "N"),
        ("ref_n_paths", "N de la référence"), ("seed", "Graine")]),
    ("A13 Exercice slide 78", "p4_ex78.csv", [
        ("option", "Option"), ("K", "Strike K"), ("n_paths", "N"),
        ("price_exact", "Prix exact (Black-Scholes)"), ("mc_price", "Monte-Carlo"),
        ("mc_std_error", "Écart-type MC"), ("anti_price", "Antithétique"),
        ("anti_std_error", "Écart-type antithétique"),
        ("antithetic_corr", "Corrélation h(Z), h(−Z)"),
        ("estimator_var_ratio_mc_over_anti", "Variance ÷"),
        ("exact_in_mc_ci99", "Exact dans l'IC 99 % (MC)"),
        ("exact_in_anti_ci99", "Exact dans l'IC 99 % (anti.)"), ("seed", "Graine")]),
    ("A14 Greeks", "p4_greeks.csv", [
        ("kind", "Option"), ("option", "Type"), ("K", "Strike K"),
        ("crn", "Nombres aléatoires communs"), ("control", "Contrôle"), ("price", "Prix"),
        ("delta", "Delta"), ("delta_se", "Écart-type delta"), ("gamma", "Gamma"),
        ("gamma_se", "Écart-type gamma"), ("vega", "Vega"), ("vega_se", "Écart-type vega"),
        ("bs_delta", "Delta BS"), ("bs_gamma", "Gamma BS"), ("bs_vega", "Vega BS"),
        ("n_paths", "N"), ("seed", "Graine")]),
    ("A15 EUR-USD", "p5_eurusd.csv", [
        ("strike_type", "Strike"), ("option", "Option"), ("K", "K (USD pour 1 EUR)"),
        ("asian_price", "Asiatique"), ("asian_std_error", "Écart-type"),
        ("asian_ci_low", "IC 95 % bas"), ("asian_ci_high", "IC 95 % haut"),
        ("asian_pct_S0", "Asiatique (% de S0)"), ("euro_bs_price", "Européenne (Black-Scholes)"),
        ("euro_bs_pct_S0", "Européenne (% de S0)"),
        ("ratio_asian_euro_bs", "Ratio asiatique / européenne"), ("variance_ratio", "Variance ÷"),
        ("hedge_cost_eur", "Prime (EUR)"), ("n_paths", "N"), ("seed", "Graine")]),
    ("A16 EUR-USD selon σ", "p5_eurusd_sensitivity.csv", [
        ("sigma", "σ"), ("sigma_label", "Type de σ"), ("strike_type", "Strike"),
        ("option", "Option"), ("asian_price", "Asiatique"), ("asian_std_error", "Écart-type"),
        ("asian_pct_S0", "Asiatique (% de S0)"), ("euro_bs_price", "Européenne (Black-Scholes)"),
        ("euro_bs_pct_S0", "Européenne (% de S0)"),
        ("ratio_asian_euro_bs", "Ratio asiatique / européenne"), ("n_paths", "N"),
        ("seed", "Graine")]),
]


# --- lecture -------------------------------------------------------------------------------------

def rows(path: Path | str) -> list[dict]:
    data = px._read(RESULTS / path if isinstance(path, str) else path)
    return [dict(zip(data[0], r)) for r in data[1:]]


def _eq(have: str, want) -> bool:
    if isinstance(want, str):
        return have == want
    return have != "" and math.isclose(float(have), float(want), rel_tol=1e-12)


def one(table: list[dict], **where) -> dict:
    hits = [r for r in table if all(_eq(r[k], v) for k, v in where.items())]
    if len(hits) != 1:
        raise LookupError(f"{len(hits)} ligne(s) pour {where}")
    return hits[0]


def og_value(v: float, sig: int = 2) -> float:
    """Ordre de grandeur, en nombre : sig chiffres significatifs (1 401,9 → 1 400)."""
    exp = math.floor(math.log10(abs(v)))
    return round(v / 10 ** (exp - sig + 1)) * 10 ** (exp - sig + 1)


def og_format(v: float) -> str:
    return "#,##0" if abs(v) >= 10 else "0.0"


def efficiency_env(T: float, option: str, estimator: str) -> float:
    """Gain d'efficacité à l'ordre de grandeur : moyenne des deux mesures du temps (règle du
    tableau 1 du rapport), arrondie à 2 chiffres significatifs."""
    at = {"T": T, "option": option, "estimator": estimator}
    now = float(one(rows("p3_vr_atm.csv"), **at)["efficiency_gain_vs_plain"])
    before = float(one(rows(HISTORY), **at)["efficiency_gain_vs_plain"])
    return og_value((now + before) / 2)


def gain_dispersion() -> tuple[float, float]:
    """Écart relatif min et max entre les deux mesures d'un même gain (hors « sans réduction »)."""
    old = rows(HISTORY)
    rel = [float(r["efficiency_gain_vs_plain"])
           / float(one(old, T=float(r["T"]), option=r["option"],
                       estimator=r["estimator"])["efficiency_gain_vs_plain"]) - 1
           for r in rows("p3_vr_atm.csv") if r["estimator"] != "plain"]
    return min(rel), max(rel)


def french(value):
    return WORDS.get(value, value) if isinstance(value, str) else value


def fr_date(iso: str) -> str:
    y, mth, d = iso.split("-")
    return f"{d}/{mth}/{y}"


def num(row: dict, col: str):
    """(valeur, format du classeur du groupe) d'une cellule CSV."""
    v = px.parse_cell(row[col])
    return v, px.number_format(col, v)


# --- mise en forme -------------------------------------------------------------------------------

def _font(size=10, bold=False, color=None):
    kw = {"color": color} if color else {}
    return Font(name=FONT_SANS, size=size, bold=bold, **kw)


class Sheet:
    """Écriture ligne à ligne d'un onglet (titres, notes, petits tableaux, figures)."""

    def __init__(self, ws):
        self.ws, self.row = ws, 1

    def title(self, text):
        self.ws.cell(self.row, 1, text).font = _font(16, bold=True)
        self.row += 1

    def section(self, text):
        self.row += 1
        self.ws.cell(self.row, 1, text).font = _font(13, bold=True, color=px.HEX["a2"])
        self.row += 1

    def note(self, text):
        c = self.ws.cell(self.row, 1, text)
        c.font = _font(10, color=NOTE_COLOR)
        c.alignment = Alignment(vertical="top")
        self.row += 1

    def table(self, header, body):
        """body : lignes de cellules, chacune « valeur » ou « (valeur, format Excel) »."""
        px._header(self.ws, self.row, header)
        self.row += 1
        for line in body:
            for j, cell in enumerate(line, start=1):
                value, fmt = cell if isinstance(cell, tuple) else (cell, None)
                c = self.ws.cell(self.row, j, value)
                if fmt:
                    c.number_format, c.font = fmt, Font(name=FONT_MONO, size=10)
                else:
                    c.font = px.TEXT_FONT
            self.row += 1

    def image(self, name: str, at_row: int) -> int:
        """Figure du mode rendu à droite des tableaux ; renvoie la ligne sous l'image."""
        png = FIG_DIR / f"{name}.png"
        with Image.open(png) as im:
            w, h = im.size
        img = XLImage(str(png))
        img.width, img.height = IMAGE_WIDTH_PX, round(h * IMAGE_WIDTH_PX / w)
        self.ws.add_image(img, f"{IMAGE_COL}{at_row}")
        return at_row + math.ceil(img.height / ROW_PX) + 1

    def skip_to(self, row):
        self.row = max(self.row, row)


# --- onglet Synthèse -----------------------------------------------------------------------------

def theoretical_line(g: dict) -> str:
    return (f"Actif théorique : S0 = {fmt_int(float(g['S0']))}, σ = {fmt_pct(float(g['sigma']), 0)}, "
            f"r = {fmt_pct(float(g['r']), 0)}, q = {fmt_pct(float(g['q']), 0)}, observation "
            f"{OBS[g['obs']]} ; N = {fmt_int(float(g['n_paths']))} trajectoires, graine {g['seed']}, "
            f"normales par transformée inverse (AS241) d'un générateur congruentiel linéaire.")


def _eps_label(e: float) -> str:
    return fmt_num(e, len(f"{e:g}") - 2)


def sheet_synthesis(wb) -> None:
    ws = wb.active
    ws.title = "Synthèse"
    ws.sheet_properties.tabColor = px.HEX["a1"]
    ws.sheet_view.showGridLines = False
    s = Sheet(ws)
    grid = rows("p4_grid_cv.csv")
    g = one(grid, K=100, T=1, option="call")
    T1 = [r for r in rows("p3_vr_atm.csv") if float(r["T"]) == 1]

    s.title("L'option asiatique, pricée par Monte-Carlo : résultats")
    s.note("Projet Pricing Monte-Carlo, énoncé 2 · ECE Paris, ING4 Finance · "
           "cours d'A. W. Sanoussi Mani")
    s.note("Groupe : " + ", ".join(GROUP) + ".")
    s.note("Toutes les valeurs sont recopiées des fichiers de résultats (CSV) produits par le code "
           "Python : aucune formule, aucun chiffre saisi à la main. Prix à 10⁻⁴ ; écarts-types sous "
           "10⁻⁴ en notation scientifique.")
    s.note(theoretical_line(g))

    # Question 1
    s.section("Question 1 · Prix Monte-Carlo du call et du put asiatiques (moyenne arithmétique)")
    top = s.row
    s.note(f"T = 1 an, K = S0 = {fmt_int(float(g['K']))}, observation mensuelle ; méthode simple, "
           "puis avec la variable de contrôle géométrique.")
    body = []
    for option in ("call", "put"):
        for est in ("plain", "control_beta_optimal"):
            r = one(T1, option=option, estimator=est)
            body.append([option, ESTIMATORS[est], num(r, "price"), num(r, "std_error"),
                         num(r, "ci_low"), num(r, "ci_high"), num(r, "n_paths"), num(r, "seed")])
    s.table(["Option", "Estimateur", "Prix", "Écart-type", "IC 95 % bas", "IC 95 % haut", "N",
             "Graine"], body)
    s.skip_to(s.image("fig1_eventail_eurusd", top))

    # Question 2
    s.section("Question 2 · Asiatique contre européenne de mêmes caractéristiques")
    top = s.row
    s.note(f"Asiatique avec contrôle géométrique, européenne par la formule de Black-Scholes ; "
           f"K = {fmt_int(float(g['K']))}, quatre maturités.")
    body = []
    for option in ("call", "put"):
        for r in sorted((x for x in grid if x["option"] == option and float(x["K"]) == 100),
                        key=lambda x: float(x["T"])):
            body.append([option, (float(r["T"]), "0.00"), num(r, "price"), num(r, "std_error"),
                         num(r, "euro_bs_price"), num(r, "ratio")])
    s.table(["Option", "T (ans)", "Asiatique", "Écart-type", "Européenne (Black-Scholes)",
             "Ratio asiatique / européenne"], body)
    s.row += 1
    Ks = sorted({float(r["K"]) for r in grid})
    s.note("Ratio asiatique / européenne pour chaque strike et chaque maturité :")
    body = []
    for option in ("call", "put"):
        for T in sorted({float(r["T"]) for r in grid}):
            body.append([option, (T, "0.00"),
                         *(num(one(grid, K=K, T=T, option=option), "ratio") for K in Ks)])
    s.table(["Option", "T (ans)", *(f"K = {fmt_int(K)}" for K in Ks)], body)
    under = sum(float(r["ratio"]) < 1 for r in grid)
    s.note(f"L'asiatique vaut moins que l'européenne dans {under} cas sur {len(grid)} : la moyenne "
           "des cours est moins dispersée que le cours final.")
    s.skip_to(s.image("fig2_disques_ratio", top))

    # Question 3
    s.section("Question 3 · Réduction de variance : la moyenne géométrique comme variable de "
              "contrôle")
    top = s.row
    s.note("T = 1 an, K = S0. Variance ÷ : variance sans réduction divisée par celle de "
           "l'estimateur, à N égal.")
    body = []
    for est in ("plain", "antithetic", "control_beta_1", "control_beta_optimal",
                "antithetic_control"):
        c, p = one(T1, option="call", estimator=est), one(T1, option="put", estimator=est)
        gain = efficiency_env(1, "call", est)
        body.append([ESTIMATORS[est], num(c, "price"), num(c, "std_error"), num(p, "price"),
                     num(p, "std_error"), num(c, "var_ratio_vs_plain"),
                     num(p, "var_ratio_vs_plain"), (gain, og_format(gain))])
    s.table(["Estimateur", "Call", "Écart-type", "Put", "Écart-type", "Variance ÷ (call)",
             "Variance ÷ (put)", "Efficacité, environ (call)"], body)
    lo, hi = gain_dispersion()
    s.note("Efficacité : gain sur variance × temps de calcul, contre « sans réduction » ; moyenne de "
           "deux mesures du temps arrondie à 2 chiffres significatifs (un même gain a varié de "
           f"{fmt_num(100 * lo, 0)} % à +{fmt_num(100 * hi, 0)} % d'une mesure à l'autre).")
    ctrl = one(T1, option="call", estimator="control_beta_optimal")
    s.note("Corrélation des gains arithmétique et géométrique (call) : "
           f"{fmt_num(float(ctrl['corr']), 4)} ; β estimé : {fmt_num(float(ctrl['beta']), 4)}.")
    s.skip_to(s.image("fig5_nuage_payoffs", top))

    # Question 4
    s.section("Question 4 · Gain de temps et de précision")
    top = s.row
    need = rows("p4_n_required.csv")
    slopes = {r["estimator"]: r for r in rows("p4_convergence_slopes.csv")}
    eps = sorted({float(r["epsilon"]) for r in need}, reverse=True)
    estimators = ("plain", "antithetic", "control", "antithetic_control")
    s.note("Nombre de trajectoires nécessaire pour une demi-largeur d'IC à 95 % donnée (call, "
           "T = 1, K = S0), et pente de la marge d'erreur contre N en échelles logarithmiques.")
    body = []
    for est in estimators:
        body.append([ESTIMATORS[est],
                     *(num(one(need, estimator=est, epsilon=e), "n_required") for e in eps),
                     *(num(one(need, estimator=est, epsilon=e), "time_estimated_s") for e in eps),
                     num(slopes[est], "slope")])
    s.table(["Estimateur", *(f"N pour ±{_eps_label(e)}" for e in eps),
             *(f"Temps pour ±{_eps_label(e)} (s)" for e in eps), "Pente mesurée"], body)
    s.row += 1
    eq = rows("p4_equal_time.csv")
    budget = max(float(r["budget_s"]) for r in eq)
    s.note(f"À temps de calcul égal ({fmt_num(budget, 0)} s) :")
    body = []
    for est in estimators:
        r = one(eq, estimator=est, budget_s=budget)
        body.append([ESTIMATORS[est], num(r, "n_paths"), num(r, "price"), num(r, "half_width_95")])
    s.table(["Estimateur", "N atteint", "Prix", "Demi-largeur IC 95 %"], body)
    s.skip_to(s.image("fig3_gain_efficacite", s.image("fig4_convergence", top)))

    # Cas EUR/USD
    s.section("Cas réel · EUR/USD : la couverture de change d'un exportateur")
    top = s.row
    m = {r["name"]: r for r in rows("p5_market.csv")}
    fx = rows("p5_eurusd.csv")
    call = one(fx, strike_type="spot", option="call")
    s.note(f"Un exportateur encaisse {fmt_int(float(call['usd_per_month']))} USD par mois pendant "
           f"{call['n_months']} mois : call asiatique sur EUR/USD, {call['n_obs']} observations "
           f"mensuelles, T = 1 an. Calibration du {fr_date(m['S0']['date'])} : "
           f"S0 = {fmt_num(float(m['S0']['value']), 4)}, "
           f"σ = {fmt_pct(float(m['sigma_ecb']['value']), 2)}, "
           f"r = {fmt_pct(float(m['r_usd']['value']), 2)} (dollar), "
           f"q = {fmt_pct(float(m['q_eur']['value']), 2)} (euro).")
    body = [[STRIKES[r["strike_type"]], r["option"], num(r, "K"), num(r, "asian_price"),
             num(r, "asian_std_error"), num(r, "asian_ci_low"), num(r, "asian_ci_high"),
             num(r, "euro_bs_price"), num(r, "ratio_asian_euro_bs"), num(r, "variance_ratio")]
            for r in fx]
    s.table(["Strike", "Option", "K (USD pour 1 EUR)", "Asiatique", "Écart-type", "IC 95 % bas",
             "IC 95 % haut", "Européenne (Black-Scholes)", "Ratio", "Variance ÷"], body)
    s.note(f"Prime du call asiatique K = S0 : {fmt_int(float(call['hedge_cost_eur']))} EUR, soit "
           f"{fmt_num(float(call['asian_pct_S0']), 2)} % du cours contre "
           f"{fmt_num(float(call['euro_bs_pct_S0']), 2)} % pour l'européenne. "
           f"N = {fmt_int(float(call['n_paths']))}, graine {call['seed']}.")
    s.row += 1
    sens = [r for r in rows("p5_eurusd_sensitivity.csv")
            if r["strike_type"] == "spot" and r["sigma_label"] == "grille"]
    s.note("Faute de volatilité implicite, prix selon σ (K = S0, en % de S0) :")
    body = []
    for sigma in sorted({float(r["sigma"]) for r in sens}):
        c, p = (one(sens, sigma=sigma, option=o) for o in ("call", "put"))
        body.append([(sigma, "0%"), num(c, "asian_pct_S0"), num(c, "euro_bs_pct_S0"),
                     num(p, "asian_pct_S0"), num(p, "euro_bs_pct_S0")])
    s.table(["σ", "Call asiatique (%)", "Call européen (%)", "Put asiatique (%)",
             "Put européen (%)"], body)
    s.skip_to(s.image("fig6_eurusd_sigma", top))

    for col, width in zip("ABCDEFGHIJ", (26, 22, 14, 14, 14, 16, 16, 16, 12, 12)):
        ws.column_dimensions[col].width = width


# --- onglet Paramètres et sources ----------------------------------------------------------------

def manifest_rows() -> list[dict]:
    """Premier tableau de data/raw/MANIFEST.md (un relevé par ligne)."""
    head, out = None, []
    for line in (ROOT / "data" / "raw" / "MANIFEST.md").read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            if head:
                break
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if head is None:
            head = cells
        elif set(cells[0]) - set("-"):
            out.append(dict(zip(head, cells)))
    return out


def sheet_parameters(wb) -> None:
    ws = wb.create_sheet("Paramètres et sources")
    ws.sheet_properties.tabColor = px.HEX["a2"]
    ws.sheet_view.showGridLines = False
    s = Sheet(ws)
    grid = rows("p4_grid_cv.csv")
    g = one(grid, K=100, T=1, option="call")
    s.title("Paramètres et sources")

    s.section("Actif théorique (validation du pricer)")
    s.note(f"S0 = {fmt_int(float(g['S0']))} pour lire chaque prix en % du spot ; σ, r et q usuels "
           "qui font jouer tous les paramètres du pricer, dividende compris ; cadre Black-Scholes où "
           "des formules fermées (européenne, moyenne géométrique) valident le pricer avant "
           "l'application réelle.")
    body = [["Spot S0", num(g, "S0"), "", ""],
            ["Strikes K", " · ".join(fmt_int(K) for K in sorted({float(r["K"]) for r in grid})),
             "", "grille de comparaison"],
            ["Maturités T", " · ".join(f"{T:g}".replace(".", ",")
                                       for T in sorted({float(r["T"]) for r in grid})), "an", ""],
            ["Volatilité σ", (float(g["sigma"]), "0%"), "par an", ""],
            ["Taux sans risque r", (float(g["r"]), "0%"), "continu, par an", ""],
            ["Dividende q", (float(g["q"]), "0%"), "continu, par an", "dividende continu"],
            ["Observation du spot", OBS[g["obs"]], "", f"{g['n_obs']} dates par an"],
            ["Trajectoires N", num(g, "n_paths"), "", ""],
            ["Graine", num(g, "seed"), "", "même graine pour tous les résultats"],
            ["Générateur", f"congruentiel linéaire de Park-Miller, a = {PARK_MILLER_A}, "
                           "m = 2³¹ − 1", "", ""],
            ["Normales", METHODS[g["rng_method"]], "", "méthode par défaut du pricer"]]
    s.table(["Paramètre", "Valeur", "Unité", "Note"], body)

    s.section("EUR/USD (actif réel, modèle de Garman-Kohlhagen : q joue le rôle du dividende)")
    m = {r["name"]: r for r in rows("p5_market.csv")}

    def market(name, label, fmt, source, note=""):
        r = m[name]
        return [label, (float(r["value"]), fmt), r["unit"], fr_date(r["date"]), source, note]

    body = [
        market("S0", "Spot S0", "0.0000", "BCE, fixing de référence EUR/USD", "dernier fixing"),
        market("sigma_ecb", "Volatilité σ", "0.00%", "BCE, fixings de référence sur un an",
               f"historique 1 an, depuis le {fr_date(m['sigma_ecb']['date_first'])}"),
        market("sigma_av", "Volatilité σ (contrôle)", "0.00%", ALPHA_VANTAGE,
               "contrôle croisé de la volatilité"),
        market("y_usd_1y_pct", "Rendement Trésor 1 an publié", "0.00", "Trésor américain",
               "en %, base semestrielle (« bond-equivalent »)"),
        market("r_usd", "Taux dollar r", "0.00%", "Trésor américain, 1 an",
               "r = 2·ln(1 + y/2), composition continue"),
        market("y_eur_1y_pct", "Taux AAA zone euro 1 an publié", "0.00", "BCE, courbe AAA",
               "en %, déjà en composition continue"),
        market("q_eur", "Taux euro q", "0.00%", "BCE, courbe AAA, spot 1 an", "q = y / 100"),
        market("estr_pct", "€STR", "0.00", "BCE", "en %, comparaison seulement"),
        market("forward_1y", "Forward 1 an", "0.0000", "calcul", "S0·exp((r − q)·1)"),
        market("xcheck_mean_abs_diff", "Écart moyen BCE − Alpha Vantage", "0.0000",
               "BCE et Alpha Vantage",
               f"écart absolu moyen sur {m['xcheck_n_common']['value']} jours communs"),
    ]
    s.table(["Paramètre", "Valeur", "Unité", "Date", "Source", "Note"], body)

    s.section("Sources")
    body = []
    for r in manifest_rows():
        if "alphavantage" in r["Fichier"]:
            continue
        when = r["Relevé"]
        body.append([r["Source"], r["URL"], f"{fr_date(when[:10])} {when[11:16]}"])
    body.append([ALPHA_VANTAGE, ALPHA_VANTAGE_URL, ""])
    read_on = re.search(r"lues le (\d{2}/\d{2}/\d{4})", m["r_usd"]["note"]).group(1)
    body.append(["Trésor américain, FAQ sur les taux (convention « bond-equivalent »)",
                 TREASURY_SOURCES[0], read_on])
    body.append(["Réserve fédérale, FEDS 2006-28, éq. (4)", TREASURY_SOURCES[1], read_on])
    body.append(["Cours « Pricing Monte-Carlo » 2026, A. W. Sanoussi Mani",
                 "slides et polycopié du cours", ""])
    s.table(["Source", "URL", "Relevé"], body)
    for col, width in zip("ABCDEF", (40, 70, 18, 12, 34, 44)):
        ws.column_dimensions[col].width = width


# --- annexes -------------------------------------------------------------------------------------

def sheet_annex(wb, name: str, csv_name: str, columns) -> None:
    ws = wb.create_sheet(name)
    ws.sheet_properties.tabColor = px.HEX["a2"]
    px._header(ws, 1, [fr for _col, fr in columns])
    for i, r in enumerate(rows(csv_name), start=2):
        for j, (col, _fr) in enumerate(columns, start=1):
            v = px.parse_cell(r[col])
            if isinstance(v, bool):
                v = "oui" if v else "non"
            elif col == "control" and v is None:
                v = "aucun"
            c = ws.cell(i, j, french(v))
            fmt = px.number_format(col, v)
            if fmt:
                c.number_format, c.font = fmt, px.NUM_FONT
            else:
                c.font = px.TEXT_FONT
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = ws.dimensions
    px._widths(ws)


def build(out: Path = OUT) -> Path:
    wb = Workbook()
    wb.properties.creator = "Projet Pricing Monte-Carlo, ECE Paris ING4"
    sheet_synthesis(wb)
    sheet_parameters(wb)
    for name, csv_name, columns in ANNEXES:
        sheet_annex(wb, name, csv_name, columns)
    out.parent.mkdir(exist_ok=True)
    wb.save(out)
    return out


def main() -> None:
    out = build()
    print(f"{out.relative_to(ROOT)}  {out.stat().st_size:,} octets ; onglets : Synthèse, "
          f"Paramètres et sources, {', '.join(a[0] for a in ANNEXES)}")


if __name__ == "__main__":
    main()
