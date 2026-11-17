"""Garde-fou : aucun générateur aléatoire tiers dans src/.

Contrainte du sujet : les normales sont produites uniquement par les méthodes du cours
(LCG + transformée inverse / Box-Muller / acceptation-rejet). Ce test échoue dès qu'un
fichier de src/ mentionne numpy.random, le module random de la bibliothèque standard
ou une méthode .rvs( de scipy.stats, ni n'importe SciPy (CLAUDE.md : SciPy permis dans tests/ et
scripts/ seulement ; Φ est codée sans SciPy dans src/).
"""
from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"

FORBIDDEN = {
    "numpy.random": re.compile(r"\bnumpy\s*\.\s*random\b|\bnp\s*\.\s*random\b"),
    "from numpy import random": re.compile(r"from\s+numpy\s+import\s+(?:[\w\s,()]*\b)?random\b"),
    "import random": re.compile(r"^\s*import\s+(?:[\w.]+\s*,\s*)*random\b", re.MULTILINE),
    "from random import": re.compile(r"^\s*from\s+random\s+import\b", re.MULTILINE),
    ".rvs(": re.compile(r"\.\s*rvs\s*\("),
    "import scipy": re.compile(r"^\s*(?:import|from)\s+scipy\b", re.MULTILINE),
}


def find_violations(root: Path) -> list[str]:
    violations = []
    for path in sorted(root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for label, pattern in FORBIDDEN.items():
            for m in pattern.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                violations.append(f"{path.relative_to(root.parent)}:{line}: {label}")
    return violations


def test_src_exists_and_has_python_files():
    assert SRC.is_dir()
    assert any(SRC.rglob("*.py")), "src/ ne contient aucun fichier Python"


def test_no_forbidden_rng_in_src():
    violations = find_violations(SRC)
    assert violations == [], "Générateur interdit dans src/ :\n" + "\n".join(violations)


def test_detector_catches_each_forbidden_pattern(tmp_path):
    """Le détecteur lui-même doit voir chaque motif interdit (contrôle du garde-fou)."""
    samples = {
        "a.py": "import numpy as np\nz = np.random.standard_normal(3)\n",
        "b.py": "import numpy.random\n",
        "c.py": "from numpy import random\n",
        "d.py": "import random\n",
        "e.py": "from random import gauss\n",
        "f.py": "from scipy import stats\nx = stats.norm.rvs(size=3)\n",
        "g.py": "from scipy.special import ndtr\n",
        "h.py": "import scipy.stats as st\n",
        "ok.py": "# randomness comes from LCG only\nimport numpy as np\n",
        "ok2.py": "import scipyish_not_scipy\n# from scipy import nothing (commentaire)\n",
    }
    pkg = tmp_path / "src"
    pkg.mkdir()
    for name, body in samples.items():
        (pkg / name).write_text(body, encoding="utf-8")
    flagged = {v.split(":")[0].replace("\\", "/").split("/")[-1] for v in find_violations(pkg)}
    assert flagged == {"a.py", "b.py", "c.py", "d.py", "e.py", "f.py", "g.py", "h.py"}
