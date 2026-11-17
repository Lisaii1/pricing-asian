# data/raw — relevés bruts

Généré par `scripts/p5_fetch.py` (ne pas éditer à la main). Fichiers enregistrés tels que reçus
(octets bruts, `.gitattributes` : `data/raw/** -text`). Lignes = nombre de caractères de fin de
ligne (\n) ; première et dernière date = extrêmes de la colonne de date, toutes lignes comprises
(y compris les jours sans valeur).

| Fichier | Source | URL | Relevé | sha256 | Lignes | Première date | Dernière date | Colonne de date | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `data/raw/2026-11-17_alphavantage_FX_DAILY_EURUSD_full.csv` | Alpha Vantage FX_DAILY EUR/USD (Cowork) | outil Alpha Vantage de Cowork, URL non relevée | 2026-11-17 (Cowork, heure non relevée) | `7165537af57c47390b9a1bdcfc47b0d85e8c4a525176238a33b13195672d3a70` | 5001 | 2007-09-17 | 2026-11-16 | `timestamp` | ok |
| `data/raw/2026-11-17_alphavantage_TREASURY_YIELD_3month_daily_sample.csv` | Alpha Vantage TREASURY_YIELD 3 mois (Cowork) | outil Alpha Vantage de Cowork, URL non relevée | 2026-11-17 (Cowork, heure non relevée) | `27b7e122feb87bd6da06ea34e2a16e1e972fe74f18e8d1425ab8a538d59c3457` | 3795 | 2012-04-30 | 2026-11-13 | `timestamp` | ok |
| `data/raw/2026-11-17_ecb_EST_B.EU000A2X2A25.WT.csv` | BCE, €STR (taux moyen pondéré) | https://data-api.ecb.europa.eu/service/data/EST/B.EU000A2X2A25.WT?startPeriod=2025-01-01&format=csvdata | 2026-11-17T16:29:52+01:00 | `4bf00cdd8bb69c12ec5439d9024a385b7af951affe97ebb2a6e564f2bb0c12a0` | 480 | 2025-01-02 | 2026-11-16 | `TIME_PERIOD` | ok |
| `data/raw/2026-11-17_ecb_EXR_D.USD.EUR.SP00.A.csv` | BCE, fixing de référence EUR/USD | https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?startPeriod=2024-01-01&format=csvdata | 2026-11-17T16:29:51+01:00 | `af1b3b5f0be4b271e994c62bc00090d14a0ff41349592f56a47cca7cc9180844` | 737 | 2024-01-02 | 2026-11-17 | `TIME_PERIOD` | ok |
| `data/raw/2026-11-17_ecb_YC_B.U2.EUR.4F.G_N_A.SV_C_YM.SR_1Y.csv` | BCE, courbe AAA zone euro, spot 1 an | https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_1Y?startPeriod=2025-01-01&format=csvdata | 2026-11-17T16:29:55+01:00 | `e56d0059583d8de0e02809bb741a7927e6063eaeeeb527f581b419833a6b05c3` | 480 | 2025-01-02 | 2026-11-16 | `TIME_PERIOD` | ok |
| `data/raw/2026-11-17_treasury_daily_yield_curve_2026.csv` | Trésor américain, courbe des taux journalière | https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/2026/all?type=daily_treasury_yield_curve&field_tdr_date_value=2026&page&_format=csv | 2026-11-17T16:30:39+01:00 | `e0a34fc89581322490fc56e2e572e15f3e920ca0d6d37dff148c4f3b4a9e6d82` | 219 | 2026-01-02 | 2026-11-16 | `Date` | ok |

## Journal des appels réseau (data/raw/fetch_log.csv)

| Heure locale | UTC | Source | URL | Statut | HTTP | Octets | sha256 | Vérification / erreur |
|---|---|---|---|---|---|---|---|---|
| 2026-11-17T16:29:51+01:00 | 2026-11-17T15:29:51+00:00 | BCE, fixing de référence EUR/USD | https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?startPeriod=2024-01-01&format=csvdata | ok | 200 | 153344 | `af1b3b5f0be4b271e994c62bc00090d14a0ff41349592f56a47cca7cc9180844` | KEY = EXR.D.USD.EUR.SP00.A sur 736 lignes ; TITLE « US dollar/Euro ECB reference exchange rate » |
| 2026-11-17T16:29:52+01:00 | 2026-11-17T15:29:52+00:00 | BCE, €STR (taux moyen pondéré) | https://data-api.ecb.europa.eu/service/data/EST/B.EU000A2X2A25.WT?startPeriod=2025-01-01&format=csvdata | ok | 200 | 148756 | `4bf00cdd8bb69c12ec5439d9024a385b7af951affe97ebb2a6e564f2bb0c12a0` | KEY = EST.B.EU000A2X2A25.WT sur 479 lignes ; TITLE « Euro short-term rate » |
| 2026-11-17T16:29:55+01:00 | 2026-11-17T15:29:55+00:00 | BCE, courbe AAA zone euro, spot 1 an | https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_1Y?startPeriod=2025-01-01&format=csvdata | ok | 200 | 264812 | `e56d0059583d8de0e02809bb741a7927e6063eaeeeb527f581b419833a6b05c3` | KEY = YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_1Y sur 479 lignes ; TITLE « AAA yield curve - 1-year spot rate » |
| 2026-11-17T16:30:39+01:00 | 2026-11-17T15:30:39+00:00 | Trésor américain, courbe des taux journalière | https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/2026/all?type=daily_treasury_yield_curve&field_tdr_date_value=2026&page&_format=csv | ok | 200 | 17849 | `e0a34fc89581322490fc56e2e572e15f3e920ca0d6d37dff148c4f3b4a9e6d82` |  |
