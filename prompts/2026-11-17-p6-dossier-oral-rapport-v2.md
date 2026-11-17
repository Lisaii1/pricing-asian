Projet pricing-asian (C:\dev\pricing-asian), branche main, HEAD 01948d2 (28 commits ; origin/main = 5be6b12 avant le push de Loup).
C'est Loup qui pousse, toi jamais. Lot P6 : dossier pour le groupe, texte de l'oral, rapport PDF de 2 pages.
(v2 du prompt du 17/11 : remplace la v1, jamais lancée ; ajoute les noms du groupe et la règle des documents rendus.)

CONTEXTE : CLAUDE.md chargé. Rapport P5b vérifié par Cowork (5 commits ; figures 1 et 4 et tableau 1 ouverts : conformes à la maquette).
Tes rapports P1 à P5b sont dans reports/ (non versionnés) : ce sont tes sources pour raconter ce qui a été fait, avec les prompts dans
prompts/ et l'historique git. Lis-les en entier une fois, c'est le cœur de ce lot.

DEMANDE DE LOUP (17/11, 19:07, mot pour mot) : « un fichier qui expliquerait ce qu'on a fait, les étapes qu'on a pu faire, bien
détaillé, et ensuite ce que ça a donné, parce que comme ça permet à mon groupe de savoir exactement qu'est-ce qu'on a pu faire via juste
un dossier qu'ils ont besoin de lire […] un truc assez simple, c'est clair à comprendre […] Et également comme du texte qu'on pourrait
expliquer après ensuite au professeur ».

RÉPONSES À TES QUESTIONS DE P5b (Cowork ; Loup lance ce prompt = validées), à inscrire dans CLAUDE.md :
Q1 palette Plasma gardée telle quelle (le rendu est un PDF lu à l'écran). Q2 pas d'installation de polices : Segoe UI + Consolas partout,
figures et rapport. Q3 oui : biais du pilot non détecté à 2 000 runs, le −2,51 de P5a présenté comme une fluctuation, avec les deux
chiffres. Q4 oui : gains d'efficacité cités à l'ordre de grandeur (« environ ×1 400 ») avec la dispersion mesurée entre deux mesures.
Q5 pas de grain.

SKILLS : superpowers:verification-before-completion ; doc-coauthoring ou humanizer si disponibles (français clair, sans jargon inutile).
SOUS-AGENTS : aucun.

DOCUMENTS RENDUS AU PROFESSEUR (rapport PDF et tout texte destiné à être lu ou dit devant lui, donc ORAL.md) : décision de Loup
(17/11, 19:19) : aucune mention de notre outillage de travail : ni « Cowork », ni « Claude », ni « prompt », ni « lot P1…P6 », ni
« tranché par… », ni noms de fichiers internes (reports/, prompts/, CLAUDE.md). On écrit à la première personne du pluriel (« nous avons… »).
Les étapes s'appellent par leur contenu (« génération de l'aléa », « pricer », « réduction de variance », « analyse », « cas réel »).
DOSSIER_GROUPE.md reste un document interne au groupe : il peut citer les étapes P1-P6 et qui a tranché. Test : grep de ces mots
interdits sur rapport/*.html, le texte extrait du PDF et docs/ORAL.md (zéro occurrence).

RÈGLE DES CHIFFRES (absolue) : aucun nombre de résultat tapé à la main dans un texte. Les textes sont des gabarits (`docs/templates/*.md`,
`rapport/rapport_template.html`) avec des champs {{nom}} remplis par `scripts/p6_build.py` depuis les CSV de results/ (et CLAUDE.md pour
les décisions). Test : chaque nombre décimal des fichiers produits vient d'un champ (liste des champs et de leur CSV d'origine au rapport).
Arrondis : prix à 10^-4 ; écarts-types sous 10^-4 en notation scientifique à 2 chiffres ; gains à l'ordre de grandeur.

FONCTIONNEMENT : un commit par étape (4), pas de push, aucun appel réseau, aucune dépendance nouvelle. Français clair, phrases courtes,
chaque terme technique expliqué à sa première apparition.

1. Dossier du groupe. Un commit. `docs/DOSSIER_GROUPE.md` (lisible sur GitHub, environ 6 à 10 pages).
   - « En une page » : le sujet (énoncé 2), ce qu'on rend, les 5 résultats qui comptent.
   - « Ce qu'on a fait, étape par étape » : P1 à P5b, une section chacune : objectif en une phrase, ce qui a été construit (fichiers),
     comment on l'a vérifié (tests, cas exacts), résultat chiffré, décisions prises et pourquoi (avec qui a tranché : Loup ou Cowork).
   - « Les 6 coquilles du cours » (slide, ce qui est écrit, la bonne forme, comment on l'a vu).
   - « Les résultats » : chaque figure (image intégrée depuis results/figures/) avec 3 lignes « ce qu'on voit / ce que ça veut dire ».
   - « Limites et choix assumés » (σ historique faute d'implicite gratuite, Black-Scholes pour le change, biais de β, temps machine…).
   - « Relancer le projet » (commandes exactes, durée de chaque script) et « Carte du dépôt » (à quoi sert chaque dossier et fichier).
   - « Glossaire » : LCG, seed, transformée inverse, Box-Muller, acceptation-rejet, mouvement brownien géométrique, option asiatique,
     moyenne géométrique, estimateur Monte-Carlo, IC, variable de contrôle, β, antithétique, efficacité, Garman-Kohlhagen, forward, Greeks.
2. Texte de l'oral. Un commit. `docs/ORAL.md`.
   - Déroulé de 8 à 10 minutes, découpé par question du sujet (Q1 pricer, Q2 comparaison européenne, Q3 réduction de variance, Q4 gain
     temps / précision) puis le cas EUR/USD et ce qu'on a fait en plus ; pour chaque partie : ce qu'on montre (figure), ce qu'on dit
     (phrases prêtes à dire, à la première personne du pluriel), le chiffre à retenir.
   - « Questions probables du professeur » : au moins 12, avec une réponse de 3 à 5 lignes chacune (ex. pourquoi pas numpy.random ;
     pourquoi la moyenne géométrique ; pourquoi β estimé et pas 1 ; pourquoi l'antithétique + contrôle n'améliore pas toujours la variance ;
     pourquoi l'asiatique est moins cher, et surtout hors de la monnaie ; pourquoi le call EUR/USD vaut plus que le put ici (r > q) ;
     comment on choisit N pour une marge donnée ; pourquoi la pente vaut −0,5 ; que vaut le biais de β ; limites de Black-Scholes pour le
     change ; reproductibilité ; coquilles du cours).
3. Rapport PDF. Un commit. `rapport/rapport_template.html` → `rapport/rapport.html` → `rapport/Rapport_Pricing_Asiatique.pdf`.
   - Mise en page de la maquette validée (`docs/maquettes/2026-11-17-maquette-F-nuit-profonde.html`, Plasma) : page de garde + 2 pages A4
     au maximum (contrainte du sujet, vérifiée sur le PDF produit : nombre de pages écrit au rapport).
   - Contenu : Q1 à Q4 et le cas EUR/USD, en français académique, environ 30 lignes de texte ; figures de results/figures/ (PNG 300 dpi) :
     choisis celles qui tiennent (proposition : fig. 1, 2, 3, 4, tableau 1, fig. 6 + tableau 2 ; fig. 5 réservée à l'oral) et dis ton choix.
   - Page de garde : titre, « Projet Pricing Monte-Carlo, énoncé 2 », ECE Paris ING4, A. W. Sanoussi Mani, date ; noms du groupe
     (donnés par Loup le 17/11, à recopier tels quels) : Zoe HUBERT, Arthur LOURENCO, Matthieu DEHNEL, Pierre DUPLESSIS,
     Charlotte PONTCHATEAU, Thomas GALLOIS, Sacha BEAUQUESNES, et Loup (nom de famille : à demander à Loup, champ {{loup}} laissé visible
     « [Loup — nom] » d'ici là). Pas de lien GitHub dans le rapport (le dépôt contient nos notes internes).
   - PDF produit par Chrome ou Edge installés, en mode headless (--print-to-pdf), chemin détecté et écrit au rapport ; fonds imprimés.
   - Sources en bas de la page 2 : cours 2026, polycopié 2018, BCE, Trésor US, Fed FEDS 2006-28, Alpha Vantage (données EUR/USD).
4. Fin. Un commit. CLAUDE.md (réponses Q1-Q5, « Prochain : relecture de Loup et du groupe, soutenance »), pytest complet vert, git status
   propre, git log --oneline.

RAPPORT `reports/2026-11-17-p6.md` : liste des champs {{}} et leur CSV ; nombre de pages du PDF ; figures retenues et écartées ; écarts avec
ce prompt ; « Questions à Loup ». Puis tu t'arrêtes.

Ce que tu ne fais PAS : pas de nouveau calcul de prix, pas de nouvelle figure, pas de push, pas de réseau ; aucune phrase qui invente un
résultat ou une décision absente des rapports, des CSV ou de CLAUDE.md.
