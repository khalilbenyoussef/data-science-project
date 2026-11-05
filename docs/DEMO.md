# Script de démonstration (10 minutes)

- **Généré le** : 2026-11-05T19:04:13
- **Run audité (Route 1)** : `part_d_audit_report`
- **Snapshot** : `v5`
- **Version du catalogue KPI** : 1.7.0
- **Run Route 2 (spec publiée)** : `route2_20261104T125802503588`
- **Sources lues** : `table kpi_values`, `data/audit/audit_report.json`, `outputs/reports/<run>/*.json`, `outputs/evaluation/*.json`, `config/recommendations.yaml`
- Document généré par `scripts/build_deliverables.py` : ne pas modifier à la main.

Lancement : `./start.ps1` puis ouvrir l'adresse affichée (ajouter `?demo=1` pour passer l'écran d'accueil). Périmètre de la démonstration : **Tunisie, 2024**. Les chiffres ci-dessous sont lus dans les données courantes : régénérer ce script après un nouveau run.

| Minute | Écran | Ce que je clique | Ce que je dis | Chiffres attendus |
|---|---|---|---|---|
| 0:00–1:00 | Accueil → Vue d'ensemble | « Entrer », pays TUN, année 2024 | FinOVA mesure l'inclusion financière de la Tunisie face à quatre pairs, à partir de sources officielles auditées. | Détention d'un compte : 37.8 % ; pairs : DZA 35.3 %, EGY 43.1 %, JOR 46.5 %, MAR 44.4 % |
| 1:00–2:30 | Vue d'ensemble, bas de page | Faire défiler jusqu'à « Pistes de recommandation » | Les pistes viennent de règles fixes appliquées aux valeurs auditées ; chacune cite ses chiffres et son groupe cible ; association, pas causalité. | 9 pistes ; ex. groupe cible « femmes » |
| 2:30–3:00 | Vue d'ensemble | « Télécharger le rapport (PDF) » | Le rapport des constats est construit à la demande, pour le pays et l'année affichés. | page de garde : run, snapshot, catalogue |
| 3:00–4:00 | Inclusion et inégalités | Graphique des groupes | Les écarts entre groupes sont les plus forts signaux. | Écart hommes − femmes : 23.0 pts ; revenu : 27.0 pts |
| 4:00–5:00 | Pourquoi l'exclusion ? | Carte des obstacles | Obstacles déclarés par les adultes sans compte, comparés aux pairs. | Pas de compte : pas assez d'argent : 45.7 % |
| 5:00–7:00 | Sources et qualité → « Agents » | Lire la frise, puis « Relancer la démonstration » | 7 agents en Route 1 puis 2 en Route 2, chacun déterministe ou avec LLM optionnel. Le recalcul reprend les sources officielles du snapshot publié ; sans donnée nouvelle, il s'arrête après le snapshot et les autres agents sont marqués « ignoré ». | score qualité 0.936 ; 90 732 lignes fact ; 1 620 lignes KPI ; Route 1 (hors collecte) 15.9 s |
| 7:00–8:30 | Audit et confiance | Verdict, contrôles, injection de fautes, « Télécharger le rapport (PDF) » | Un auditeur indépendant recalcule chaque valeur ; on a vérifié qu'il détecte des fautes injectées. | pass_with_warnings : 17 réussis, 2 avertissements, 0 échecs ; 1 509 approuvées, 111 avec réserve ; fautes 9/9 ; constats 15/15 acceptés |
| 8:30–9:30 | Ask Finova | Poser « Quel est le taux de détention d'un compte en Tunisie ? » | Chaque nombre de la réponse est contrôlé contre les faits ; sinon réponse déterministe. | 37.8 % ; contrôle en direct 10/10 réponses fondées |
| 9:30–10:00 | Conclusion | — | Recalcul naïf depuis les CSV : mêmes valeurs ; le pipeline ajoute statut, pairs, traçabilité et audit. | 132/132 valeurs identiques |

## Si une question arrive

- *Le LLM invente-t-il des chiffres ?* Non : tout nombre est vérifié contre les faits ; voir EVALUATION.md.
- *Pourquoi « association, pas causalité » ?* Les données Findex sont des enquêtes transversales : elles décrivent des écarts, pas leurs causes.
- *Et sans clé LLM ?* Chaque agent a un repli déterministe ; la démonstration fonctionne hors ligne.
