"""Calibration EUR/USD (P5a, étape 2) : results/p5_market.csv recalculé depuis les relevés bruts.

S0 = dernier fixing BCE ; σ = historique 252 fixings (BCE et Alpha Vantage) ; r = Trésor 1 an,
ln(1 + y) ; q = BCE AAA spot 1 an, déjà en composition continue (métadonnée TITLE_COMPL de la
réponse BCE : « continuous compounding »), donc q = y ; contrôle croisé BCE / Alpha Vantage.
"""
from __future__ import annotations

import csv
import math
from datetime import date
from pathlib import Path

import pytest

from pricer.market import (cross_check, historical_vol, last_on_or_before, read_series,
                           to_continuous)

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "results" / "p5_market.csv"
ECB_FX = RAW / "2026-11-17_ecb_EXR_D.USD.EUR.SP00.A.csv"
AV_FX = RAW / "2026-11-17_alphavantage_FX_DAILY_EURUSD_full.csv"
UST = RAW / "2026-11-17_treasury_daily_yield_curve_2026.csv"
YC = RAW / "2026-11-17_ecb_YC_B.U2.EUR.4F.G_N_A.SV_C_YM.SR_1Y.csv"


def _csv():
    with OUT.open(encoding="utf-8") as f:
        return {r["name"]: r for r in csv.DictReader(f)}


def test_s0_is_last_ecb_fixing():
    ecb = read_series(ECB_FX, "TIME_PERIOD", "OBS_VALUE")
    row = _csv()["S0"]
    assert float(row["value"]) == ecb[-1][1]
    assert row["date"] == ecb[-1][0].isoformat()


def test_sigma_ecb_and_av_recomputed_from_raw():
    rows = _csv()
    ecb = [v for _, v in read_series(ECB_FX, "TIME_PERIOD", "OBS_VALUE")]
    av = [v for _, v in read_series(AV_FX, "timestamp", "close")]
    assert float(rows["sigma_ecb"]["value"]) == pytest.approx(historical_vol(ecb, 252), rel=1e-14)
    assert float(rows["sigma_av"]["value"]) == pytest.approx(historical_vol(av, 252), rel=1e-14)


def test_r_is_treasury_1y_log_one_plus_y_on_or_before_s0_date():
    rows = _csv()
    d0 = date.fromisoformat(rows["S0"]["date"])
    d, y = last_on_or_before(read_series(UST, "Date", "1 Yr"), d0)
    assert rows["r_usd"]["date"] == d.isoformat()
    assert float(rows["r_usd"]["value"]) == pytest.approx(math.log1p(y / 100), rel=1e-15)
    assert float(rows["r_usd"]["value"]) == pytest.approx(to_continuous(y / 100, "annual"))


def test_q_is_ecb_aaa_1y_spot_already_continuous():
    rows = _csv()
    d0 = date.fromisoformat(rows["S0"]["date"])
    d, y = last_on_or_before(read_series(YC, "TIME_PERIOD", "OBS_VALUE"), d0)
    assert rows["q_eur"]["date"] == d.isoformat()
    assert float(rows["q_eur"]["value"]) == pytest.approx(y / 100, rel=1e-15)
    # variante du prompt (ln(1 + y)), gardée pour comparaison
    assert float(rows["q_eur_ln1py_prompt"]["value"]) == pytest.approx(math.log1p(y / 100))


def test_forward_and_cross_check():
    rows = _csv()
    S0, r, q = (float(rows[k]["value"]) for k in ("S0", "r_usd", "q_eur"))
    assert float(rows["forward_1y"]["value"]) == pytest.approx(S0 * math.exp(r - q), rel=1e-15)
    cc = cross_check(read_series(ECB_FX, "TIME_PERIOD", "OBS_VALUE"),
                     read_series(AV_FX, "timestamp", "close"), n=252)
    assert int(float(rows["xcheck_n_common"]["value"])) == cc["n_common"] == 252
    assert float(rows["xcheck_mean_abs_diff"]["value"]) == pytest.approx(cc["mean_abs_diff"])
    assert float(rows["xcheck_max_abs_diff"]["value"]) == pytest.approx(cc["max_abs_diff"])
    assert rows["xcheck_max_abs_diff"]["date"] == cc["max_abs_diff_date"].isoformat()
