Projet pricing-asian (C:\dev\pricing-asian), branche main. Lot P6d : le dossier, l'oral et la grille en PDF lisibles et faciles à apprendre, et le paquet pour l'équipe.
(v2 du 17/11, 21:03 : remplace la v1, jamais lancée ; ajoute l'étape 4 « paquet équipe ».)
À lancer APRÈS P6c. C'est Loup qui pousse, toi jamais.

D'ABORD : relève HEAD, `git status`, vérifie que le commit de fin de P6c est là (sinon arrête-toi et dis-le).

DEMANDE DE LOUP (17/11, 20:49) : « le problème de Markdown, c'est que déjà les images […] on peut pas les voir […] c'est difficile à
apprendre. Sur un texte en oral à Markdown, c'est un peu chiant […] comme le rapport PDF, on a aussi texte à l'oral, conformité, aussi en
PDF, ou en Word […] qu'on puisse vraiment le voir et que ça soit visuellement, qu'on puisse l'apprendre ».

SKILLS : superpowers:verification-before-completion ; pdf si disponible. SOUS-AGENTS : aucun.
FONCTIONNEMENT : un commit par étape (5), pas de push, pas de réseau sauf `pip install` d'UN paquet de conversion Markdown → HTML si tu en
as besoin (version épinglée, dans un nouveau `requirements-dev.txt`, jamais dans requirements.txt ni dans le paquet de rendu ; sinon un
petit convertisseur maison). Même chaîne que le rapport : HTML → PDF par Chrome headless, fonds imprimés, Segoe UI + Consolas, style Plasma
de la maquette validée ; les PDF sont régénérés par `scripts/p6_build.py --pdf-groupe` depuis les .md (les .md restent la source, la règle
des chiffres ne change pas). Les images de results/figures/ sont intégrées (version « rendu » de P6c pour l'oral et la grille).
Ces trois PDF sont des documents de travail du groupe : ils ne vont pas dans le paquet de rendu.

1. `docs/pdf/Oral_Pricing_Asiatique.pdf`, fait pour apprendre. Un commit.
   - Une page de garde avec le déroulé : chaque partie, sa durée, qui parle (champ {{orateur_*}} laissé visible « [à attribuer] »).
   - Puis UNE FICHE PAR PARTIE (Q1 pricer, Q2 comparaison, Q3 réduction de variance, Q4 temps et précision, cas EUR/USD, ce qu'on a fait
     en plus) : en haut la figure à montrer, en grand ; à côté le CHIFFRE À RETENIR dans un encadré ; dessous les phrases à dire, en
     police lisible (13-14 pt), découpées en 3 à 5 points courts avec les mots-clés en gras ; en bas « si on vous demande… » (1 à 2
     questions liées à cette partie).
   - Puis les 19 questions probables en FICHES QUESTION / RÉPONSE (deux ou trois par page, question en gras, réponse courte), et une page
     « Les 10 chiffres à connaître par cœur » (tableau : chiffre, ce qu'il veut dire, d'où il vient).
2. `docs/pdf/Conformite_Pricing_Asiatique.pdf`. Un commit.
   - Pages en paysage pour la partie A (tableau lisible, statut en pastille de couleur ✅ ⚠️ ❌) ; partie B en cartes (ajout, utilité, deux
     phrases d'oral) ; partie C en liste à cocher.
3. `docs/pdf/Dossier_Groupe_Pricing_Asiatique.pdf`. Un commit.
   - Sommaire cliquable, chaque étape sur une page ou deux, figures intégrées avec leurs 3 lignes d'explication, glossaire en fin.
4. Paquet pour l'équipe. Un commit. Demande de Loup (21:03) : « le dossier que je dois envoyer à mon équipe […] avec toutes les
   informations. Et si […] ils veulent voir en plus en détail, qu'ils aillent sur le GitHub […] et qu'ils récupèrent tout ».
   - `scripts/p6_package.py --equipe` → `rendu/Dossier_Equipe_Pricing_Asiatique/` puis `.zip` (rendu/ reste ignoré par git) :
     `0_LISEZ-MOI_EQUIPE.pdf` (une page : ce que contient le dossier et dans quel ordre le lire ; ce qu'on rend au prof ; et
     « Pour tout voir en détail : GitHub » avec les étapes exactes : accepter l'invitation reçue par mail, puis
     `git clone https://github.com/Lisaii1/pricing-asian.git`, `cd pricing-asian`, `python -m venv .venv`,
     `.venv\Scripts\pip install -r requirements.txt`, `.venv\Scripts\python -m pytest -q` et ce qu'on doit voir) ;
     `1_Dossier_Groupe.pdf`, `2_Oral.pdf`, `3_Conformite.pdf`, `4_Rapport_rendu.pdf` (le PDF final de P6c), `5_Resultats.xlsx` (version
     professeur de P6c), `figures/` (PNG du mode rendu).
   - Ce paquet est interne au groupe : les mots de l'outillage y sont permis seulement dans le dossier du groupe (comme en P6) ; le
     LISEZ-MOI équipe, l'oral et la grille restent sans.
   - Test : contenu et ordre des fichiers ; le zip s'ouvre ; taille rapportée.
5. Fin. Un commit. Lien vers les trois PDF en tête des .md correspondants ; dans le README du dépôt (créé s'il n'existe pas) une section
   « Par où commencer » avec, dans l'ordre : Dossier PDF, Oral PDF, Conformité PDF, Rapport PDF, figures, Excel, chacun avec son chemin.
   CLAUDE.md : « Prochain : relecture humaine, répartition de l'oral, envoi ». pytest complet vert (avec .venv), git status propre.

CONTRÔLES (test + à l'œil) : rends chaque page des trois PDF en PNG et regarde-les toutes avant de conclure (texte qui déborde, image
coupée, tableau illisible) ; nombre de pages de chaque PDF au rapport ; l'oral et la grille sans mot de l'outillage (même liste qu'en P6c).

RAPPORT `reports/2026-11-17-p6d.md` : chemins et nombre de pages des trois PDF ; 2 captures par PDF ; écarts ; « Questions à Loup ». Puis tu
t'arrêtes. Ce que tu ne fais PAS : pas de nouveau calcul, pas de modification du rapport rendu ni du zip, pas de push.
