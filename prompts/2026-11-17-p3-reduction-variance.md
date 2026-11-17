Projet pricing-asian (C:\dev\pricing-asian), branche main, HEAD 573eeaf (8 commits). Un remote `origin`
(https://github.com/Lisaii1/pricing-asian, privé) peut exister : c'est Loup qui pousse, toi jamais. Lot P3 : réduction de variance.

CONTEXTE : CLAUDE.md chargé. Rapport P2 vérifié par Cowork sur le dépôt (4 commits, CSV : 40 lignes, |européen MC − BS| ≤ 1,2572
écart-type, BS K=100 T=1 call 8,8273 recalculé indépendamment). Lectures ciblées : `src/pricer/asian.py`, `src/pricer/paths.py`,
`src/pricer/black_scholes.py` ; dans le cours (`...\PRICING RISQUE DE MARCHE\PricingMonteCarlo_2026.pdf`, lecture seule) les slides
variables de contrôle, variables antithétiques, payoff asiatique / approximation géométrique ; polycopié Haqueberge 2018 : partie
antithétiques. Note les numéros lus. Si le cours fixe une convention (β = 1, β estimé, forme de l'antithétique), tu la suis et
tu la cites ; ce qui va au-delà est marqué « hors cours ».

SKILLS : superpowers:test-driven-development, superpowers:verification-before-completion.
SOUS-AGENTS : aucun.

FONCTIONNEMENT : un commit par étape (4), tu ne POUSSES PAS, aucun appel réseau, aucune dépendance, aucune valeur inventée,
interdits de src/ inchangés.

0. Décisions et arrondi. Un commit.
   - CLAUDE.md « Décisions » : Q1-Q6 de P1 validées par Loup le 17/11 (il lance ce prompt après les avoir relues) ; retire la mention
     « à valider par Loup » ; réponses P2, tranchées par Cowork :
     Q2 arrondi classique (demi vers le haut) pour n_obs = f·T, minimum 1, erreur seulement si T ≤ 0 ;
     Q3 en P4, temps de l'européen mesuré en un seul pas, prix comparés sur les mêmes trajectoires ; Q4 reports/ reste ignoré
     (notes de travail) ; tout chiffre du rendu vient de results/ (versionné). « Prochain : P4 ».
   - `paths.py` : arrondi demi vers le haut, tests ajoutés (T = 0,125 trimestriel → 1, mensuel → 2 ; cas 0,5 → 1).
1. Asiatique géométrique, formule fermée. Un commit. `src/pricer/geometric.py`.
   - G = (Π_{k} S_{t_k})^{1/n} est log-normale. Pour des dates quelconques t_1..t_n (S0 inclus si include_s0, avec t = 0) :
     μ_G = ln S0 + (r − q − σ²/2)·t̄, t̄ = (1/n)Σ t_k ; σ_G² = (σ²/n²)·Σ_i Σ_j min(t_i, t_j).
     Call = e^{−rT}·[e^{μ_G + σ_G²/2}·N(d1) − K·N(d2)], put = e^{−rT}·[K·N(−d2) − e^{μ_G + σ_G²/2}·N(−d1)],
     d2 = (μ_G − ln K)/σ_G, d1 = d2 + σ_G.
   - Cas t_k = kT/n : t̄ = T(n+1)/(2n), σ_G² = σ²·T(n+1)(2n+1)/(6n²) ; coder la forme générale ET tester qu'elle redonne celle-ci.
   - Tests : n = 1 ⇒ égale bs_price (call et put, q > 0) ; n → ∞ ⇒ σ_G² → σ²T/3 (Kemna-Vorst continu, hors cours si absent) ;
     géométrique MC (payoff sur G simulé, sans contrôle) à ±3 écarts-types de la formule, 3 jeux de paramètres ; inégalité
     arithmétique-géométrique trajectoire par trajectoire (A ≥ G) ⇒ call arithmétique MC ≥ call géométrique MC sur les mêmes
     trajectoires, put inversé ; σ → 1e−8.
2. Variable de contrôle géométrique. Un commit. `price_asian(..., control="geometric", beta="optimal")`.
   - Y = e^{−rT}·payoff(A), X = e^{−rT}·payoff(G) sur les mêmes trajectoires, E[X] = formule fermée.
     Estimateur : Ŷ_β = mean(Y) − β·(mean(X) − E[X]) ; β* = Cov(Y, X)/Var(X).
   - Trois modes de β : "optimal" (estimé sur l'échantillon, par blocs, sommes croisées accumulées : défaut si le cours ne dit
     pas autre chose), un réel (ex. 1.0), "pilot" (β estimé sur un pilote de n_pilot trajectoires, puis estimation sur la suite
     du même LCG, sans réutiliser le pilote : sans biais). Écart-type : sur les résidus Y − β(X − E[X]).
   - MCResult enrichi : beta, corr(Y, X), écart-type sans contrôle (même échantillon), ratio de variance.
   - Tests : avec Y := X (payoff géométrique comme cible) et β = 1, prix = formule fermée exactement et écart-type 0 ;
     prix contrôlé à ±3 écarts-types (combinés) du prix sans contrôle à N = 10^6 ; écart-type contrôlé < sans contrôle ;
     ratio de variance ≈ 1/(1 − ρ²) avec β optimal (tolérance justifiée) ; mode pilot sans réutilisation (test sur le compteur
     d'uniformes) ; reproductibilité au bit près.
3. Antithétiques et combinaison. Un commit. `price_asian(..., antithetic=True)`, aussi pour price_european_mc.
   - Chaque trajectoire Z est jumelée avec −Z (forme du cours si elle diffère, ex. U ↔ 1 − U avec l'inverse : la tester
     équivalente pour method="inverse"). n_paths = nombre total de trajectoires (n_paths/2 paires, erreur si impair) ;
     écart-type calculé sur les moyennes de paires.
   - Combinaison antithétique + contrôle : le contrôle s'applique aux moyennes de paires (Y et X).
   - Tests : européen antithétique à ±3 écarts-types de BS ; asiatique antithétique à ±3 du prix sans réduction ;
     écart-type antithétique < écart-type sans réduction à n_paths égal ; combinaison < chacun des deux.
   - `scripts/p3_vr_atm.py` → `results/p3_vr_atm.csv` : actif théorique de CLAUDE.md, K = 100, T ∈ {0,25 ; 1 ; 2}, call et put,
     N = 200 000, seed 20261117, méthode inverse ; 4 estimateurs (sans, antithétique, contrôle β optimal, les deux), plus le
     contrôle avec β = 1 ; colonnes : prix, écart-type, IC, β, corr, ratio de variance, temps (médiane de 3 runs),
     efficacité = variance × temps et gain d'efficacité vs sans réduction. Pas de graphique.
4. Fin : pytest complet vert, git status propre, git log --oneline.

RAPPORT `reports/2026-11-17-p3.md` : slides lues et convention du cours retenue pour β et l'antithétique ; tableau du CSV (valeurs
lues, arrondies à 10^-4) ; corrélation arithmétique/géométrique mesurée ; mutations vues rouges (au moins : σ_G² avec n au lieu de n²,
t̄ décalé d'un pas, signe de β, contrôle sans actualisation, antithétique compté en paires comme en trajectoires) ; écarts avec ce
prompt ; « Questions à Loup ». Puis tu t'arrêtes.

Ce que tu ne fais PAS : pas de graphique, pas de données réelles, pas d'analyse de convergence complète (P4), pas de push,
rien hors de C:\dev\pricing-asian, aucune modification du cours.
