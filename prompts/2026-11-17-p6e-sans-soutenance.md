Projet pricing-asian (C:\dev\pricing-asian), branche main. Petit lot P6e : il n'y a pas de soutenance orale. C'est Loup qui pousse, toi jamais.

D'ABORD : relève HEAD, `git status`, `git rev-parse origin/main` (Loup vient de pousser a6092b9) ; arrête-toi si l'arbre n'est pas propre.

FAIT NOUVEAU (Loup, 17/11, 22:30) : « Il n'y a pas de soutenance orale. Que des rendus à faire ». Les PDF du groupe (dont l'oral) restent
tels quels, « au cas où ».

PROBLÈME : la dernière phrase des sources du rapport rendu (page 2) dit « Six coquilles relevées dans les slides 9, 23, 24 et 76 du cours sont
détaillées à la soutenance. » Il n'y en aura pas : la promesse serait fausse.

SKILLS : superpowers:verification-before-completion. SOUS-AGENTS : aucun. 3 commits au plus, pas de push, pas de réseau, aucune dépendance.

1. Rapport et paquet du professeur. Un commit.
   - Dans le gabarit du rapport, remplace la fin de phrase par un renvoi qui existe dans le rendu : « … sont détaillées dans le LISEZMOI du code ».
   - Ajoute au LISEZMOI du paquet professeur une courte section « Coquilles relevées dans le support de cours » (slide, ce qui est écrit,
     la forme correcte, une ligne chacune), depuis les mêmes sources que la grille ; sans mot de l'outillage.
   - Régénère le PDF (3 pages, vérifiées en image) et le paquet professeur (contrôles (a) à (d) de P6c relancés et rapportés).
2. Paquet équipe. Un commit si quelque chose change : régénère rendu/Dossier_Equipe_Pricing_Asiatique.zip pour qu'il contienne le PDF
   final ; dans le LISEZ-MOI équipe, remplace toute mention d'une soutenance par « (pas de soutenance prévue : l'oral sert à comprendre
   et à défendre le projet si le professeur pose des questions) ». La grille : la ligne « soutenance » de la partie C passe en « sans objet ».
3. Fin. CLAUDE.md : « Prochain : relecture du groupe, envoi du paquet professeur avant le 22/11 ». pytest complet vert (avec .venv),
   git status propre, git log --oneline.

RAPPORT `reports/2026-11-17-p6e.md` : la phrase avant / après, la section ajoutée, résultats des contrôles, empreintes sha256 des deux zips.
Puis tu t'arrêtes. Ce que tu ne fais PAS : aucun autre changement de texte du rapport, aucun calcul, pas de push.
