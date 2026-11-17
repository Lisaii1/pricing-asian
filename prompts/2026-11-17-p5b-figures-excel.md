Projet pricing-asian (C:\dev\pricing-asian), branche main, HEAD 5be6b12 (23 commits ; origin/main = 1da23f1 avant le push de Loup).
C'est Loup qui pousse, toi jamais. Lot P5b : corrections de P5a, temps au repos, figures Plasma, classeur Excel.

CONTEXTE : CLAUDE.md chargé. Rapport P5a vérifié par Cowork sur le dépôt (5 commits, 4 sources HTTP 200, p5_market.csv relu).
Lectures ciblées : `src/pricer/market.py`, `scripts/p5_market.py`, `scripts/p5_eurusd.py`, `scripts/p4_sensibilites.py` (partie β),
`docs/maquettes/2026-11-17-maquette-F-nuit-profonde.html` (maquette validée par Loup : « Plasma validé pour moi », 17/11, 15:21 ;
couleurs, mise en page et forme de chaque figure à reprendre).

RÉPONSES À TES 5 QUESTIONS DE P5a (Cowork ; Loup lance ce prompt = validées), à inscrire dans CLAUDE.md :
- Q1 q : on garde y / 100 (déjà continu). Vérifié par Cowork dans le fichier brut : TITLE_COMPL de la série BCE « … Svensson model -
  continuous compounding … ». Ton écart au prompt était justifié.
- Q2 r : base SEMESTRIELLE, r = 2·ln(1 + y/2). Source : FAQ du Trésor américain (les taux de la courbe par sont des rendements
  « bond-equivalent », intérêts semestriels ; APY = (1 + i/2)² − 1) et Fed, FEDS 2006-28, éq. (4) y = 2·ln(1 + y_ce/2).
  URL à citer : https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics/interest-rates-frequently-asked-questions
  et https://www.federalreserve.gov/pubs/feds/2006/200628 (lues le 17/11/2026).
- Q3 biais du pilot : on relance avec plus de runs avant de conclure (étape 1) ; rien n'est ajusté.
- Q4 strike central : K = S0 (taux budget = cours du jour pour l'exportateur) ; la ligne K = forward reste dans les tableaux.
- Q5 écarts-types : prix arrondis à 10^-4 ; écarts-types et demi-largeurs d'IC en notation scientifique à 2 chiffres significatifs
  (ex. 4,2 × 10⁻⁷) quand ils sont sous 10^-4.

SKILLS : superpowers:test-driven-development, superpowers:verification-before-completion, dataviz (si disponible : méthode de couleur
et de forme ; la palette reste celle de la maquette).
SOUS-AGENTS : aucun.
MÉMOIRE : mémoire libre relevée avant chaque script lourd ; sous 3 Go : arrêt et rapport (les commits faits restent).

FONCTIONNEMENT : un commit par étape (5), tu ne POUSSES PAS, aucun appel réseau, aucune dépendance nouvelle (matplotlib et openpyxl sont
déjà là), aucune valeur inventée : chaque nombre d'une figure ou du classeur vient d'un CSV de results/ ou d'un calcul du pricer dans le
script, jamais tapé à la main.

0. Corrections de P5a. Un commit.
   - r = 2·ln(1 + y/2) (y = Trésor 1 an, 4,62 % au 16/11) dans market.py + test ; sources ci-dessus en commentaire et dans p5_market.csv
     (la variante ln(1 + y) reste en ligne de comparaison).
   - Relance p5_market.py puis p5_eurusd.py ; diff des CSV montré (seules les valeurs qui dépendent de r doivent bouger).
1. Biais de β et temps au repos. Un commit.
   - Biais : 2 000 runs à flux disjoints (au lieu de 500), modes optimal et pilot, même N = 1 000 ; référence sur un flux à part.
     Rapporte les deux biais en écarts-types de la moyenne. Si le pilot reste au-delà de 2 écarts-types, ne corrige rien : rapporte,
     avec ton hypothèse, dans « Questions à Loup ».
   - Temps : Loup aura fermé les autres programmes. Relance les seuls scripts qui mesurent des temps (p3_vr_atm.py, et dans P4 :
     temps égal, N nécessaire). Les prix doivent rester identiques au bit près (même seed) : vérifie colonne par colonne, seules les
     colonnes de temps et de gains d'efficacité peuvent changer. Diff au rapport.
2. Style et figures 1 à 3. Un commit. `src/pricer/plotstyle.py` + `scripts/p5_figures.py`.
   - Style Plasma de la maquette : fond #030306, lueurs floues en arrière-plan (taches gaussiennes en imshow, faible opacité), couleurs
     a1 #00ffa3, a2 #7c3aed, a3 #ffd60a, texte #f4f5fb, secondaire #a3a6b8, discret #5c6075 ; aucune boîte grise ; axes en pointillés
     discrets ; polices installées sur Windows (une sans-serif propre et une monospace pour les chiffres ; dis lesquelles).
   - Fig. 1 éventail EUR/USD avec les paramètres calibrés de p5_market.csv (S0, σ BCE, r, q) : 200 trajectoires affichées, couleur selon
     la valeur finale, une trajectoire en blanc avec ses 12 points de moyenne en a3 ; à droite, histogrammes de S_T et de la moyenne A
     calculés sur N = 200 000 trajectoires du pricer (pas sur les 200 affichées).
   - Fig. 2 matrices de disques call ET put depuis results/p4_grid_cv.csv (ratio asiatique / européen, taille = remise).
   - Fig. 3 gain d'efficacité par méthode depuis p3_vr_atm.csv (remesuré étape 1) : point plein call, anneau put, taille selon T.
   - Sorties : results/figures/fig1…fig3 en PNG 300 dpi ET en PDF vectoriel ; dimensions pensées pour la mise en page A4 de la maquette.
3. Figures 4, 5 et tableau. Un commit.
   - Fig. 4 convergence MESURÉE depuis p4_convergence.csv : demi-largeur d'IC 95 % contre N (log-log), les 4 estimateurs, points mesurés
     + droite ajustée (pente écrite), ligne ±0,01.
   - Fig. 5 nuage payoff arithmétique / géométrique (2 000 trajectoires du pricer, T = 1, actif théorique), corrélation calculée écrite.
   - Fig. 6 (nouvelle) cas réel EUR/USD : prix asiatique et européen contre σ de 4 % à 8 % depuis p5_eurusd_sensitivity.csv, point au σ mesuré.
   - Tableau 1 en image (même style) : 5 estimateurs, call et put, T = 1, prix, demi-IC, gain ; et Tableau 2 : cas réel (K = S0 et forward).
   - Test : chaque figure se régénère à l'identique (même seed) ; aucune valeur codée en dur (grep sur les scripts).
4. Classeur Excel et registres. Un commit. `scripts/p5_excel.py` → `results/pricing_asian_resultats.xlsx` (openpyxl).
   - Onglets : « Lisez-moi » (projet, méthode en 10 lignes, sources avec URL et dates, seed), « Paramètres » (théorique et EUR/USD), un onglet
     par CSV de results/ utile au rendu (p2, p3, p4, p5), « Figures » (les PNG insérés).
   - Mise en forme sobre et sombre cohérente avec Plasma (en-têtes, formats numériques : prix 0,0000, écarts-types en scientifique),
     volets figés, largeurs de colonnes ; aucune formule qui recalcule un prix (les valeurs viennent des CSV).
   - CLAUDE.md : réponses Q1-Q5, « Prochain : P6 rapport et soutenance ». pytest complet vert, git status propre, git log --oneline.

RAPPORT `reports/2026-11-17-p5b.md` : diff p5_market / p5_eurusd ; biais de β à 2 000 runs ; temps avant / après ; liste des figures
avec leur source CSV ; polices utilisées ; écarts avec ce prompt ; « Questions à Loup ». Puis tu t'arrêtes.

Ce que tu ne fais PAS : pas de rapport Word/PDF (P6), pas de push, pas de réseau, aucune modification des prix déjà validés hors effet de r.
