"""Données de marché de l'actif réel EUR/USD (P5a, étape 2) : pricer.market.

Lecture des séries brutes (valeurs manquantes = absentes, jamais 0), conversion des taux en taux
continus, volatilité historique annualisée, contrôle croisé de deux séries de cours.
"""
from __future__ import annotations

import math
from datetime import date

import numpy as np
import pytest

from pricer.market import (cross_check, historical_vol, last_on_or_before, log_returns,
                           read_series, to_continuous)
from pricer.normals import normals


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


# --- lecture -------------------------------------------------------------------------------------

def test_read_series_drops_dot_and_empty_values_never_zero(tmp_path):
    p = _write(tmp_path, "t.csv", "timestamp,value\n2026-11-13,4.32\n2026-11-12,.\n"
                                  "2026-11-11,\n2026-11-10,4.30\n")
    s = read_series(p, "timestamp", "value")
    assert s == [(date(2026, 11, 10), 4.30), (date(2026, 11, 13), 4.32)]   # trié, 2 absents


def test_read_series_us_dates_and_bom(tmp_path):
    p = tmp_path / "u.csv"
    p.write_bytes('﻿Date,"1 Yr"\n11/16/2026,4.62\n01/02/2026,3.47\n'.encode("utf-8"))
    assert read_series(p, "Date", "1 Yr") == [(date(2026, 1, 2), 3.47), (date(2026, 11, 16), 4.62)]


def test_read_series_ecb_csvdata_with_missing_obs(tmp_path):
    p = _write(tmp_path, "e.csv", "KEY,TIME_PERIOD,OBS_VALUE,TITLE\n"
                                  "EXR.D.USD.EUR.SP00.A,2026-11-16,1.1014,x\n"
                                  "EXR.D.USD.EUR.SP00.A,2026-11-17,,x\n")
    assert read_series(p, "TIME_PERIOD", "OBS_VALUE") == [(date(2026, 11, 16), 1.1014)]


def test_read_series_rejects_unknown_text_and_duplicate_dates(tmp_path):
    bad = _write(tmp_path, "b.csv", "timestamp,value\n2026-11-13,abc\n")
    with pytest.raises(ValueError, match="abc"):
        read_series(bad, "timestamp", "value")
    dup = _write(tmp_path, "d.csv", "timestamp,value\n2026-11-13,1\n2026-11-13,2\n")
    with pytest.raises(ValueError, match="double"):
        read_series(dup, "timestamp", "value")


def test_last_on_or_before():
    s = [(date(2026, 11, 10), 1.0), (date(2026, 11, 13), 2.0)]
    assert last_on_or_before(s, date(2026, 11, 12)) == (date(2026, 11, 10), 1.0)
    assert last_on_or_before(s, date(2026, 11, 13)) == (date(2026, 11, 13), 2.0)
    with pytest.raises(ValueError):
        last_on_or_before(s, date(2026, 11, 9))


# --- taux ----------------------------------------------------------------------------------------

def test_to_continuous_annual_is_log_one_plus_y():
    assert to_continuous(0.0462, "annual") == pytest.approx(math.log(1.0462), rel=1e-15)
    # aller-retour : e^{r} = 1 + y
    assert math.exp(to_continuous(0.03, "annual")) == pytest.approx(1.03, rel=1e-15)


def test_to_continuous_continuous_is_identity_and_semiannual():
    assert to_continuous(0.0298, "continuous") == 0.0298
    assert to_continuous(0.04, "semiannual") == pytest.approx(2 * math.log(1.02), rel=1e-15)


def test_to_continuous_orders_conventions_for_positive_rate():
    y = 0.05            # composition plus fréquente ⇒ taux continu équivalent plus grand
    assert to_continuous(y, "annual") < to_continuous(y, "semiannual") < y


def test_to_continuous_rejects_unknown_convention_and_percent_input():
    with pytest.raises(ValueError):
        to_continuous(0.03, "monthly")
    with pytest.raises(ValueError, match="décimal"):
        to_continuous(4.62, "annual")             # 4,62 % doit être passé 0,0462


# --- volatilité ----------------------------------------------------------------------------------

def test_log_returns():
    assert np.allclose(log_returns([1.0, 2.0, 1.0]), [math.log(2), -math.log(2)])


def test_historical_vol_uses_last_window_fixings_ddof1_sqrt252():
    z = normals(400, "inverse", seed=20261117).z
    prices = 1.1 * np.exp(np.cumsum(0.004 * z))
    prices = np.concatenate([[1.1], prices])
    last = prices[-252:]                                       # 252 fixings → 251 rendements
    expected = np.std(np.diff(np.log(last)), ddof=1) * math.sqrt(252)
    assert historical_vol(prices, window=252) == pytest.approx(expected, rel=1e-14)


def test_historical_vol_recovers_known_volatility():
    sigma = 0.0555
    z = normals(200_001, "inverse", seed=20261117).z
    prices = np.exp(np.cumsum(sigma / math.sqrt(252) * z))
    est = historical_vol(prices, window=prices.size)
    assert est == pytest.approx(sigma, rel=0.01)              # erreur relative ≈ 1/√(2N) ≈ 0,16 %


def test_historical_vol_needs_enough_points():
    with pytest.raises(ValueError):
        historical_vol([1.0, 1.1], window=252)


# --- contrôle croisé -----------------------------------------------------------------------------

def test_cross_check_on_common_dates_only():
    a = [(date(2026, 11, d), 1.10 + d / 1000) for d in (10, 11, 12, 13)]
    b = [(date(2026, 11, d), 1.10 + d / 1000 + (0.002 if d == 12 else 0.001)) for d in (9, 11, 12, 13)]
    res = cross_check(a, b, n=2)
    assert res["n_common"] == 2
    assert (res["first"], res["last"]) == (date(2026, 11, 12), date(2026, 11, 13))
    assert res["mean_abs_diff"] == pytest.approx(0.0015, abs=1e-12)
    assert res["max_abs_diff"] == pytest.approx(0.002, abs=1e-12)
    assert res["max_abs_diff_date"] == date(2026, 11, 12)
    assert res["mean_diff"] == pytest.approx(-0.0015, abs=1e-12)          # a − b
