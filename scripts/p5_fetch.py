"""Relevés officiels pour l'actif réel EUR/USD.

Sources (seules URL utilisées) :
  - BCE, API SDMX sans clé (documentation : https://data.ecb.europa.eu/help/api/overview ; point
    d'accès des données https://data-api.ecb.europa.eu/service/data/{flux}/{clé}) :
      EXR/D.USD.EUR.SP00.A                fixing de référence BCE EUR/USD (USD pour 1 EUR), journalier
      EST/B.EU000A2X2A25.WT               €STR, taux moyen pondéré (comparaison seulement)
      YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_1Y  courbe AAA zone euro, taux spot 1 an
    format=csvdata, startPeriod borné (voir START) pour limiter la taille.
  - Trésor américain, courbe des taux journalière (home.treasury.gov), fichier CSV de l'année 2026 ;
    colonne « 1 Yr ». Repli si absent : relevé Alpha Vantage 3 mois déjà dans data/raw/.

Chaque appel est journalisé dans data/raw/fetch_log.csv (URL, date et heure locales et UTC, statut
HTTP, sha256, octets) ; la réponse est enregistrée brute (octets reçus, sans réécriture) dans
data/raw/ avant tout usage. Une source qui ne répond pas est notée « absent » : aucune valeur de
remplacement. La clé de chaque série est vérifiée sur la réponse réelle (colonne KEY = clé demandée).
Puis data/raw/MANIFEST.md est régénéré (tous les fichiers de data/raw/, dont les deux relevés Alpha
Vantage, et le journal des appels).

Usage : .venv/Scripts/python.exe scripts/p5_fetch.py            (appels réseau + MANIFEST)
        .venv/Scripts/python.exe scripts/p5_fetch.py --manifest (MANIFEST seul, sans réseau)
"""
from __future__ import annotations

import csv
import hashlib
import io
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
LOG = RAW / "fetch_log.csv"
MANIFEST = RAW / "MANIFEST.md"

ECB = "https://data-api.ecb.europa.eu/service/data"
START = {"EXR": "2024-01-01", "EST": "2025-01-01", "YC": "2025-01-01"}
ECB_SERIES = [
    ("EXR", "D.USD.EUR.SP00.A", "BCE, fixing de référence EUR/USD"),
    ("EST", "B.EU000A2X2A25.WT", "BCE, €STR (taux moyen pondéré)"),
    ("YC", "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_1Y", "BCE, courbe AAA zone euro, spot 1 an"),
]
TREASURY_YEAR = 2026
TREASURY_URL = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
                f"daily-treasury-rates.csv/{TREASURY_YEAR}/all?type=daily_treasury_yield_curve"
                f"&field_tdr_date_value={TREASURY_YEAR}&page&_format=csv")
USER_AGENT = "pricing-asian-fetch/1.0 (Python urllib)"     # générique, aucune donnée personnelle
TIMEOUT = 60
LOG_FIELDS = ["source", "url", "requested_at_local", "requested_at_utc", "status", "http_status",
              "error", "file", "sha256", "bytes", "key_check"]

# Relevés Alpha Vantage (17/11/2026, API FX_DAILY et TREASURY_YIELD) : URL et heure non relevées.
ALPHA_VANTAGE_FILES = {
    "2026-11-17_alphavantage_FX_DAILY_EURUSD_full.csv":
        ("Alpha Vantage, API FX_DAILY, EUR/USD", "timestamp"),
    "2026-11-17_alphavantage_TREASURY_YIELD_3month_daily_sample.csv":
        ("Alpha Vantage, API TREASURY_YIELD, 3 mois", "timestamp"),
}


def _now():
    local = datetime.now().astimezone()
    return local.isoformat(timespec="seconds"), local.astimezone(timezone.utc).isoformat(
        timespec="seconds")


def _get(url: str) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.status, resp.read()


def _log(entry: dict) -> None:
    new = not LOG.exists()
    with LOG.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if new:
            w.writeheader()
        w.writerow(entry)


def _ecb_key_check(data: bytes, flow: str, key: str) -> str:
    """Vérifie sur la réponse réelle que toutes les lignes portent la clé demandée."""
    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
    if not rows:
        return "réponse vide"
    keys = {r.get("KEY", "") for r in rows}
    want = f"{flow}.{key}"
    title = rows[0].get("TITLE", "")
    return (f"KEY = {want} sur {len(rows)} lignes ; TITLE « {title} »" if keys == {want}
            else f"KEY inattendue {sorted(keys)} (demandée {want})")


def fetch_one(source: str, url: str, filename: str, check=None) -> dict:
    local, utc = _now()
    entry = dict(source=source, url=url, requested_at_local=local, requested_at_utc=utc,
                 status="absent", http_status="", error="", file="", sha256="", bytes="",
                 key_check="")
    try:
        status, data = _get(url)
        entry["http_status"] = status
        if status != 200 or not data:
            entry["error"] = f"HTTP {status}, {len(data)} octets"
        else:
            path = RAW / filename
            path.write_bytes(data)                     # brut, avant tout usage
            entry.update(status="ok", file=f"data/raw/{filename}",
                         sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
            if check:
                entry["key_check"] = check(data)
    except urllib.error.HTTPError as e:
        entry.update(http_status=e.code, error=f"HTTPError {e.code} {e.reason}")
    except Exception as e:                             # réseau, délai, DNS… : source absente
        entry["error"] = f"{type(e).__name__}: {e}"
    _log(entry)
    print(f"{source:<45} {entry['status']:<6} {entry['http_status']!s:<4} "
          f"{entry['sha256'][:16]} {entry['error']}", flush=True)
    return entry


def fetch_all(day: str) -> None:
    for flow, key, label in ECB_SERIES:
        url = f"{ECB}/{flow}/{key}?startPeriod={START[flow]}&format=csvdata"
        fetch_one(label, url, f"{day}_ecb_{flow}_{key}.csv",
                  check=lambda d, f=flow, k=key: _ecb_key_check(d, f, k))
    fetch_one("Trésor américain, courbe des taux journalière", TREASURY_URL,
              f"{day}_treasury_daily_yield_curve_{TREASURY_YEAR}.csv")


# --- MANIFEST -------------------------------------------------------------------------------------

def _date_column(path: Path) -> str:
    with path.open(encoding="utf-8-sig", newline="") as f:
        head = next(csv.reader(f))
    for c in ("TIME_PERIOD", "Date", "timestamp"):
        if c in head:
            return c
    raise ValueError(f"{path.name} : aucune colonne de date connue dans {head}")


def _iso(v: str) -> str:
    return datetime.strptime(v, "%m/%d/%Y").date().isoformat() if "/" in v else v


def _describe(path: Path) -> dict:
    data = path.read_bytes()
    col = _date_column(path)
    with path.open(encoding="utf-8-sig", newline="") as f:
        dates = [_iso(r[col]) for r in csv.DictReader(f)]
    return dict(sha256=hashlib.sha256(data).hexdigest(), lines=data.count(b"\n"),
                first=min(dates), last=max(dates), column=col)


def _read_log() -> list[dict]:
    if not LOG.exists():
        return []
    with LOG.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_manifest() -> None:
    log = _read_log()
    by_file = {e["file"]: e for e in log if e["status"] == "ok"}      # dernier appel réussi
    rows = []
    for path in sorted(RAW.glob("*.csv")):
        if path.name == LOG.name:
            continue
        rel = f"data/raw/{path.name}"
        d = _describe(path)
        if path.name in ALPHA_VANTAGE_FILES:
            source, url, when = ALPHA_VANTAGE_FILES[path.name][0], "API Alpha Vantage, URL non relevée", \
                "2026-11-17 (heure non relevée)"
        elif rel in by_file:
            e = by_file[rel]
            source, url, when = e["source"], e["url"], e["requested_at_local"]
            if e["sha256"] != d["sha256"]:
                raise RuntimeError(f"{rel} : sha256 du fichier ≠ sha256 relevé à l'appel")
        else:
            raise RuntimeError(f"{rel} : fichier sans appel journalisé ni relevé Alpha Vantage connu")
        rows.append(f"| `{rel}` | {source} | {url} | {when} | `{d['sha256']}` | {d['lines']} | "
                    f"{d['first']} | {d['last']} | `{d['column']}` | ok |")
    for e in log:
        if e["status"] != "ok" and not any(e["source"] in r for r in rows):
            rows.append(f"| `—` | {e['source']} | {e['url']} | {e['requested_at_local']} | — | 0 | "
                        f"— | — | `—` | absent ({e['error']}) |")
    calls = [f"| {e['requested_at_local']} | {e['requested_at_utc']} | {e['source']} | {e['url']} | "
             f"{e['status']} | {e['http_status']} | {e['bytes']} | "
             f"{('`' + e['sha256'] + '`') if e['sha256'] else '—'} | {e['key_check'] or e['error']} |"
             for e in log]
    text = "\n".join([
        "# data/raw — relevés bruts",
        "",
        "Généré par `scripts/p5_fetch.py` (ne pas éditer à la main). Fichiers enregistrés tels que reçus",
        "(octets bruts, `.gitattributes` : `data/raw/** -text`). Lignes = nombre de caractères de fin de",
        "ligne (\\n) ; première et dernière date = extrêmes de la colonne de date, toutes lignes comprises",
        "(y compris les jours sans valeur).",
        "",
        "| " + " | ".join(["Fichier", "Source", "URL", "Relevé", "sha256", "Lignes", "Première date",
                          "Dernière date", "Colonne de date", "Statut"]) + " |",
        "|" + "---|" * 10,
        *rows,
        "",
        "## Journal des appels réseau (data/raw/fetch_log.csv)",
        "",
        "| Heure locale | UTC | Source | URL | Statut | HTTP | Octets | sha256 | Vérification / erreur |",
        "|---|---|---|---|---|---|---|---|---|",
        *calls,
        "",
    ])
    MANIFEST.write_text(text, encoding="utf-8")
    print(f"MANIFEST : {len(rows)} lignes, {len(calls)} appels journalisés")


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if argv not in ([], ["--manifest"]):
        raise SystemExit("usage : p5_fetch.py [--manifest]")
    if not argv:
        fetch_all(datetime.now().astimezone().date().isoformat())
    write_manifest()


if __name__ == "__main__":
    main()
