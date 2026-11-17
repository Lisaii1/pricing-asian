# Projet Pricing ING4 — Option asiatique et réduction de variance

Projet de groupe, cours « Pricing Monte Carlo » (ING4 Finance, ECE Paris, S1 2026, A. W. Sanoussi Mani).
**Rendu : 22 novembre 2026.** Énoncé choisi : **énoncé 2** (sujet complet : `docs/2026-S1_ProjetPricing.pdf`).
Aucun lien avec AlphaDesk, Adesk-Corp ni le cerveau : on n'y lit rien et on n'y écrit rien.

## Énoncé 2 (recopié du sujet)
Actif Black-Scholes : dS_t/S_t = (r − q)dt + σ dW_t.
1. Pricer call et put asiatiques (moyenne arithmétique) par Monte-Carlo.
2. Comparer aux options européennes de mêmes caractéristiques pour plusieurs strikes et maturités.
3. Réduction de variance : variable de contrôle = option sur moyenne géométrique.
4. Analyser le gain de temps / précision.

## Contraintes du sujet (non négociables)
- Code **Python** (choix de Loup, 17/11 : option A, Python + classeur Excel de résultats exporté).
- Interface = une fonction avec paramètres généraux (S0, K, sigma, r, T, q, …) et spécifique asiatique
  (fréquence d'observation du spot).
- Normales générées **uniquement** par les méthodes du cours : générateur congruentiel linéaire (LCG) +
  transformée inverse / Box-Muller / acceptation-rejet. **Interdit dans `src/` : `numpy.random`, `random`,
  `scipy`** (un test le vérifie). SciPy est permis dans `tests/` et `scripts/` (références, diagnostics),
  jamais dans `src/` (Φ y est codée avec `math.erfc`).
- Actif réel et actif théorique : théorique d'abord (validation), réel ensuite (application), choix justifié.
- Rapport Word ou PDF, 2 pages maximum hors page de garde.

## Règles de travail
1. **Aucun chiffre inventé** : tout nombre vient du code exécuté. Un prix Monte-Carlo est toujours rendu
   avec son écart-type, son IC à 95 %, le nombre de tirages N et la seed. Résultats arrondis à 10^-4.
2. **Le cours fait foi** pour notations et formules : `C:\Users\loupf\OneDrive\Bureau\ING4\PRICING RISQUE DE MARCHE\`
   (lecture seule). Ce qui n'est pas dans le cours est marqué « hors cours » dans le code et le rapport.
3. Tests d'abord (pytest), un commit par étape, **jamais de push**, aucun dépôt distant sans Loup.
4. Paquets : versions épinglées dans `requirements.txt`, jamais `latest`.
5. Graphiques : deux thèmes (sombre orange, clair argent), idées cherchées d'abord dans le catalogue Designeer
   (https://designeer.xyz/resources?category=resources-components). Sur la figure : chiffres et source courte ;
   la méthode va dans la légende du rapport.

## Phases
| Phase | Contenu |
|---|---|
| P1 | Socle + aléa : LCG, transformée inverse, Box-Muller, acceptation-rejet, tests statistiques |
| P2 | Trajectoires GBM, pricer asiatique arithmétique, européen MC vs Black-Scholes fermé avec q |
| P3 | Contrôle géométrique (formule fermée discrète, β estimé), antithétiques, combinaison |
| P4 | Analyse : grille K × T, convergence, IC, ratio de variance, efficacité variance × temps |
| P5 | Actif réel calibré, graphiques, classeur Excel |
| P6 | Rapport 2 pages + support de présentation |

## Décisions
- 17/11/2026, Loup : actif réel = **EUR/USD** (q = taux euro, r = taux dollar), « même si possible que ça
  puisse changer » ; utilisé en P5.
- 17/11/2026, Loup : actif théorique d'abord pour valider, réel ensuite.
- 17/11/2026, réponses aux questions P1 (tranchées par Cowork, validées par Loup le 17/11/2026) :
  - Q1 Hastings : t = √(−2 ln p) est la forme d'Abramowitz-Stegun 26.2.23 ; on la garde. Si le slide dit
    autre chose, c'est une coquille listée avec les autres (slide 9 « c = 0 », slide 23 Marsaglia,
    dénominateur de Hastings).
  - Q2 SciPy permis dans `tests/` et `scripts/`, jamais dans `src/`.
  - Q3 dépendances transitives figées par `pip freeze` : conforme (« jamais latest » = toujours épinglé).
  - Q4 rejet : version lisible conservée ; coût (3,95 uniformes par normale) cité tel quel au rapport final.
  - Q5 méthode par défaut du pricer : transformée inverse AS241 (méthode phare du cours, 1 uniforme par
    normale, monotone en U : l'antithétique U ↔ 1 − U du cours est exact). Les autres méthodes restent un
    paramètre ; leur coût sur le prix est mesuré en P4.
  - Q6 seed de référence du projet : **20261117**.
- 17/11/2026, réponses aux questions P2 (tranchées par Cowork) :
  - Q2 nombre d'observations n_obs = f·T : arrondi classique (demi vers le haut), minimum 1, erreur
    seulement si T ≤ 0.
  - Q3 en P4, le temps de l'européen est mesuré en un seul pas ; les prix sont comparés sur les mêmes
    trajectoires.
  - Q4 `reports/` reste ignoré par git (notes de travail) ; tout chiffre du rendu vient de `results/`
    (versionné).
- 17/11/2026, Cowork (P2) : actif théorique = S0 = 100, σ = 0,20, r = 0,03, q = 0,01, observations
  mensuelles (paramètres de `scripts/p2_grid.py`, repris en P3). Sa dérive logarithmique
  r − q − σ²/2 = 0,03 − 0,01 − 0,02 est **nulle** (relevé de P3) : les tests de signe de dérive
  utilisent un autre jeu (r = 0,05).
- 17/11/2026, réponses aux questions P3 (tranchées par Cowork, validées par Loup) :
  - Q1 slide 76 : voir coquilles 5 et 6 ci-dessous ; notre formule σ_G² est équivalente.
  - Q2 la combinaison antithétique + contrôle se présente telle qu'elle est mesurée : gain d'efficacité
    (moitié moins de normales), pas de gain de variance garanti sur le contrôle seul ; P4 compare à N égal
    ET à temps égal.
  - Q3 β « optimal » (slide 50) reste le défaut et sert aux chiffres du rapport ; son biais est mesuré en P4.
  - Q4 n_paths hors pilote, n_pilot = 10 000 : validé.
  - Q5 tableaux des slides 77 et 78 reproduits, avec IC à 99 % là où le slide le demande.
  - Q6 corrélation h(Z)/h(−Z) dans MCResult (`antithetic_corr`).
  - Q7 ligne « actif théorique » gardée (dérive nulle notée ci-dessus).
- 17/11/2026, P4 : IC au niveau `confidence` (défaut 0,95), z = Φ^{-1}((1 + c)/2) calculé par l'inverse
  AS241 du projet (z(0,95) = 1,959964 au lieu du 1,96 arrondi du cours).

## Coquilles du cours relevées (citées au rapport final)
1. Slide 9 : « c = 0 ».
2. Slide 23 (Marsaglia polaire) : « V = −2U − 1 », lire V = 2U − 1.
3. Slide 24 (Hastings) : dénominateur imprimé « d1 + d2 t² + d3 t³ », lire 1 + d1 t + d2 t² + d3 t³.
4. Slide 24 (Hastings) : t lu « −log(min(U, 1 − U)) », lire t = √(−2 ln p) (Abramowitz-Stegun 26.2.23).
5. Slide 76 : « T = (1/n) Σ S(t_j) », lire T̄ = (1/n) Σ t_j.
6. Slide 76 : σ̄² = σ²/(n²T̄)·Σ(2i − 1)t_{n+1−j} mélange i et j (lire i partout) ; équivalente à la nôtre
   (Σ_iΣ_j min(t_i, t_j) = Σ_j (2j − 1)t_{n+1−j}), δ = σ²/2 − σ̄²/2 ; le slide est écrit sans q.

## État court
- P1 fait (4 commits). P2 fait (4 commits). P3 fait (4 commits). P4 : prompt
  `prompts/2026-11-17-p4-analyse.md`.
- Prochain : P5.
