"""Garde-fou de version de tests/conftest.py : arrêt de pytest, avec un message en français, si
numpy, scipy ou pytest n'ont pas les versions de requirements.txt."""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("garde_fou", ROOT / "tests" / "conftest.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

REQ = (ROOT / "requirements.txt").read_text(encoding="utf-8")


def test_installed_versions_are_the_pinned_ones():
    assert guard.version_problems(REQ) == []


def test_each_guarded_package_is_pinned():
    assert set(guard.GUARDED) <= set(guard.pinned(REQ))


def test_a_changed_pin_is_reported():
    want = guard.pinned(REQ)["numpy"]
    mutated = REQ.replace(f"numpy=={want}", "numpy==0.0.1")
    assert any(p.startswith("numpy ") and "0.0.1" in p for p in guard.version_problems(mutated))


def test_a_missing_package_is_reported():
    def installed(name):
        raise guard.PackageNotFoundError(name)
    problems = guard.version_problems(REQ, installed)
    assert len(problems) == len(guard.GUARDED) and all("non installé" in p for p in problems)


def test_pytest_stops_with_a_clear_message_when_a_pin_changes(tmp_path):
    """Mutation de bout en bout : copie du garde-fou, requirements.txt dont la version attendue de
    numpy est changée, un test trivial ; pytest doit s'arrêter avant de le lancer."""
    (tmp_path / "tests").mkdir()
    shutil.copy(ROOT / "tests" / "conftest.py", tmp_path / "tests" / "conftest.py")
    want = guard.pinned(REQ)["numpy"]
    (tmp_path / "requirements.txt").write_text(REQ.replace(f"numpy=={want}", "numpy==0.0.1"),
                                               encoding="utf-8")
    (tmp_path / "tests" / "test_rien.py").write_text("def test_rien():\n    assert True\n",
                                                     encoding="utf-8")
    done = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                           "tests"], cwd=tmp_path, capture_output=True, timeout=120,
                          env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    out = (done.stdout + done.stderr).decode("utf-8", errors="replace")
    assert done.returncode == 4, out
    assert "numpy" in out and "0.0.1" in out
    assert "créez l'environnement : python -m venv .venv" in out
    assert "pip install -r requirements.txt" in out
    assert "1 passed" not in out
