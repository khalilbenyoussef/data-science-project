# Script de démonstration (10 minutes)

- **Généré le** : 2026-11-05T22:20:39
- **Run audité (Route 1)** : `user_delete_20261105T221858`
- **Snapshot** : `v9`
- **Version du catalogue KPI** : 1.7.0
- **Run Route 2 (spec publiée)** : `route2_20261105T221924144045`
- **Sources lues** : `table kpi_values`, `data/audit/audit_report.json`, `outputs/reports/<run>/*.json`, `outputs/evaluation/*.json`, `config/recommendations.yaml`
- Document généré par `scripts/build_deliverables.py` : ne pas modifier à la main.

Lancement : `./start.ps1` puis ouvrir l'adresse affichée et se connecter avec un compte FinOVA. Périmètre de la démonstration : **Tunisie, 2024**. Les chiffres ci-dessous sont lus dans les données courantes : régénérer ce script après un nouveau run.

| Minute | Écran | Ce que je clique | Ce que je dis | Chiffres attendus |
|---|---|---|---|---|
| 0:00–1:00 | Accueil → Vue d'ensemble | « Entrer », pays TUN, année 2024 | FinOVA mesure l'inclusion financière de la Tunisie face à quatre pairs, à partir de sources officielles auditées. | Détention d'un compte : 37.8 % ; pairs : DZA 35.3 %, EGY 43.1 %, JOR 46.5 %, MAR 44.4 % |
| 1:00–2:30 | Vue d'ensemble, bas de page | Faire défiler jusqu'à « Pistes de recommandation » | Les pistes viennent de règles fixes appliquées aux valeurs auditées ; chacune cite ses chiffres et son groupe cible ; association, pas causalité. | 9 pistes ; ex. groupe cible « femmes » |
| 2:30–3:00 | Vue d'ensemble | « Télécharger le rapport (PDF) » | Le rapport des constats est construit à la demande, pour le pays et l'année affichés. | page de garde : run, snapshot, catalogue |
| 3:00–4:00 | Inclusion et inégalités | Graphique des groupes | Les écarts entre groupes sont les plus forts signaux. | Écart hommes − femmes : 23.0 pts ; revenu : 27.0 pts |
| 4:00–5:00 | Pourquoi l'exclusion ? | Carte des obstacles | Obstacles déclarés par les adultes sans compte, comparés aux pairs. | Pas de compte : pas assez d'argent : 45.7 % |
| 5:00–7:00 | Sources et qualité → « Agents » | Lire la frise, puis « Relancer la démonstration » | 7 agents en Route 1 puis 2 en Route 2, chacun déterministe ou avec LLM optionnel. Le recalcul reprend les sources officielles du snapshot publié ; sans donnée nouvelle, il s'arrête après le snapshot et les autres agents sont marqués « ignoré ». | score qualité 0.936 ; 90 732 lignes fact ; 1 620 lignes KPI ; Route 1 (hors collecte) 19.5 s |
| 7:00–8:30 | Audit et confiance | Verdict, contrôles, injection de fautes, « Télécharger le rapport (PDF) » | Un auditeur indépendant recalcule chaque valeur ; on a vérifié qu'il détecte des fautes injectées. | pass_with_warnings : 17 réussis, 2 avertissements, 0 échecs ; 1 509 approuvées, 111 avec réserve ; fautes 9/9 ; constats 15/15 acceptés |
| 8:30–9:30 | Ask Finova | Poser « Quel est le taux de détention d'un compte en Tunisie ? » | Chaque nombre de la réponse est contrôlé contre les faits ; sinon réponse déterministe. | 37.8 % ; contrôle en direct 10/10 réponses fondées |
| 9:30–10:00 | Conclusion | — | Recalcul naïf depuis les CSV : mêmes valeurs ; le pipeline ajoute statut, pairs, traçabilité et audit. | 132/132 valeurs identiques |

## Mode banquier (2 minutes, facultatif)

Fichier : `docs/examples/banque_fictive_exemple.csv` (**données fictives**, « exemple fictif » dans chaque libellé). Les valeurs utilisateur ne sont pas reprises ici : ce document ne contient que des données officielles.

| Étape | Ce que je clique | Ce que je dis |
|---|---|---|
| 1 | Mes données → « Ajouter un fichier », déposer l'exemple, « Continuer » | Structure détectée ; les chiffres officiels ne seront pas modifiés. |
| 2 | Étape « Indicateurs » : unités « par 100 000 adultes » et « % » ; distributeurs → `atm_density`, agences → `branch_density` ; cocher « Mon indicateur mesure la même chose » | Seuls les KPI de même unité sont proposés ; même unité n'est pas même définition : je la déclare, avec la définition officielle sous les yeux. |
| 3 | « Ajouter et recalculer » | Recalcul hors ligne : sources officielles reprises du snapshot. |
| 4 | Vue d'ensemble (Tunisie, 2024) → « Vos indicateurs face aux données officielles » | Chaque valeur porte « Données utilisateur · non vérifiée par BIFlow » ; les agences s'arrêtent en 2023 : « années différentes : comparaison indicative », et aucune piste. |
| 5 | « Pistes de recommandation » → « À partir de vos données » | Même règle fixe, seulement à année identique : ici les distributeurs. |
| 6 | Ask Finova : « Quel est le taux de clients utilisant la banque mobile de ma banque ? » | Réponse « D'après vos données », en mode simple : rien n'est envoyé au LLM tant que `llm.ask.allow_user_data_to_llm` est désactivé. |
| 7 | Cocher « Inclure l'annexe : vos données », « Télécharger le rapport (PDF) » | L'annexe est une section séparée, chaque valeur étiquetée. |
| 8 | Mes données → « Supprimer » | Les lignes quittent l'entrepôt au recalcul. |

## Limites (à dire si on demande)

- Connexion : comptes FinOVA sur invitation (rôles administrateur et utilisateur) ; chaque page et chaque route de données exige une session ouverte. Les sources de « Mes données » sont communes à tous les comptes.
- Niveau pays uniquement : pas encore de gouvernorat, d'agence ni de client.
- Données locales, sauf si `llm.ask.allow_user_data_to_llm` est activé : Ask Finova envoie alors les valeurs lues au fournisseur LLM configuré.
- Définition déclarée par l'utilisateur : comparaison indicative, pas vérifiée par BIFlow.

## Si une question arrive

- *Le LLM invente-t-il des chiffres ?* Non : tout nombre est vérifié contre les faits ; voir EVALUATION.md.
- *Pourquoi « association, pas causalité » ?* Les données Findex sont des enquêtes transversales : elles décrivent des écarts, pas leurs causes.
- *Et sans clé LLM ?* Chaque agent a un repli déterministe ; la démonstration fonctionne hors ligne.
