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
- 17/11/2026, réponses aux questions P4 (tranchées par Cowork, validées par Loup en lançant P5a) :
  - Q1 slide 77 : les deux colonnes sont montrées, nommées « Exact (géométrique, formule fermée) » et
    « Référence arithmétique (contrôle, N = 4 000 000) ».
  - Q2 slide 78 : « Variance MC » = variance de l'estimateur (σ̂²/N), comparable d'un N à l'autre ; la
    variance des payoffs reste dans le CSV.
  - Q3 seed 20261117 gardée sur le slide 78, avec la phrase sur la variance 1,0105 des 50 000 premières
    normales (changer de seed serait de l'ajustement).
  - Q4 les temps seront remesurés une fois, machine au repos, en P5b.
  - Q5 flux disjoints : les 500 runs du biais de β sont pris bout à bout dans un flux LCG unique
    (run i à l'état a^(i·M)·x0 mod m, saut exact `pricer.rng.state_after`), la référence après eux ;
    vérifié par `scan_stream` (P5a, étape 0).
- 17/11/2026, Loup (15:21) : maquette retenue `docs/maquettes/2026-11-17-maquette-F-nuit-profonde.html`,
  palette Plasma (« Plasma validé pour moi »).
- 17/11/2026, Loup (questionnaire de Cowork, vers 15:22), actif réel EUR/USD (P5a) :
  - Série de cours : fixing de référence BCE EUR/USD (`EXR/D.USD.EUR.SP00.A`) en série principale,
    clôtures Alpha Vantage en contrôle croisé.
  - Volatilité : historique 1 an (252 derniers fixings BCE, √252) pour le prix central, puis prix pour
    σ de 4 % à 8 %.
  - Cas : exportateur français qui encaisse des USD chaque mois pendant 1 an et couvre son taux moyen :
    call asiatique sur EUR/USD, à la monnaie, 12 observations mensuelles, T = 1.
  - Taux (Garman-Kohlhagen, q joue le dividende) : r = Trésor américain 1 an, r = 2·ln(1 + y/2)
    depuis P5b (Q2 ci-dessous ; ln(1 + y) en P5a) ; q = BCE courbe AAA spot 1 an, publiée en
    composition continue (« continuous compounding », réponse BCE) donc q = y (Q1 ci-dessous).
  - Relevés bruts dans `data/raw/` (octets conservés, `-text`), décrits par `data/raw/MANIFEST.md`.
- 17/11/2026, réponses aux questions P5a (Cowork ; validées par Loup en lançant P5b) :
  - Q1 q = y / 100 (déjà continu) : TITLE_COMPL de la série BCE « … Svensson model - continuous
    compounding … », vérifié par Cowork dans le fichier brut ; l'écart au prompt P5a était justifié.
  - Q2 r en base SEMESTRIELLE, r = 2·ln(1 + y/2) : rendements « bond-equivalent » du Trésor (FAQ du
    Trésor : APY = (1 + i/2)² − 1 ; Fed FEDS 2006-28, éq. (4)), URL lues le 17/11/2026 dans
    `pricer.market.TREASURY_SOURCES` et `results/p5_market.csv` ; ln(1 + y) gardé en comparaison.
  - Q3 biais du pilot : relancé à 2 000 runs à flux disjoints avant de conclure (P5b, étape 1) ;
    rien n'est ajusté.
  - Q4 strike central K = S0 (taux budget = cours du jour pour l'exportateur) ; la ligne K = forward
    reste dans les tableaux.
  - Q5 prix arrondis à 10^-4 ; écarts-types et demi-largeurs d'IC sous 10^-4 en notation
    scientifique à 2 chiffres significatifs (ex. 4,2 × 10⁻⁷), `pricer.plotstyle.fmt_err`.
- 17/11/2026, P5b : figures en Segoe UI (texte) et Consolas (chiffres), polices Windows installées
  (Inter et JetBrains Mono de la maquette absentes) ; `results/figures/` (PNG 300 dpi + PDF) et
  `results/pricing_asian_resultats.xlsx` sont générés par `scripts/p5_figures.py` et
  `scripts/p5_excel.py`, jamais édités à la main.
- 17/11/2026, réponses aux questions P5b (Cowork ; validées par Loup en lançant P6) :
  - Q1 palette Plasma gardée telle quelle (le rendu est un PDF lu à l'écran).
  - Q2 pas d'installation de polices : Segoe UI + Consolas partout, figures et rapport.
  - Q3 biais du pilot non détecté à 2 000 runs ; le −2,51 de P5a (500 runs) est présenté comme une
    fluctuation, avec les deux chiffres.
  - Q4 gains d'efficacité cités à l'ordre de grandeur (« environ ×1 400 »), avec la dispersion
    mesurée entre deux mesures du temps.
  - Q5 pas de grain.
- 17/11/2026, Loup (19:19) : documents rendus au professeur (rapport PDF, `docs/ORAL.md`) : aucune
  mention de notre outillage de travail (noms des assistants, consignes, numéros de lots, « tranché
  par… », `reports/`, `prompts/`, `CLAUDE.md`), première personne du pluriel, étapes nommées par leur
  contenu. `docs/DOSSIER_GROUPE.md` reste interne au groupe et peut les citer. Un test le vérifie
  (liste des mots : `scripts/p6_build.FORBIDDEN`). Pas de lien GitHub dans le rapport.
- 17/11/2026, Loup : noms du groupe pour la page de garde dans `scripts/p6_build.GROUP` ; le nom de
  famille de Loup reste à fournir (`p6_build.LOUP`, affiché « [Loup — nom] » d'ici là).
- 17/11/2026, P6 : règle des chiffres. Dossier, oral et rapport sont des gabarits
  (`docs/templates/*.md`, `rapport/rapport_template.html`) à champs {{nom}} remplis par
  `scripts/p6_build.py` depuis les CSV de `results/` ; aucun décimal tapé (testé) ; les fichiers
  produits ne s'éditent pas à la main. Gain d'efficacité « à l'ordre de grandeur » = moyenne des deux
  mesures du temps, arrondie à 2 chiffres significatifs ; les deux anciennes mesures utiles sont dans
  `results/historique/` (recopiées de git, commits 01dca19 et beb2bb2). Rapport : page de garde +
  2 pages A4, figures 1, 2, 4, 3 de `results/figures/`, tableaux 1 et 2 en HTML depuis les CSV ;
  figures 5 et 6 réservées à l'oral ; PDF produit par Chrome en mode headless.

- 17/11/2026, P6b : `docs/CONFORMITE.md` est un gabarit de `scripts/p6_build.py` comme le dossier et
  l'oral, traité comme un document rendu (liée depuis l'oral) : aucun mot de l'outillage (testé). Les
  citations du sujet sont vérifiées dans le texte du PDF du sujet (pdftotext). Les tests se lancent avec
  `.venv\Scripts\python.exe -m pytest` : l'interpréteur `python` du système (Anaconda, NumPy 1.26)
  fait échouer deux tests bit à bit.

- 17/11/2026, Loup (20:13) : nom pour la page de garde « Loup FLORENTIN » (8e de `p6_build.GROUP`) ;
  paquet de rendu option B (code + PDF + annexes : tests, CSV, figures, classeur professeur).
- 17/11/2026, Loup (questions de P6c, vers 21:15) :
  - Les mots interdits présents dans du code exécutable (libellés de `p5_fetch.py`, `p5_market.py`
    et de son CSV, étiquette « P3 » de la figure 5, 4 noms dans les tests) sont reformulés dans le
    dépôt : 20 changements de libellé ou de nom, valeurs inchangées (AST identique hors ces
    libellés) ; la ligne `q_eur_ln1py_prompt` de `p5_market.csv` s'appelle `q_eur_ln1py_variante`.
  - `code/` du paquet est autonome : il contient aussi `data/raw/` et `results/` aux chemins lus
    par le code (copies de `donnees/` et `resultats/`).
- 17/11/2026, P6c : figures du mode rendu `results/figures/rendu/` (`p5_figures.py --rendu`) pour
  le rapport, l'oral, le classeur professeur et le paquet ; `results/figures/` reste pour le dossier.
  Tests : lancer avec `.venv\Scripts\python.exe -m pytest` ; un autre interpréteur est arrêté par le
  garde-fou de version (`tests/conftest.py`).

## Coquilles du cours relevées (citées au rapport final)
1. Slide 9 : « c = 0 ».
2. Slide 23 (Marsaglia polaire) : « V = −2U − 1 », lire V = 2U − 1.
3. Slide 24 (Hastings) : dénominateur imprimé « d1 + d2 t² + d3 t³ », lire 1 + d1 t + d2 t² + d3 t³.
4. Slide 24 (Hastings) : t lu « −log(min(U, 1 − U)) », lire t = √(−2 ln p) (Abramowitz-Stegun 26.2.23).
5. Slide 76 : « T = (1/n) Σ S(t_j) », lire T̄ = (1/n) Σ t_j.
6. Slide 76 : σ̄² = σ²/(n²T̄)·Σ(2i − 1)t_{n+1−j} mélange i et j (lire i partout) ; équivalente à la nôtre
   (Σ_iΣ_j min(t_i, t_j) = Σ_j (2j − 1)t_{n+1−j}), δ = σ²/2 − σ̄²/2 ; le slide est écrit sans q.

## État court
- P1 fait (4 commits). P2 fait (4 commits). P3 fait (4 commits). P4 fait (6 commits).
  P5a fait (5 commits) : prompt `prompts/2026-11-17-p5a-eurusd.md`.
  P5b fait (5 commits) : prompt `prompts/2026-11-17-p5b-figures-excel.md`.
  P6 fait (4 commits) : prompt `prompts/2026-11-17-p6-dossier-oral-rapport-v2.md` ; dossier
  `docs/DOSSIER_GROUPE.md`, oral `docs/ORAL.md`, rapport `rapport/Rapport_Pricing_Asiatique.pdf`.
  P6b fait (2 commits) : prompt `prompts/2026-11-17-p6b-conformite.md` ; grille de conformité au sujet
  `docs/CONFORMITE.md` (15 exigences : 11 faites, 4 partielles ; 19 ajouts ; 7 points restants),
  liée en tête du dossier et de l'oral ; section d'oral « Ce qu'on a fait en plus, en 1 minute ».
  P6c fait (4 commits) : prompt `prompts/2026-11-17-p6c-rendu-v2.md` ; rapport final (nom complet,
  titre en SVG, justification de l'actif théorique, figures du mode rendu), classeur professeur
  `results/Resultats_Pricing_Asiatique.xlsx`, paquet `rendu/Projet_Pricing_Asiatique.zip` par
  `scripts/p6_package.py`, garde-fou de version `tests/conftest.py` ; grille : 12 faites, 3 partielles.
- Prochain : relecture humaine du paquet, soutenance.
