"""Garde-fou de version : avant tout test, numpy, scipy et pytest doivent avoir exactement les
versions épinglées dans requirements.txt. Sinon pytest s'arrête avec un message clair : des
versions différentes changent des résultats bit à bit (arrondis, générateurs de figures).
"""
from __future__ import annotations

import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pytest

REQUIREMENTS = Path(__file__).resolve().parents[1] / "requirements.txt"
GUARDED = ("numpy", "scipy", "pytest")
HINT = ("créez l'environnement : python -m venv .venv, puis "
        r".venv\Scripts\pip install -r requirements.txt")


def pinned(text: str) -> dict[str, str]:
    """Versions épinglées (« paquet==version ») d'un requirements.txt."""
    return {m.group(1).lower(): m.group(2)
            for m in re.finditer(r"^\s*([A-Za-z0-9_.\-]+)==(\S+)", text, re.M)}


def version_problems(text: str, installed=version) -> list[str]:
    """Écarts entre les versions installées et celles de requirements.txt (liste vide : tout va)."""
    want = pinned(text)
    problems = []
    for package in GUARDED:
        if package not in want:
            problems.append(f"{package} absent de requirements.txt")
            continue
        try:
            have = installed(package)
        except PackageNotFoundError:
            have = "non installé"
        if have != want[package]:
            problems.append(f"{package} {have} au lieu de {want[package]}")
    return problems


def pytest_configure(config):
    problems = version_problems(REQUIREMENTS.read_text(encoding="utf-8"))
    if problems:
        pytest.exit("Versions différentes de requirements.txt (" + " ; ".join(problems) + ") : "
                    + HINT + ".", returncode=4)
