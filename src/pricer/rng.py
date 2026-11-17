"""Générateur congruentiel linéaire (LCG) — cours PricingMonteCarlo_2026, slides 7-12.

Récurrence du cours :
    pur   (slide 7, éq. 1) : x_{i+1} = a·x_i mod m,        u_{i+1} = x_{i+1} / m
    mixte (slide 9, éq. 2) : x_{i+1} = (a·x_i + c) mod m,  u_{i+1} = x_{i+1} / m

Paramètres par défaut : Park & Miller (1988), a = 16807, m = 2^31 − 1 (cours, figure 2,
slide 12). Les autres couples (m, a) de la figure 2 sont acceptés, ainsi que tout LCG mixte.

Seed : slide 7, « x0 est un entier compris entre 1 et m − 1 ». Pour un LCG pur, x0 = 0
donne la suite constante 0 (réponse à la question du slide 12) : elle est refusée.
Pour un LCG mixte, x0 ∈ [0, m − 1].

Vectorisation exacte (hors cours : technique de saut, « jump-ahead »)
--------------------------------------------------------------------
On calcule d'abord un bloc de L valeurs par la boucle du cours. Ensuite, en itérant L fois
la récurrence :
    x_{k+L} = (A_L·x_k + C_L) mod m,  avec  A_L = a^L mod m,
                                          C_L = c·(1 + a + … + a^{L−1}) mod m
(C_L = 0 pour un LCG pur). Chaque bloc suivant se déduit donc du précédent par une seule
opération vectorielle. Le résultat est identique bit à bit à la boucle naïve (testé).

Preuve d'absence de dépassement en uint64 : on impose m ≤ 2^32. Alors 0 ≤ x_k ≤ m − 1 et
0 ≤ A_L ≤ m − 1, donc A_L·x_k ≤ (m − 1)² ≤ (2^32 − 1)² = 2^64 − 2^33 + 1 < 2^64 : le produit
tient dans un uint64. Après réduction, (A_L·x_k mod m) + C_L ≤ 2(m − 1) ≤ 2^33 − 2 < 2^64.
Pour Park-Miller (m = 2^31 − 1), le produit est même < 2^62.

Conversion en uniformes : u = x / m en float64. x < 2^32 < 2^53 est exact en float64 et la
division IEEE est correctement arrondie, d'où l'égalité bit à bit avec x / m en Python.
Pour un LCG pur, x ∈ [1, m − 1] donc u ∈ [1/m, 1 − 1/m] ⊂ ]0, 1[ ; 1 − 1/m < 1 en float64
puisque 1/m > 2^−53. Pour un LCG mixte, x = 0 est atteint une fois par période et donne u = 0
(formule du cours inchangée) : les fonctions de `pricer.normals` le détectent.
"""
from __future__ import annotations

import numbers

import numpy as np

PARK_MILLER_A = 16807
PARK_MILLER_M = 2**31 - 1
MAX_MODULUS = 2**32
DEFAULT_BLOCK = 4096


def _as_int(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, numbers.Integral):
        raise TypeError(f"{name} doit être un entier, reçu {value!r} ({type(value).__name__})")
    return int(value)


class LCG:
    """Générateur congruentiel linéaire pur (c = 0) ou mixte (c ≠ 0).

    >>> g = LCG(1)              # Park-Miller, seed 1
    >>> u = g.uniforms(5)       # 5 uniformes dans ]0, 1[
    >>> saved = g.get_state()   # état sauvegardable, reprise par LCG.from_state(saved)
    """

    def __init__(self, seed, a: int = PARK_MILLER_A, m: int = PARK_MILLER_M, c: int = 0,
                 block: int = DEFAULT_BLOCK):
        self.a, self.m, self.c = self._check_params(a, m, c)
        self.block = _as_int(block, "block")
        if self.block < 1:
            raise ValueError("block doit être ≥ 1")
        self._x = self._check_seed(seed)
        self.count = 0          # nombre total d'uniformes produites par ce générateur
        self._jump_cache: dict[int, tuple[int, int]] = {}

    # --- validation ---------------------------------------------------------------------

    @staticmethod
    def _check_params(a, m, c) -> tuple[int, int, int]:
        a, m, c = _as_int(a, "a"), _as_int(m, "m"), _as_int(c, "c")
        if not 2 <= m <= MAX_MODULUS:
            raise ValueError(f"m = {m} hors de [2, 2**32] (borne requise contre le dépassement uint64)")
        if not 1 <= a <= m - 1:
            raise ValueError(f"a = {a} hors de [1, m − 1] = [1, {m - 1}]")
        if not 0 <= c <= m - 1:
            raise ValueError(f"c = {c} hors de [0, m − 1] = [0, {m - 1}]")
        return a, m, c

    def _check_seed(self, seed) -> int:
        x = _as_int(seed, "seed")
        if self.c == 0:
            if x == 0:
                raise ValueError("seed x0 = 0 interdite pour un LCG pur : la suite resterait à 0")
            if not 1 <= x <= self.m - 1:
                raise ValueError(f"seed {x} hors de [1, m − 1] = [1, {self.m - 1}] (LCG pur)")
        elif not 0 <= x <= self.m - 1:
            raise ValueError(f"seed {x} hors de [0, m − 1] = [0, {self.m - 1}] (LCG mixte)")
        return x

    # --- état -----------------------------------------------------------------------------

    @property
    def mixed(self) -> bool:
        return self.c != 0

    @property
    def state(self) -> int:
        """Dernier entier x produit (ou la seed si rien n'a encore été tiré)."""
        return self._x

    def get_state(self) -> dict:
        return {"a": self.a, "m": self.m, "c": self.c, "x": self._x}

    def set_state(self, state: dict) -> None:
        a, m, c = self._check_params(state["a"], state["m"], state["c"])
        self.a, self.m, self.c = a, m, c
        self._x = self._check_seed(state["x"])
        self._jump_cache.clear()

    @classmethod
    def from_state(cls, state: dict, block: int = DEFAULT_BLOCK) -> "LCG":
        return cls(state["x"], a=state["a"], m=state["m"], c=state["c"], block=block)

    # --- génération -------------------------------------------------------------------

    def _jump(self, L: int) -> tuple[int, int]:
        """(A_L, C_L) tels que x_{k+L} = (A_L·x_k + C_L) mod m (entiers Python exacts)."""
        if L not in self._jump_cache:
            A = pow(self.a, L, self.m)
            C = 0
            if self.c:
                for _ in range(L):          # C_L = c(1 + a + … + a^{L−1}) mod m
                    C = (C * self.a + self.c) % self.m
            self._jump_cache[L] = (A, C)
        return self._jump_cache[L]

    def integers(self, n: int) -> np.ndarray:
        """Les n prochains états x_{i+1}, …, x_{i+n} (uint64), état avancé de n pas."""
        n = _as_int(n, "n")
        if n < 0:
            raise ValueError("n doit être ≥ 0")
        out = np.empty(n, dtype=np.uint64)
        if n == 0:
            return out

        a, m, c = self.a, self.m, self.c
        L = min(n, self.block)
        x = self._x
        for i in range(L):                  # premier bloc : boucle du cours
            x = (a * x + c) % m
            out[i] = x

        if n > L:
            A, C = self._jump(L)
            A64, C64, m64 = np.uint64(A), np.uint64(C), np.uint64(m)
            for start in range(L, n, L):    # blocs suivants : saut de L pas, vectorisé
                stop = min(start + L, n)
                nxt = (out[start - L:stop - L] * A64) % m64
                if C:
                    nxt = (nxt + C64) % m64
                out[start:stop] = nxt

        self._x = int(out[-1])
        self.count += n
        return out

    def uniforms(self, n: int) -> np.ndarray:
        """n uniformes u = x / m (float64), dans ]0, 1[ pour un LCG pur."""
        return self.integers(n) / float(self.m)

    def __repr__(self) -> str:
        kind = "mixte" if self.mixed else "pur"
        return f"LCG({kind}, a={self.a}, m={self.m}, c={self.c}, x={self._x}, count={self.count})"
