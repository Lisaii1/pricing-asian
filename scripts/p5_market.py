"""Calibration de l'actif réel EUR/USD → results/p5_market.csv.

Entrées : relevés bruts de data/raw/ (voir data/raw/MANIFEST.md), aucun appel réseau.
  S0     dernier fixing de référence BCE EUR/USD (USD pour 1 EUR, 14 h 15 CET), date écrite.
  σ      historique : écart-type (1/(n − 1)) des log-rendements des 252 derniers fixings BCE
         (251 rendements), × √252 ; même calcul sur les 252 dernières clôtures Alpha Vantage.
  r      USD (domestique) : Trésor américain 1 an (« 1 Yr ») au plus tard à la date de S0. Rendement
         de la courbe par, « bond-equivalent », intérêts semestriels (FAQ du Trésor ; Fed FEDS
         2006-28 éq. (4)) : r = 2·ln(1 + y/2) (sources dans pricer.market).
         Variante ln(1 + y) (base annuelle) écrite pour comparaison.
  q      EUR (étranger, joue le dividende, Garman-Kohlhagen) : BCE, courbe AAA zone euro, taux spot
         1 an au plus tard à la date de S0. La réponse BCE le dit « continuous compounding »
         (colonne TITLE_COMPL) : q = y, sans conversion. La variante ln(1 + y) est écrite
         pour comparaison.
  Pour comparaison seulement : €STR (BCE, au jour le jour) et bons du Trésor 3 mois (Alpha Vantage),
  en % tels que publiés.
  Contrôle croisé : fixing BCE − clôture Alpha Vantage du même jour, 252 derniers jours communs.
  Forward 1 an : F = S0·e^{(r − q)·1}.

Usage : .venv/Scripts/python.exe scripts/p5_market.py
"""
from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pricer.market import (TREASURY_SOURCES, cross_check, historical_vol,  # noqa: E402
                           last_on_or_before, read_series, to_continuous,
                           treasury_par_to_continuous)

RAW = ROOT / "data" / "raw"
OUT = ROOT / "results" / "p5_market.csv"
ECB_FX = RAW / "2026-11-17_ecb_EXR_D.USD.EUR.SP00.A.csv"
AV_FX = RAW / "2026-11-17_alphavantage_FX_DAILY_EURUSD_full.csv"
UST = RAW / "2026-11-17_treasury_daily_yield_curve_2026.csv"
YC = RAW / "2026-11-17_ecb_YC_B.U2.EUR.4F.G_N_A.SV_C_YM.SR_1Y.csv"
ESTR = RAW / "2026-11-17_ecb_EST_B.EU000A2X2A25.WT.csv"
AV_3M = RAW / "2026-11-17_alphavantage_TREASURY_YIELD_3month_daily_sample.csv"
WINDOW = 252
FIELDS = ["name", "value", "unit", "date", "date_first", "source", "convention", "note"]


def _ecb_title_compl(path: Path) -> str:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return next(csv.DictReader(f))["TITLE_COMPL"]


def calibrate() -> dict:
    """Dictionnaire {nom: ligne} des paramètres de marché (valeurs en décimal sauf mention)."""
    ecb = read_series(ECB_FX, "TIME_PERIOD", "OBS_VALUE")
    av = read_series(AV_FX, "timestamp", "close")
    d0, S0 = ecb[-1]
    rows = {}

    def put(name, value, unit, day, source, convention="", note="", first=""):
        rows[name] = dict(name=name, value=value, unit=unit, date=str(day), date_first=str(first),
                          source=source, convention=convention, note=note)

    put("S0", S0, "USD pour 1 EUR", d0, ECB_FX.name, "fixing de référence BCE",
        "dernier fixing disponible")
    for name, series, src in (("sigma_ecb", ecb, ECB_FX.name), ("sigma_av", av, AV_FX.name)):
        win = series[-WINDOW:]
        put(name, historical_vol([v for _, v in series], WINDOW), "par an", win[-1][0], src,
            "std(ln S_k/S_{k-1}, ddof=1)·√252 sur 252 points (251 rendements)",
            "BCE : prix central" if name == "sigma_ecb" else "contrôle", first=win[0][0])

    d_r, y_r = last_on_or_before(read_series(UST, "Date", "1 Yr"), d0)
    put("r_usd", treasury_par_to_continuous(y_r / 100), "continu, par an", d_r, UST.name,
        "2·ln(1 + y/2), y = 1 Yr / 100 (bond-equivalent, semestriel)",
        f"y = {y_r} % ; sources (lues le 17/11/2026) : " + " ; ".join(TREASURY_SOURCES))
    put("r_usd_annual_alt", to_continuous(y_r / 100, "annual"), "continu, par an", d_r,
        UST.name, "ln(1 + y)", "comparaison : base annuelle, non retenue")
    put("y_usd_1y_pct", y_r, "% publié", d_r, UST.name, "tel que publié", "")

    compl = _ecb_title_compl(YC)
    if "continuous compounding" not in compl:
        raise RuntimeError(f"courbe BCE : convention inattendue ({compl})")
    d_q, y_q = last_on_or_before(read_series(YC, "TIME_PERIOD", "OBS_VALUE"), d0)
    put("q_eur", to_continuous(y_q / 100, "continuous"), "continu, par an", d_q, YC.name,
        "y / 100 (déjà continu)", "TITLE_COMPL BCE : « continuous compounding »")
    put("q_eur_ln1py_variante", to_continuous(y_q / 100, "annual"), "continu, par an", d_q, YC.name,
        "ln(1 + y)", "comparaison : conversion ln(1 + y), non retenue")
    put("y_eur_1y_pct", y_q, "% publié", d_q, YC.name, "tel que publié", "")

    d_e, y_e = last_on_or_before(read_series(ESTR, "TIME_PERIOD", "OBS_VALUE"), d0)
    put("estr_pct", y_e, "% publié", d_e, ESTR.name, "tel que publié",
        "comparaison seulement (taux au jour le jour)")
    d_t, y_t = last_on_or_before(read_series(AV_3M, "timestamp", "value"), d0)
    put("ust_3m_pct", y_t, "% publié", d_t, AV_3M.name, "tel que publié",
        "comparaison seulement (Alpha Vantage)")

    r, q = rows["r_usd"]["value"], rows["q_eur"]["value"]
    put("forward_1y", S0 * math.exp(r - q), "USD pour 1 EUR", d0, "calcul",
        "S0·e^{(r − q)·1}", "strike « forward 1 an »")

    cc = cross_check(ecb, av, n=WINDOW)
    for k in ("n_common", "mean_diff", "mean_abs_diff", "max_abs_diff"):
        day = cc["max_abs_diff_date"] if k == "max_abs_diff" else cc["last"]
        put(f"xcheck_{k}", cc[k], "USD pour 1 EUR" if k != "n_common" else "jours", day,
            f"{ECB_FX.name} − {AV_FX.name}", "fixing BCE − clôture AV, même date",
            "252 derniers jours communs", first=cc["first"])
    return rows


def main() -> None:
    rows = calibrate()
    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for row in rows.values():
            w.writerow({k: (repr(float(v)) if isinstance(v, float) else v) for k, v in row.items()})
    for name, row in rows.items():
        print(f"{name:<22} {row['value']!s:<24} {row['date']}  {row['convention']}")


if __name__ == "__main__":
    main()
