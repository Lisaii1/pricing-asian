Projet pricing-asian (C:\dev\pricing-asian), branche main. Lot P6b : grille de conformité au sujet. À lancer APRÈS P6, dans une
nouvelle session. C'est Loup qui pousse, toi jamais.

D'ABORD : relève HEAD, `git status`, et vérifie que le commit de fin de P6 est là (sinon arrête-toi et dis-le).

DEMANDE DE LOUP (17/11, 19:10) : « selon ce qu'on a pu faire, regarder le sujet et dire qu'est-ce qu'on a validé et qu'est-ce qu'on a fait
en plus pour tout ce qui est en termes d'explication, surtout, c'est important ».

SOURCES : le sujet `docs/2026-S1_ProjetPricing.pdf` (lis-le en entier : consignes générales ET énoncé 2), CLAUDE.md, reports/ (P1 à P6),
results/, tests/, docs/DOSSIER_GROUPE.md, docs/ORAL.md.

SKILLS : superpowers:verification-before-completion. SOUS-AGENTS : aucun.
RÈGLE DES CHIFFRES : comme en P6, aucun nombre de résultat tapé à la main : gabarit `docs/templates/CONFORMITE.md` rempli par
`scripts/p6_build.py` (étends-le), test inclus. FONCTIONNEMENT : 2 commits, pas de push, pas de réseau, aucune dépendance.

1. `docs/CONFORMITE.md`. Un commit.
   - Partie A « Ce que le sujet demande » : un tableau, une ligne par exigence, citée mot pour mot depuis le PDF (consignes générales :
     langage, interface de la fonction, générateurs du cours, actif réel ou théorique justifié, rapport, date de rendu ; énoncé 2 : Q1 à Q4).
     Colonnes : exigence (citation) | statut (✅ fait / ⚠️ partiel / ❌ non fait, sans complaisance) | où (fichier, fonction, figure) |
     preuve (test qui le vérifie, CSV, page du rapport) | explication en une phrase simple.
   - Partie B « Ce qu'on a fait en plus » : une ligne par ajout (ex. 4 méthodes de normales comparées, LCG vectorisé exact et test Park-Miller,
     formule fermée géométrique discrète, β optimal / pilot et mesure du biais, flux d'aléa disjoints, combinaison antithétique + contrôle,
     efficacité variance × temps et comparaison à temps égal, N nécessaire pour une marge donnée, exercices des slides 77-78 reproduits,
     6 coquilles du cours relevées, Greeks par différences finies avec nombres aléatoires communs, actif réel EUR/USD sur sources officielles
     et conventions de taux vérifiées, figures et classeur Excel reproductibles, tests automatiques) ; colonnes : ajout | pourquoi c'est utile
     (pour le résultat ou pour le professeur) | où | preuve | comment l'expliquer à l'oral en deux phrases.
   - Partie C « Ce qui reste à faire » (ex. noms du groupe, relecture humaine, soutenance) : liste courte, honnête.
2. Liens et fin. Un commit.
   - Lien vers CONFORMITE.md en tête de DOSSIER_GROUPE.md et d'ORAL.md ; dans ORAL.md, une section « Ce qu'on a fait en plus, en 1 minute ».
   - CLAUDE.md : « Prochain : relecture de Loup et du groupe, soutenance ». pytest complet vert, git status propre, git log --oneline.

RAPPORT `reports/2026-11-17-p6b.md` : nombre d'exigences et leur statut ; toute exigence non ✅ avec ta proposition ; « Questions à Loup ».
Puis tu t'arrêtes. Ce que tu ne fais PAS : aucun nouveau calcul, aucune modification du PDF du rapport, pas de push.
