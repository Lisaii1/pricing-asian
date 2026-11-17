# Option asiatique et réduction de variance — projet Pricing Monte-Carlo

Projet de groupe, cours « Pricing Monte-Carlo » (A. W. Sanoussi Mani), ECE Paris, ING4 Finance,
énoncé 2. Le code Python évalue par Monte-Carlo le call et le put asiatiques (moyenne arithmétique)
sous Black-Scholes avec dividende continu, les compare aux options européennes, réduit la variance
par une variable de contrôle (option sur moyenne géométrique) et mesure le gain de temps et de
précision ; il l'applique ensuite au change EUR/USD. Les nombres aléatoires viennent uniquement des
méthodes du cours (générateur congruentiel linéaire et transformations).

## Par où commencer

Dans cet ordre :

1. **Dossier du groupe (PDF)** : `docs/pdf/Dossier_Groupe_Pricing_Asiatique.pdf` — tout ce qu'on a
   fait, étape par étape, avec les figures et un glossaire.
2. **Oral (PDF)** : `docs/pdf/Oral_Pricing_Asiatique.pdf` — une fiche par partie de la soutenance,
   les questions probables, les 10 chiffres à connaître.
3. **Conformité (PDF)** : `docs/pdf/Conformite_Pricing_Asiatique.pdf` — le sujet exigence par
   exigence, ce qu'on a fait en plus, ce qui reste à faire.
4. **Rapport (PDF)** : `rapport/Rapport_Pricing_Asiatique.pdf` — le rapport rendu (page de garde et
   2 pages).
5. **Figures** : `results/figures/rendu/` — les figures et tableaux du rapport (PNG et PDF).
6. **Excel** : `results/Resultats_Pricing_Asiatique.xlsx` — les résultats, onglet « Synthèse » en
   premier.

Les mêmes documents existent en Markdown dans `docs/` (`DOSSIER_GROUPE.md`, `ORAL.md`,
`CONFORMITE.md`). Ils sont produits par `scripts/p6_build.py` à partir de `docs/templates/` : on
corrige le gabarit, jamais le fichier produit.

## Installer et lancer les tests

Sous Windows, avec Python 3.13, depuis la racine du dépôt :

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m pytest -q
```

La dernière ligne doit annoncer des tests « passed » et aucun « failed ». Les tests vérifient au
démarrage que numpy, scipy et pytest ont exactement les versions de `requirements.txt`.

## Régénérer les documents

```
.venv\Scripts\python scripts\p6_build.py               # les .md et le rapport en HTML
.venv\Scripts\python scripts\p6_build.py --pdf-groupe  # et les trois PDF de docs/pdf/
```

Les chiffres de tous les documents sont recopiés par ce script depuis les fichiers `results/*.csv` :
aucun n'est tapé à la main. Les PDF demandent Chrome ou Edge installé.
