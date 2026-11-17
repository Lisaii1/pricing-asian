"""Pricer Monte-Carlo : option asiatique à moyenne arithmétique et option européenne.

Payoffs (cours PricingMonteCarlo_2026, slides 38-39) :
    asiatique  call max(A − K, 0), put max(K − A, 0),  A = (1/n) Σ_k S(t_k)
    européen   call max(S_T − K, 0), put max(K − S_T, 0)
Prix = moyenne des payoffs actualisés e^{−rT}·payoff (slides 43-44).

Estimateur et intervalle de confiance (slides 48-49, annexe slides 64-65) :
    prix = (1/N) Σ h_i,  s² = 1/(N − 1) Σ (h_i − prix)²,  écart-type de l'estimateur s/√N,
    IC 95 % = [prix − 1,96·s/√N ; prix + 1,96·s/√N]  (IC symétrique, α1 = α2 = 2,5 %).
Moyenne et variance accumulées bloc par bloc (fusion de Chan, Golub et LeVeque 1979, hors
cours : variante par blocs de l'algorithme de Welford) : la mémoire ne dépend pas de N.

Variable de contrôle géométrique (slides 50-51, exercice des slides 76-77) :
    Y = e^{−rT}·payoff(A),  X = e^{−rT}·payoff(G) sur les mêmes trajectoires,
    E[X] = formule fermée (pricer.geometric),
    Ŷ_b = mean(Y) − b·(mean(X) − E[X]),   b optimal = Cov(Y, X)/Var(X)   (slide 50).
Trois modes pour b (paramètre beta) :
    "optimal"  b estimé sur l'échantillon lui-même, à partir des sommes croisées accumulées par
               blocs (convention du slide 50 ; estimer b sur le même échantillon introduit un
               biais d'ordre 1/N, hors cours) ;
    un réel    b imposé (b = 1 : Ŷ = E[X] + mean(Y − X)) ;
    "pilot"    b estimé sur n_pilot trajectoires, puis estimation sur les n_paths trajectoires
               suivantes du même LCG, sans réutiliser le pilote : sans biais (hors cours).
Écart-type de l'estimateur contrôlé : celui des résidus Y − b(X − E[X]), dont la variance
empirique s'écrit avec les sommes accumulées : [syy − 2b·sxy + b²·sxx]/(N − 1).

Variables antithétiques (slide 52 ; polycopié Haqueberge p. 13-14) : chaque trajectoire Z est
jumelée avec −Z (pricer.paths). n_paths est le nombre total de trajectoires, soit M = n_paths/2
paires. Le prix est la moyenne des n_paths payoffs, c'est-à-dire la moyenne des M moyennes de
paires (h(Z) + h(−Z))/2. Les deux trajectoires d'une paire n'étant pas indépendantes,
l'écart-type est celui des moyennes de paires : s_paires/√M.
Combinaison : le contrôle s'applique aux moyennes de paires de Y et de X ; « sans contrôle »
désigne alors l'estimateur antithétique seul, sur le même échantillon.
"""
from __future__ import annotations

import math
import numbers
import time
from dataclasses import asdict, dataclass

import numpy as np

from pricer.black_scholes import OPTIONS
from pricer.geometric import geometric_asian_price
from pricer.paths import DEFAULT_BATCH, NormalStream, gbm_paths, n_obs_from

Z_95 = 1.96
REFERENCE_SEED = 20261117
AVERAGES = ("arithmetic", "geometric")
CONTROLS = (None, "geometric")
BETA_MODES = ("optimal", "pilot")
DEFAULT_PILOT = 10_000


@dataclass(frozen=True)
class MCResult:
    price: float            # estimateur Monte-Carlo du prix
    std_error: float        # écart-type de l'estimateur, s/√N
    ci_low: float           # IC 95 % : prix − 1,96·s/√N
    ci_high: float          # IC 95 % : prix + 1,96·s/√N
    n_paths: int
    seed: int
    rng_method: str
    n_obs: int              # dates simulées (S0 non compté)
    elapsed: float          # temps de calcul, secondes
    option: str             # "call" / "put"
    kind: str               # "asian" / "european"
    include_s0: bool
    n_uniforms: int         # uniformes consommées dans le LCG
    z: float = Z_95
    average: str | None = None   # asiatique : "arithmetic" / "geometric" ; européen : None
    # --- variable de contrôle (None sans contrôle) ---
    control: str | None = None                 # "geometric"
    beta: float | None = None                  # coefficient b utilisé
    beta_mode: str | None = None               # "optimal" / "fixed" / "pilot"
    corr: float | None = None                  # corrélation empirique de (Y, X)
    control_mean: float | None = None          # E[X], formule fermée
    std_error_no_control: float | None = None  # écart-type sans contrôle, même échantillon
    variance_ratio: float | None = None        # variance sans contrôle / variance avec contrôle
    n_pilot: int = 0                           # trajectoires du pilote (en plus de n_paths)
    antithetic: bool = False                   # trajectoires jumelées (Z, −Z)

    def as_dict(self) -> dict:
        return asdict(self)


class _Moments:
    """Moments de Y, et moments joints de (Y, X) si X est fourni, fusionnés bloc par bloc :
    moyennes, sommes des carrés des écarts syy = Σ(Y − Ȳ)², sxx, et somme croisée sxy."""

    def __init__(self):
        self.n = 0
        self.mean = self.mean_x = 0.0
        self.syy = self.sxx = self.sxy = 0.0

    def add(self, y: np.ndarray, x: np.ndarray | None = None) -> None:
        nb = y.size
        if nb == 0:
            return
        n = self.n + nb
        mb = float(y.mean())
        dy = y - mb
        delta = mb - self.mean
        self.syy += float(np.square(dy).sum()) + delta * delta * self.n * nb / n
        self.mean += delta * nb / n
        if x is not None:
            mxb = float(x.mean())
            dx = x - mxb
            delta_x = mxb - self.mean_x
            self.sxx += float(np.square(dx).sum()) + delta_x * delta_x * self.n * nb / n
            self.sxy += float((dy * dx).sum()) + delta * delta_x * self.n * nb / n
            self.mean_x += delta_x * nb / n
        self.n = n

    @property
    def variance(self) -> float:      # s² en 1/(N − 1), slide 49
        return self.syy / (self.n - 1)

    @property
    def beta_optimal(self) -> float:  # b = Cov(Y, X)/Var(X), slide 50 ; 0 si Var(X) = 0
        return self.sxy / self.sxx if self.sxx > 0.0 else 0.0

    @property
    def corr(self) -> float:          # 0 par convention si une variance est nulle
        d = self.syy * self.sxx
        return self.sxy / math.sqrt(d) if d > 0.0 else 0.0

    def residual_variance(self, b: float) -> float:
        """Variance empirique (1/(N − 1)) des résidus Y − b(X − E[X])."""
        return max(self.syy - 2.0 * b * self.sxy + b * b * self.sxx, 0.0) / (self.n - 1)


def _check_count(value, name: str, antithetic: bool = False) -> int:
    """Entier ≥ 2 trajectoires, ou ≥ 2 paires si antithétique (la parité et le type de
    antithetic sont vérifiés par gbm_paths)."""
    if isinstance(value, bool) or not isinstance(value, numbers.Integral):
        raise TypeError(f"{name} doit être un entier, reçu {value!r}")
    minimum = 4 if antithetic else 2      # il faut au moins 2 termes (paires ou trajectoires)
    if value < minimum:
        raise ValueError(f"{name} doit être ≥ {minimum} (variance empirique en 1/(N − 1))")
    return int(value)


def _check_beta(beta, control):
    """→ (mode, valeur) : ("optimal", None), ("pilot", None) ou ("fixed", b)."""
    if isinstance(beta, str):
        if beta not in BETA_MODES:
            raise ValueError(f"beta inconnu {beta!r} ; choix : {BETA_MODES} ou un réel")
        mode, value = beta, None
    elif isinstance(beta, bool) or not isinstance(beta, numbers.Real):
        raise TypeError(f"beta doit être un réel, 'optimal' ou 'pilot', reçu {beta!r}")
    else:
        mode, value = "fixed", float(beta)
        if not math.isfinite(value):
            raise ValueError(f"beta doit être fini, reçu {beta!r}")
    if control is None and mode != "optimal":
        raise ValueError("beta n'a de sens qu'avec control='geometric'")
    return mode, value


def _price(kind, S0, K, sigma, r, T, q, option, obs, n_paths, seed, rng_method, batch_size,
           include_s0, control, average=None, beta="optimal", n_pilot=DEFAULT_PILOT,
           antithetic=False) -> MCResult:
    if option not in OPTIONS:
        raise ValueError(f"option inconnue {option!r} ; choix : {OPTIONS}")
    if kind == "asian" and average not in AVERAGES:
        raise ValueError(f"average inconnue {average!r} ; choix : {AVERAGES}")
    if control not in CONTROLS:
        raise ValueError(f"control inconnu {control!r} ; choix : {CONTROLS}")
    if control is not None and kind != "asian":
        raise NotImplementedError("le contrôle géométrique porte sur la moyenne des fixings : "
                                  "il n'est défini que pour l'option asiatique")
    beta_mode, b = _check_beta(beta, control)
    K = float(K)
    if not (math.isfinite(K) and K > 0.0):
        raise ValueError(f"K doit être > 0, reçu {K!r}")
    n_paths = _check_count(n_paths, "n_paths", antithetic)
    n_pilot = _check_count(n_pilot, "n_pilot", antithetic) if beta_mode == "pilot" else 0

    start = time.perf_counter()
    stream = NormalStream(seed, rng_method)
    n_obs = n_obs_from(obs, T)
    disc = math.exp(-float(r) * float(T))
    control_mean = (geometric_asian_price(S0, K, sigma, r, T, q, option, obs, include_s0)
                    if control else None)

    def payoff(level: np.ndarray) -> np.ndarray:      # e^{−rT}·max(±(niveau − K), 0)
        return disc * (np.maximum(level - K, 0.0) if option == "call"
                       else np.maximum(K - level, 0.0))

    def sample(level: np.ndarray) -> np.ndarray:
        """Payoffs par trajectoire, ou moyennes de paires (h(Z) + h(−Z))/2 si antithétique."""
        h = payoff(level)
        return 0.5 * (h[0::2] + h[1::2]) if antithetic else h

    def accumulate(n: int) -> _Moments:
        """Simule les n trajectoires suivantes du flux et accumule Y (et X si contrôle)."""
        acc = _Moments()
        for S in gbm_paths(S0, sigma, r, T, q, obs=obs, n_paths=n, batch_size=batch_size,
                           include_s0=include_s0, stream=stream, antithetic=antithetic):
            x = None
            if kind == "european":
                y = sample(S[:, -1])
            else:
                if control or average == "geometric":
                    x = sample(np.exp(np.log(S).mean(axis=1)))        # G = (Π S(t_k))^{1/n}
                y = x if average == "geometric" else sample(S.mean(axis=1))   # A = (1/n)Σ S(t_k)
            acc.add(y, x if control else None)
        return acc

    if beta_mode == "pilot":
        b = accumulate(n_pilot).beta_optimal          # le pilote ne sert qu'à b
    acc = accumulate(n_paths)
    se_plain = math.sqrt(acc.variance / acc.n)
    extra = {}
    if control is None:
        price, se = acc.mean, se_plain
    else:
        if beta_mode == "optimal":
            b = acc.beta_optimal
        price = acc.mean - b * (acc.mean_x - control_mean)
        var_res = acc.residual_variance(b)
        se = math.sqrt(var_res / acc.n)
        if var_res > 0.0:
            ratio = acc.variance / var_res
        else:
            ratio = math.inf if acc.variance > 0.0 else 1.0
        extra = dict(control=control, beta=b, beta_mode=beta_mode, corr=acc.corr,
                     control_mean=control_mean, std_error_no_control=se_plain,
                     variance_ratio=ratio, n_pilot=n_pilot)
    elapsed = time.perf_counter() - start
    return MCResult(price=price, std_error=se, ci_low=price - Z_95 * se,
                    ci_high=price + Z_95 * se, n_paths=n_paths, seed=seed,
                    rng_method=rng_method, n_obs=n_obs, elapsed=elapsed, option=option,
                    kind=kind, include_s0=bool(include_s0), n_uniforms=stream.n_uniforms,
                    average=average, antithetic=antithetic, **extra)


def price_asian(S0, K, sigma, r, T, q=0.0, option="call", obs="monthly", n_paths=100_000,
                seed=REFERENCE_SEED, rng_method="inverse", batch_size=DEFAULT_BATCH,
                include_s0=False, control=None, average="arithmetic", beta="optimal",
                n_pilot=DEFAULT_PILOT, antithetic=False) -> MCResult:
    """Call ou put asiatique à moyenne arithmétique par Monte-Carlo.

    Paramètres généraux : S0, K, sigma, r, T, q (dividende continu), option.
    Spécifiques asiatiques : obs = nombre de dates d'observation (entier) ou fréquence
    "daily" / "weekly" / "monthly" / "quarterly" ; include_s0 = S0 compté dans la moyenne ;
    average = "arithmetic" (énoncé) ou "geometric" (payoff sur G simulé, pour valider la
    formule fermée de pricer.geometric).
    Simulation : n_paths, seed, rng_method (méthode de pricer.normals), batch_size.
    Réduction de variance : control = None ou "geometric" (option sur moyenne géométrique
    comme variable de contrôle) ; beta = "optimal" (défaut, slide 50), un réel, ou "pilot"
    (b estimé sur n_pilot trajectoires tirées avant les n_paths de l'estimation) ;
    antithetic = True : trajectoires jumelées (Z, −Z), n_paths = nombre total (pair),
    écart-type sur les moyennes de paires ; avec control, le contrôle porte sur ces moyennes.
    """
    return _price("asian", S0, K, sigma, r, T, q, option, obs, n_paths, seed, rng_method,
                  batch_size, include_s0, control, average, beta, n_pilot, antithetic)


def price_european_mc(S0, K, sigma, r, T, q=0.0, option="call", obs="monthly",
                      n_paths=100_000, seed=REFERENCE_SEED, rng_method="inverse",
                      batch_size=DEFAULT_BATCH, include_s0=False, control=None,
                      antithetic=False) -> MCResult:
    """Call ou put européen par Monte-Carlo, mêmes paramètres que price_asian.

    Payoff sur S_T = dernière date d'observation (t_n = T). Avec les mêmes obs et seed que
    price_asian, les deux prix sont calculés sur les mêmes trajectoires ; avec obs=1, S_T est
    simulé en un pas, exactement comme au slide 43. Le schéma étant exact, la loi de S_T ne
    dépend pas de obs. control : le contrôle géométrique n'est défini que pour l'asiatique.
    antithetic = True : trajectoires jumelées (Z, −Z), comme pour price_asian.
    """
    return _price("european", S0, K, sigma, r, T, q, option, obs, n_paths, seed, rng_method,
                  batch_size, include_s0, control, antithetic=antithetic)
