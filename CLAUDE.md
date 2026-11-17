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
  `scipy.stats.*.rvs`** (un test le vérifie). SciPy n'est permis que dans `tests/` comme référence.
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

## État court
- Prochain : P1 (prompt `prompts/2026-11-17-p1-socle-alea.md`).
