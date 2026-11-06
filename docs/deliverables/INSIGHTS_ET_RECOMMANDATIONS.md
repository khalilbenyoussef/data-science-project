# Constats et pistes de recommandation

- **Généré le** : 2026-11-06T02:45:25
- **Run audité (Route 1)** : `user_delete_20261106T024500`
- **Snapshot** : `v14`
- **Version du catalogue KPI** : 1.8.0
- **Run Route 2 (spec publiée)** : `route2_20261106T024403926588`
- **Sources lues** : `dashboard_app/public/data/finova.json`, `data/audit/audit_report.json (route2_insight_audit)`, `table kpi_values`, `config/recommendations.yaml`
- Document généré par `scripts/build_deliverables.py` : ne pas modifier à la main.

## Constats audités

Constats du run Route 2 `route2_20261106T024403926588` (audit du 2026-11-06T02:44:34) : 15 audités, 15 acceptés, 0 rejetés, 2 non auditables (aucun fait KPI derrière la phrase, par exemple une référence statique).

Un constat est accepté quand chaque nombre de la phrase est une valeur publiée de `kpi_values`, une année ou une différence entre deux valeurs citées du même indicateur, au même arrondi.

| Constat | Texte | Statut | KPI · pays · année cités |
|---|---|---|---|
| `overview:INS-overview-account` | En 2024, 37,8 % des adultes en Tunisie détiennent un compte. (+1,0 pt vs 2021) | accepté | Taux de détention d'un compte · TUN · 2024<br>Taux de détention d'un compte · TUN · 2021 |
| `overview:INS-overview-digital` | Les paiements numériques concernent 23,7 % des adultes en Tunisie en 2024 ; ce n'est pas une mesure de détention de compte. | accepté | Paiement numérique effectué ou reçu · TUN · 2024 |
| `overview:INS-overview-saving` | L'épargne, toutes formes confondues, est estimée à 48,2 % en 2024. | accepté | Épargne (toute forme) · TUN · 2024 |
| `overview:INS-overview-emergency` | 88,4 % des adultes déclarent pouvoir obtenir de l'argent en urgence (2024). | accepté | Fonds d'urgence mobilisables en 30 jours · TUN · 2024 |
| `overview:INS-overview-peers` | Détention d'un compte en 2024 : Tunisie 37,8 %, contre Algérie 35,3 %, Égypte 43,1 %, Jordanie 46,5 %, Maroc 44,4 %. | accepté | Taux de détention d'un compte · TUN · 2024<br>Taux de détention d'un compte · DZA · 2024<br>Taux de détention d'un compte · EGY · 2024<br>Taux de détention d'un compte · JOR · 2024<br>Taux de détention d'un compte · MAR · 2024 |
| `inclusion:INS-inclusion-funnel` | Les questions Findex sont distinctes : 37,8 % détiennent un compte, 23,7 % ont effectué un paiement numérique, 21,6 % épargnent à une institution formelle et 3,5 % y empruntent. | accepté | Taux de détention d'un compte · TUN · 2024<br>Paiement numérique effectué ou reçu · TUN · 2024<br>Épargne auprès d'une institution financière · TUN · 2024<br>Emprunt auprès d'une institution financière · TUN · 2024 |
| `inclusion:INS-inclusion-gap-gender` | Écart femmes-hommes en 2024 : 26,6 % des femmes contre 49,6 % des hommes, soit +23,0 pt. Variation depuis l'année antérieure observée : +6,6 pt. | accepté | Détention d'un compte - femmes · TUN · 2024<br>Détention d'un compte - hommes · TUN · 2024<br>Écart femmes-hommes de détention d'un compte · TUN · 2024<br>Écart femmes-hommes de détention d'un compte · TUN · 2021 |
| `inclusion:INS-inclusion-gap-income` | Écart de revenu en 2024 : 21,7 % des quarante pour cent des ménages les plus pauvres contre 48,6 % des soixante pour cent des ménages les plus riches, soit +27,0 pt. Variation depuis l'année antérieure observée : +18,9 pt. | accepté | Détention d'un compte - 40 % des ménages les plus pauvres · TUN · 2024<br>Détention d'un compte - 60 % des ménages les plus riches · TUN · 2024<br>Écart de revenu de détention d'un compte · TUN · 2024<br>Écart de revenu de détention d'un compte · TUN · 2021 |
| `inclusion:INS-inclusion-gap-education` | Écart d'éducation en 2024 : 28,6 % des adultes de niveau primaire ou moins contre 45,8 % des adultes de niveau secondaire ou plus, soit +17,2 pt. Variation depuis l'année antérieure observée : +3,0 pt. | accepté | Détention d'un compte - niveau primaire ou moins · TUN · 2024<br>Détention d'un compte - niveau secondaire ou plus · TUN · 2024<br>Écart d'éducation de détention d'un compte · TUN · 2024<br>Écart d'éducation de détention d'un compte · TUN · 2021 |
| `inclusion:INS-inclusion-gap-laborforce` | Écart de marché du travail en 2024 : 16,6 % des adultes hors population active contre 62,1 % des adultes de la population active, soit +45,6 pt. Variation depuis l'année antérieure observée : +28,3 pt. | accepté | Détention d'un compte - hors population active · TUN · 2024<br>Détention d'un compte - population active · TUN · 2024<br>Écart d'activité de détention d'un compte · TUN · 2024<br>Écart d'activité de détention d'un compte · TUN · 2021 |
| `inclusion:INS-inclusion-gap-urbanicity` | Écart entre milieux en 2024 : 30,2 % des adultes ruraux contre 46,7 % des adultes urbains, soit +16,6 pt. | accepté | Détention d'un compte - milieu rural · TUN · 2024<br>Détention d'un compte - milieu urbain · TUN · 2024<br>Écart urbain-rural de détention d'un compte · TUN · 2024 |
| `access:INS-access-atm` | Le parc de distributeurs atteint 35,44 pour cent mille adultes en 2024 (+0,65 vs 2023), contre 29,78 pour cent mille adultes en 2017. | accepté | Densité des distributeurs automatiques · TUN · 2024<br>Densité des distributeurs automatiques · TUN · 2023<br>Densité des distributeurs automatiques · TUN · 2017 |
| `access:INS-access-branch` | Le réseau d'agences est de 22,37 pour cent mille adultes en 2024. | accepté | Densité des agences des banques commerciales · TUN · 2024 |
| `access:INS-access-outreach` | Déposants 1 063,3 pour mille adultes en 2018 ; Emprunteurs 253,7 pour mille adultes en 2024. | accepté | Déposants des banques commerciales · TUN · 2018<br>Emprunteurs des banques commerciales · TUN · 2024 |
| `access:INS-access-balance` | Encours de crédits 67,8 % du PIB en 2024 ; Encours de dépôts 71,7 % du PIB en 2024. | accepté | Encours des prêts des banques commerciales · TUN · 2024<br>Encours des dépôts des banques commerciales · TUN · 2024 |
| `poverty:INS-poverty-smig` | Le SMIG mensuel brut est de 448,24 TND/mois en 2025 et le barème publié prévoit 517,57 TND/mois en 2028 ; les revalorisations restent à confirmer au JORT. | non auditable | — |
| `poverty:INS-poverty-rate` | Le taux de pauvreté national était de 16,6 % en 2021 (INS) : c'est un contexte socio-économique, pas une mesure d'exclusion financière. | non auditable | — |

## Pistes de recommandation

Périmètre : **Tunisie (TUN), 2024**. Règles déterministes de `config/recommendations.yaml` (version 1), appliquées aux seules lignes `kpi_values` au statut `approved`, `approved_with_review_note`. 17 comparaisons évaluées, 9 pistes retenues, 0 écartées par l'audit des nombres.

Chaque piste est une **piste à explorer**, pas une conclusion : elle décrit une association observée dans les données, jamais une cause.

### Règles et seuils

| Règle | Condition | Indicateurs |
|---|---|---|
| `subgroup_gap` | écart entre sous-groupes ≥ 10 pts | `gender_gap`, `income_gap`, `education_gap`, `laborforce_gap`, `age_gap`, `urban_gap` |
| `barrier_above_peers` | pays − moyenne des pairs ≥ 5 pts | `barrier_too_far`, `barrier_too_expensive`, `barrier_no_documents`, `barrier_insufficient_funds`, `barrier_family_has_account`, `barrier_no_trust` |
| `usage_below_peers` | moyenne des pairs − pays ≥ 5 pts | `account_ownership`, `digital_payment_rate`, `formal_saving_rate` |
| `network_below_peers` | densité inférieure d'au moins 10 % à la moyenne des pairs | `branch_density`, `atm_density` |

La règle `user_vs_official` (vos données de « Mes données » face à l'indicateur officiel déclaré comparable) n'est jamais appliquée dans ce document : ses pistes, étiquetées « à partir de vos données », ne s'affichent que dans l'application et dans l'annexe facultative du PDF des constats.

### Pistes retenues

1. Piste à explorer : étudier des offres et canaux de distribution conçus pour les femmes. Constat : en 2024, en Tunisie, l'écart de détention d'un compte entre hommes et femmes est de 23,0 pts (49,6 % contre 26,6 %). Association, pas causalité.

   - Groupe cible : femmes
   - Règle : `subgroup_gap` (écart entre sous-groupes ≥ 10 pts)
   - Sources : Écart femmes-hommes de détention d'un compte · TUN · 2024 = 22,96 (percentage_points, `approved`) ; Détention d'un compte - hommes · TUN · 2024 = 49,57 (percent, `approved`) ; Détention d'un compte - femmes · TUN · 2024 = 26,61 (percent, `approved`)

2. Piste à explorer : examiner des comptes à bas coût et sans frais fixes pour les 40 % les plus pauvres. Constat : en 2024, en Tunisie, l'écart de détention d'un compte entre 60 % les plus riches et 40 % les plus pauvres est de 27,0 pts (48,6 % contre 21,7 %). Association, pas causalité.

   - Groupe cible : 40 % les plus pauvres
   - Règle : `subgroup_gap` (écart entre sous-groupes ≥ 10 pts)
   - Sources : Écart de revenu de détention d'un compte · TUN · 2024 = 26,96 (percentage_points, `approved`) ; Détention d'un compte - 60 % des ménages les plus riches · TUN · 2024 = 48,62 (percent, `approved`) ; Détention d'un compte - 40 % des ménages les plus pauvres · TUN · 2024 = 21,66 (percent, `approved`)

3. Piste à explorer : tester des parcours d'ouverture simplifiés et de l'accompagnement pour les adultes du primaire ou moins. Constat : en 2024, en Tunisie, l'écart de détention d'un compte entre adultes du secondaire ou plus et adultes du primaire ou moins est de 17,2 pts (45,8 % contre 28,6 %). Association, pas causalité.

   - Groupe cible : adultes du primaire ou moins
   - Règle : `subgroup_gap` (écart entre sous-groupes ≥ 10 pts)
   - Sources : Écart d'éducation de détention d'un compte · TUN · 2024 = 17,22 (percentage_points, `approved`) ; Détention d'un compte - niveau secondaire ou plus · TUN · 2024 = 45,83 (percent, `approved`) ; Détention d'un compte - niveau primaire ou moins · TUN · 2024 = 28,61 (percent, `approved`)

4. Piste à explorer : explorer des canaux qui ne passent pas par l'employeur pour les adultes hors population active. Constat : en 2024, en Tunisie, l'écart de détention d'un compte entre actifs et adultes hors population active est de 45,6 pts (62,1 % contre 16,6 %). Association, pas causalité.

   - Groupe cible : adultes hors population active
   - Règle : `subgroup_gap` (écart entre sous-groupes ≥ 10 pts)
   - Sources : Écart d'activité de détention d'un compte · TUN · 2024 = 45,55 (percentage_points, `approved`) ; Détention d'un compte - population active · TUN · 2024 = 62,12 (percent, `approved`) ; Détention d'un compte - hors population active · TUN · 2024 = 16,57 (percent, `approved`)

5. Piste à explorer : étudier des offres d'entrée pour les jeunes de 15 à 24 ans. Constat : en 2024, en Tunisie, l'écart de détention d'un compte entre adultes de 25 ans et plus et jeunes de 15 à 24 ans est de 33,8 pts (45,5 % contre 11,7 %). Association, pas causalité.

   - Groupe cible : jeunes de 15 à 24 ans
   - Règle : `subgroup_gap` (écart entre sous-groupes ≥ 10 pts)
   - Sources : Écart d'âge de détention d'un compte · TUN · 2024 = 33,82 (percentage_points, `approved`) ; Détention d'un compte - adultes de 25 ans et plus · TUN · 2024 = 45,48 (percent, `approved`) ; Détention d'un compte - adultes de 15 à 24 ans · TUN · 2024 = 11,66 (percent, `approved`)

6. Piste à explorer : examiner les points de service de proximité (agents, mobile) pour les adultes ruraux. Constat : en 2024, en Tunisie, l'écart de détention d'un compte entre adultes urbains et adultes ruraux est de 16,6 pts (46,7 % contre 30,2 %). Association, pas causalité.

   - Groupe cible : adultes ruraux
   - Règle : `subgroup_gap` (écart entre sous-groupes ≥ 10 pts)
   - Sources : Écart urbain-rural de détention d'un compte · TUN · 2024 = 16,55 (percentage_points, `approved`) ; Détention d'un compte - milieu urbain · TUN · 2024 = 46,74 (percent, `approved`) ; Détention d'un compte - milieu rural · TUN · 2024 = 30,19 (percent, `approved`)

7. Piste à explorer : explorer des comptes individuels faciles à ouvrir pour les adultes sans compte dont un proche en possède un. Constat : en 2024, 22,4 % des adultes en Tunisie n'ont pas de compte et citent « un membre de la famille en a déjà un », contre 16,8 % en moyenne chez les pairs (moyenne partielle, sans Algérie), soit 5,6 pts de plus. Association, pas causalité.

   - Groupe cible : adultes sans compte dont un proche en possède un
   - Règle : `barrier_above_peers` (pays − moyenne des pairs ≥ 5 pts)
   - Sources : Pas de compte : un membre de la famille en a déjà un · TUN · 2024 = 22,40 (percent, `approved`) ; Pas de compte : un membre de la famille en a déjà un · PEERS · 2024 = 16,79 (percent, `approved_with_review_note`)

8. Piste à explorer : explorer l'information sur la protection des clients et la garantie des dépôts pour les adultes sans compte méfiants envers les institutions financières. Constat : en 2024, 15,5 % des adultes en Tunisie n'ont pas de compte et citent « manque de confiance dans les institutions financières », contre 7,5 % en moyenne chez les pairs (moyenne partielle, sans Algérie), soit 8,0 pts de plus. Association, pas causalité.

   - Groupe cible : adultes sans compte méfiants envers les institutions financières
   - Règle : `barrier_above_peers` (pays − moyenne des pairs ≥ 5 pts)
   - Sources : Pas de compte : manque de confiance dans les institutions financières · TUN · 2024 = 15,53 (percent, `approved`) ; Pas de compte : manque de confiance dans les institutions financières · PEERS · 2024 = 7,54 (percent, `approved_with_review_note`)

9. Piste à explorer : examiner l'acceptation des paiements numériques chez les commerçants pour les adultes qui ne paient pas encore par voie numérique. Constat : en 2024, paiement numérique effectué ou reçu : 23,7 % en Tunisie, contre 29,9 % en moyenne chez les pairs, soit 6,2 pts de moins. Association, pas causalité.

   - Groupe cible : adultes qui ne paient pas encore par voie numérique
   - Règle : `usage_below_peers` (moyenne des pairs − pays ≥ 5 pts)
   - Sources : Paiement numérique effectué ou reçu · TUN · 2024 = 23,68 (percent, `approved`) ; Paiement numérique effectué ou reçu · PEERS · 2024 = 29,91 (percent, `approved`)

