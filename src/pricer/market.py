"""Données de marché de l'actif réel EUR/USD (P5a) : lecture, taux continus, volatilité historique.

Actif : taux de change EUR/USD, S = prix d'un euro en dollars. Modèle de Garman-Kohlhagen (hors
cours ; c'est le modèle de Black-Scholes avec dividende continu du cours, slide 61) :
    dS_t/S_t = (r − q)dt + σ dW_t,   r = taux sans risque domestique (USD),
                                     q = taux sans risque étranger (EUR), qui joue le dividende.

Lecture (read_series) : CSV brut de data/raw/, une colonne de date (ISO AAAA-MM-JJ ou américaine
MM/JJ/AAAA) et une colonne de valeur. Valeurs manquantes (« . » d'Alpha Vantage, cellule vide de la
BCE, « N/A ») = jour absent, jamais 0. Tout autre texte non numérique lève une erreur.

Taux (to_continuous) : y en décimal (0,0462 pour 4,62 %), converti en taux continu r tel que
1 € placé vaille e^{r·1} au bout d'un an :
    "annual"      composition annuelle      r = ln(1 + y)
    "semiannual"  composition semestrielle  r = 2·ln(1 + y/2)
    "continuous"  déjà continu              r = y

Volatilité (historical_vol, hors cours) : σ̂ = s·√252, s = écart-type empirique (en 1/(n − 1),
slide 49) des n − 1 log-rendements ln(S_k/S_{k−1}) des n = window derniers points ; 252 jours ouvrés
par an. Moyenne des rendements estimée (non forcée à 0).
"""
from __future__ import annotations

import csv
import math
from datetime import date, datetime
from pathlib import Path

import numpy as np

# Convention des rendements de la courbe par du Trésor américain (P5b, Q2) : « bond-equivalent »,
# intérêts semestriels, APY = (1 + i/2)² − 1, donc r = 2·ln(1 + y/2) en continu. Sources (lues le
# 17/11/2026) :
#   FAQ du Trésor : https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics/interest-rates-frequently-asked-questions
#   Fed, FEDS 2006-28, éq. (4) y = 2·ln(1 + y_ce/2) : https://www.federalreserve.gov/pubs/feds/2006/200628
TREASURY_CONVENTION = "semiannual"
TREASURY_SOURCES = (
    "https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics/"
    "interest-rates-frequently-asked-questions",
    "https://www.federalreserve.gov/pubs/feds/2006/200628",
)

MISSING = frozenset({"", ".", "N/A", "NA", "NaN", "nan"})
CONVENTIONS = ("annual", "semiannual", "continuous")
TRADING_DAYS = 252


def _parse_date(text: str) -> date:
    text = text.strip()
    fmt = "%m/%d/%Y" if "/" in text else "%Y-%m-%d"
    return datetime.strptime(text, fmt).date()


def read_series(path, date_col: str, value_col: str) -> list[tuple[date, float]]:
    """[(date, valeur)] trié par date croissante ; jours sans valeur omis (jamais remplacés)."""
    out: dict[date, float] = {}
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            raw = (row[value_col] or "").strip()
            if raw in MISSING:
                continue
            try:
                value = float(raw)
            except ValueError:
                raise ValueError(f"{Path(path).name} : valeur non numérique {raw!r} "
                                 f"le {row[date_col]}") from None
            d = _parse_date(row[date_col])
            if d in out:
                raise ValueError(f"{Path(path).name} : date en double {d}")
            out[d] = value
    return sorted(out.items())


def last_on_or_before(series, day: date) -> tuple[date, float]:
    """Dernier point (date, valeur) de la série à une date ≤ day."""
    pts = [p for p in series if p[0] <= day]
    if not pts:
        raise ValueError(f"aucune valeur au plus tard le {day}")
    return pts[-1]


def to_continuous(y: float, convention: str) -> float:
    """Taux continu équivalent à y (décimal) dans la convention de composition donnée."""
    if convention not in CONVENTIONS:
        raise ValueError(f"convention inconnue {convention!r} ; choix : {CONVENTIONS}")
    y = float(y)
    if not (-1.0 < y < 1.0):
        raise ValueError(f"taux {y!r} : attendu en décimal (0,0462 pour 4,62 %)")
    if convention == "annual":
        return math.log1p(y)
    if convention == "semiannual":
        return 2.0 * math.log1p(y / 2.0)
    return y


def treasury_par_to_continuous(y: float) -> float:
    """Taux continu d'un rendement de la courbe par du Trésor (décimal) : r = 2·ln(1 + y/2)."""
    return to_continuous(y, TREASURY_CONVENTION)


def log_returns(prices) -> np.ndarray:
    p = np.asarray(prices, dtype=float)
    if np.any(p <= 0.0):
        raise ValueError("cours ≤ 0")
    return np.diff(np.log(p))


def historical_vol(prices, window: int = TRADING_DAYS, periods_per_year: int = TRADING_DAYS) -> float:
    """σ annualisé sur les window derniers points : std(log-rendements, ddof=1)·√periods_per_year."""
    p = np.asarray(prices, dtype=float)
    if window < 3 or p.size < window:
        raise ValueError(f"il faut au moins window = {window} ≥ 3 points (reçu {p.size})")
    r = log_returns(p[-window:])
    return float(np.std(r, ddof=1) * math.sqrt(periods_per_year))


def cross_check(a, b, n: int = TRADING_DAYS) -> dict:
    """Écart a − b sur les n dernières dates communes aux deux séries [(date, valeur)]."""
    db = dict(b)
    common = [(d, v, db[d]) for d, v in a if d in db][-n:]
    if not common:
        raise ValueError("aucune date commune")
    diff = np.array([va - vb for _, va, vb in common])
    k = int(np.argmax(np.abs(diff)))
    return dict(n_common=len(common), first=common[0][0], last=common[-1][0],
                mean_diff=float(diff.mean()), mean_abs_diff=float(np.abs(diff).mean()),
                max_abs_diff=float(np.abs(diff[k])), max_abs_diff_date=common[k][0])
