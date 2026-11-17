Projet pricing-asian (C:\dev\pricing-asian), dossier neuf sans git. Lot P1 : socle + génération d'aléa.

CONTEXTE : lis `CLAUDE.md` (règles et contraintes du sujet), rien d'autre dans ce dossier. Sujet : `docs/2026-S1_ProjetPricing.pdf`.
COURS (lecture seule, fait foi) : `C:\Users\loupf\OneDrive\Bureau\ING4\PRICING RISQUE DE MARCHE\`. Lis seulement les slides
générateurs congruentiels, transformée inverse, acceptation-rejet, Box-Muller, inverse de Φ (PricingMonteCarlo_2026, partie S1,
environ slides 5-26 ; dans le polycopié Haqueberge 2018, les pages générateurs et PPND16). Note dans le rapport les numéros de slides lus.
Points connus du cours à respecter : seed x0 = 0 interdite pour un LCG pur ; Hastings a une coquille de dénominateur
(bonne forme : 1 + d1·t + d2·t² + d3·t³) ; Marsaglia polaire : V = 2U − 1 (coquille « −2U − 1 » du slide 21).

SKILLS : superpowers:test-driven-development, superpowers:verification-before-completion.
SOUS-AGENTS : aucun.

FONCTIONNEMENT : un commit par étape (4 au maximum), tu ne POUSSES PAS, aucun remote. Aucun appel réseau sauf `pip install`
des paquets nommés dans un venv local `.venv`, versions épinglées (jamais latest). Aucune valeur inventée. Rien hors de
C:\dev\pricing-asian (le dossier du cours est en lecture seule). Interdit dans `src/` : numpy.random, le module random,
scipy.stats.*.rvs.

1. Socle. Un commit.
   - `git init`, branche `main`, `.gitignore` (.venv, __pycache__, .pytest_cache, reports/).
   - `.venv` + `requirements.txt` épinglé : numpy, scipy, pandas, matplotlib, openpyxl, pytest.
   - Structure : `src/pricer/__init__.py`, `tests/`, `docs/`, `prompts/`, `results/`, `reports/`.
   - Test garde-fou `tests/test_no_forbidden_rng.py` : échoue si `src/` contient numpy.random, `import random`
     ou `.rvs(` (mutation vue rouge citée au rapport).
2. LCG. Un commit. `src/pricer/rng.py`.
   - Classe `LCG(seed, a=16807, m=2**31-1, c=0)` (Park-Miller par défaut, autres paramètres du cours acceptés,
     mixte si c ≠ 0). Seed invalide (0 en pur, hors [0, m−1]) → erreur explicite.
   - `uniforms(n)` → u = x/m ∈ ]0,1[. Version **vectorisée exacte** : on calcule un premier bloc de L valeurs en boucle,
     puis chaque bloc suivant par x_{k+L} = (a^L mod m)·x_k mod m (cas pur), en entiers uint64 sans dépassement
     (le prouver en commentaire : bornes des produits). Cas mixte : formule de saut ad hoc ou boucle, au choix, documenté.
   - Tests : (a) même seed ⇒ même suite ; (b) vectorisé == boucle naïve octet pour octet sur 10^5 valeurs ;
     (c) valeur publiée de Park & Miller (1988) : seed 1, après 10 000 itérations x = 1043618065 ;
     (d) aucune valeur 0 ni 1 ; (e) état sauvegardable (on reprend la suite là où elle s'est arrêtée).
3. Normales. Un commit. `src/pricer/normals.py`, fonction unique
   `normals(n, method, seed, **opts)` avec method ∈ {"inverse", "box_muller", "polar", "acceptance_rejection"} :
   - inverse : inverse de Φ codée à la main, Wichura AS241 (PPND16, double précision) ; Hastings disponible en option
     (`precision="hastings"`) pour la comparaison ;
   - box_muller : formule du cours, deux normales par paire d'uniformes ;
   - polar : Marsaglia-Bray (rejet sur le disque) ;
   - acceptance_rejection : l'exemple de loi normale du cours s'il existe ; sinon proposition exponentielle (demi-normale
     par rejet avec c = √(2e/π), puis signe), marqué « hors cours » ; taux d'acceptation mesuré renvoyé.
   - Toutes les méthodes consomment le même `LCG` (seed explicite) et renvoient aussi le nombre d'uniformes consommées.
   - Tests (SciPy autorisé ici) : AS241 contre `scipy.special.ndtri` sur une grille de u (écart max < 1e-14, sauf justification
     mesurée), Hastings contre ndtri (écart max ≈ 4,5e-4 annoncé par le cours : rapporter la valeur mesurée) ; sur 10^6 tirages
     par méthode : moyenne, variance, skewness, kurtosis, test de Kolmogorov-Smirnov (p-value rapportée, seed fixée),
     autocorrélation lag 1 ; taux d'acceptation polaire mesuré vs π/4 et rejet vs 1/c.
4. Diagnostic et rapport. Un commit.
   - `scripts/p1_diagnostics.py` : pour chaque méthode, temps pour 10^6 normales (médiane de 5 runs), moments, KS,
     taux d'acceptation → `results/p1_rng_diagnostics.csv`.
   - Pas encore de graphique (les graphiques viennent en P5 avec le design) ; mais sauvegarde les données d'un QQ-plot
     (quantiles empiriques vs théoriques, 1 000 points par méthode) dans `results/p1_qq.csv`.
   - `pytest` complet vert, `git status` propre, `git log --oneline`.

RAPPORT `reports/2026-11-17-p1.md` : slides du cours lues et ce qui en est repris ; tableau des résultats du diagnostic
(valeurs lues dans le CSV, arrondies à 10^-4) ; mutations vues rouges ; écarts avec ce prompt ; « Questions à Loup ».
Puis tu t'arrêtes.

Ce que tu ne fais PAS : pas de pricer, pas de trajectoires, pas de graphiques, pas de push ni de remote, pas d'écriture
hors C:\dev\pricing-asian, pas de modification du dossier du cours, aucun générateur de numpy/random/scipy dans src/.
