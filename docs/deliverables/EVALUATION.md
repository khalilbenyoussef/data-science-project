# Évaluation des agents et approche de référence

- **Généré le** : 2026-11-12T20:21:56
- **Run audité (Route 1)** : `20261112T201928`
- **Snapshot** : `v16`
- **Version du catalogue KPI** : 1.8.0
- **Run Route 2 (spec publiée)** : `route2_20261112T201947487351`
- **Sources lues** : `outputs/reports/<run>/*.json`, `data/audit/evaluation.json`, `data/audit/audit_report.json`, `outputs/evaluation/agents.json`, `outputs/evaluation/ask_live.json`, `outputs/evaluation/baseline.json`, `docs/deliverables/manual_baseline.yaml`
- Document généré par `scripts/build_deliverables.py` : ne pas modifier à la main.

## Fraîcheur des mesures

- Dernier audit : 2026-11-12T20:19:44
- Injection de fautes : 2026-11-12T20:21:33
- Évaluation des agents (scripts/evaluate_agents.py) : 2026-11-12T20:21:40
- Contrôle en direct d’Ask Finova : 2026-11-06T05:32:30 — **résultat antérieur au dernier audit**
- Approche de référence (scripts/baseline_reference.py) : 2026-11-12T20:21:36

## Synthèse par agent

| Agent | Mode | Statut | Durée | Lignes entrée → sortie | Sortie clé | Appels LLM |
|---|---|---|---|---|---|---|
| Collector | déterministe | réussi | 0,24 s | non disponible → 61 808 | 5 source(s) collectée(s) | 0 appel |
| Snapshot | déterministe | réussi | 0,11 s | non disponible → 61 808 | snapshot v16 (rebuild) | 0 appel |
| Profiler | déterministe | réussi | 2,55 s | 61 808 → 61 808 | findex 8 577 × 36 ; fas 32 209 × 57 ; gdp 19 575 × 6 ; banque_fictive_exemple 23 × 12 ; banque_fictive_exemple1 1 424 × 12 | 0 appel |
| Quality | déterministe + LLM optionnel | réussi | 1,19 s | 61 808 → non disponible | score 0,936, gate réussi | 0 appel |
| ETL | déterministe | réussi | 2,24 s | 61 808 → 92 179 | 92 179 lignes fact, 263 pays | 0 appel |
| Semantic & KPI | déterministe | réussi | 5,50 s | 92 179 → 1 620 | 44 KPI, 1 620 lignes kpi_values (1 267 disponibles, 111 avec revue) | 0 appel |
| Auditor (BI Auditor / XAI) | déterministe + LLM optionnel | réussi | 4,90 s | 1 620 → non disponible | verdict conforme avec avertissements (17 réussis, 2 avertissements, 0 échecs) | 0 appel |
| Analyst (FinOVA) | déterministe | réussi | 0,01 s | 96 → 17 | 17 constats sur 96 faits, carte XAI oui | 0 appel |
| Dashboard spec | déterministe | réussi | 0,60 s | non disponible → 96 | 6 pages, 96 faits, publication approuvée | 0 appel |
| Ask Finova | déterministe + LLM optionnel | à la demande | non disponible | non disponible → non disponible | réponses à la demande, nombres contrôlés contre les faits | non disponible |

## Collector

*Collecte les sources officielles (Findex, FAS, PIB WDI) et les sources utilisateur confirmées ; calcule l'empreinte SHA-256 de chaque fichier.*

- Mode : déterministe
- Run : `20261112T201650` — statut réussi, durée 0,24 s, 0 avertissement(s), 0 erreur(s)
- Sortie clé : 5 source(s) collectée(s)
- Appels LLM mesurés : 0 appel
- run courant reconstruit depuis le snapshot publié : dernier Collector exécuté

## Snapshot

*Versionne les fichiers bruts (blobs dédupliqués par SHA-256) ; sans donnée nouvelle, le run s'arrête.*

- Mode : déterministe
- Run : `20261112T201928` — statut réussi, durée 0,11 s, 0 avertissement(s), 0 erreur(s)
- Sortie clé : snapshot v16 (rebuild)
- Appels LLM mesurés : 0 appel
- Snapshot publié après l'audit : `v16` (published)

## Profiler

*Profile chaque source : dimensions, valeurs manquantes, types, colonnes de métadonnées, valeurs atypiques (IsolationForest).*

- Mode : déterministe
- Run : `20261112T201928` — statut réussi, durée 2,55 s, 0 avertissement(s), 0 erreur(s)
- Sortie clé : findex 8 577 × 36 ; fas 32 209 × 57 ; gdp 19 575 × 6 ; banque_fictive_exemple 23 × 12 ; banque_fictive_exemple1 1 424 × 12
- Appels LLM mesurés : 0 appel
- Lignes profilées : 61 808

## Quality

*Contrôle qualité : score par source, gate (seuil configuré), anomalies classées par sévérité, diagnostics de plausibilité, exclusion des sources utilisateur non conformes.*

- Mode : déterministe + LLM optionnel (plan de remédiation rédigé, sans effet sur le score ni le gate ; groq → gemini)
- Run : `20261112T201928` — statut réussi, durée 1,19 s, 0 avertissement(s), 0 erreur(s)
- Sortie clé : score 0,936, gate réussi
- Appels LLM mesurés : 0 appel
- Score global 0,936 (seuil 0,70), gate réussi
- Anomalies : critiques 0, élevées 0, moyennes 2, faibles 0
- Diagnostics : 25 ; sources utilisateur exclues : 0

## ETL

*Harmonise les sources (codes pays ISO3, années, unités) et construit le modèle en étoile.*

- Mode : déterministe
- Run : `20261112T201928` — statut réussi, durée 2,24 s, 0 avertissement(s), 0 erreur(s)
- Sortie clé : 92 179 lignes fact, 263 pays
- Appels LLM mesurés : 0 appel
- Lignes fact par source : fas 15 753, findex 64 328, gdp 10 651, user:banque_fictive_exemple 23, user:banque_fictive_exemple1 1 424

## Semantic & KPI

*Calcule chaque KPI du catalogue pour le pays focus et les pairs, sur chaque année valide ; attribue un statut de publication.*

- Mode : déterministe
- Run : `20261112T201928` — statut réussi, durée 5,50 s, 0 avertissement(s), 0 erreur(s)
- Sortie clé : 44 KPI, 1 620 lignes kpi_values (1 267 disponibles, 111 avec revue)
- Appels LLM mesurés : 0 appel

## Auditor (BI Auditor / XAI)

*Vérification indépendante : recalcul depuis fact sans le code KPI, contrôles de cohérence et de traçabilité, verdict d'audit, explications par valeur ; décide la publication du snapshot.*

- Mode : déterministe + LLM optionnel (reformulation de quelques explications, rejetée si un nombre n'est pas justifié ; groq → gemini)
- Run : `20261112T201928` — statut réussi, durée 4,90 s, 0 avertissement(s), 0 erreur(s)
- Sortie clé : verdict conforme avec avertissements (17 réussis, 2 avertissements, 0 échecs)
- Appels LLM mesurés : 0 appel
- Contrôles : 17 réussis, 2 avertissements, 0 échecs sur 1 620 lignes
- Publication : 1 509 approuvées, 111 avec réserve, 0 bloquées

### Injection de fautes (9/9 détectées)

Mesure : 2026-11-12T20:21:33

| Faute injectée | Contrôle attendu | Détectée | Verdict |
|---|---|---|---|
| 1. Valeur KPI modifiée (+0,05) | A1 – Valeurs recalculées<br><sub>`A1_recomputed_values`</sub> | oui | non conforme |
| 2. Mauvaise unité (densité en percent) | B1 – Une unité par indicateur<br><sub>`B1_one_unit_per_kpi`</sub> | oui | non conforme |
| 3. Ligne agrégat WLD dans kpi_values | B3 – Pays uniquement, sans agrégat<br><sub>`B3_country_entities_only`</sub> | oui | non conforme |
| 4. Zéro au lieu de NULL | A2 – Valeurs indisponibles vides<br><sub>`A2_unavailable_rows_are_null`</sub> | oui | non conforme |
| 5. snapshot_id incohérent | B5 – Version et run cohérents<br><sub>`B5_snapshot_and_run_ids`</sub> | oui | non conforme |
| 6. Hash source modifié (rapport qualité) | B6 – Empreintes des sources<br><sub>`B6_source_hashes`</sub> | oui | non conforme |
| 7. KPI provisoire dans le catalogue | B8 – Définitions du catalogue<br><sub>`B8_catalog_definitions`</sub> | oui | non conforme |
| 8. Insight citant un mauvais chiffre | F1 – Constats fondés sur les chiffres<br><sub>`F1_insights_grounded`</sub> | oui | conforme avec avertissements |
| 9. Insight avec un nombre non cité | F1 – Constats fondés sur les chiffres<br><sub>`F1_insights_grounded`</sub> | oui | conforme avec avertissements |

Fautes 8–9 (constats) : elles sont détectées par le rejet du constat concerné ; les données restent exactes, donc le verdict des données reste « conforme avec avertissements ».

## Analyst (FinOVA)

*Écrit les constats et la carte XAI à partir des faits exportés ; tout nombre d'une phrase doit exister dans les faits (verify_numbers).*

- Mode : déterministe (narration LLM désactivée : analyst.narrate = false)
- Run : `route2_20261112T201947487351` — statut réussi, durée 0,01 s, 0 avertissement(s), 0 erreur(s)
- Sortie clé : 17 constats sur 96 faits, carte XAI oui
- Appels LLM mesurés : 0 appel
- Audit des constats (run `route2_20261112T201947487351`) : 15 audités, 15 acceptés, 0 rejetés, 2 non auditables

## Dashboard spec

*Construit le contrat FinOVA 2.0 validé (pages, métriques, graphiques, faits, avertissements) ; ne calcule aucun KPI et n'approuve aucune publication.*

- Mode : déterministe
- Run : `route2_20261112T201947487351` — statut réussi, durée 0,60 s, 2 avertissement(s), 0 erreur(s)
- Sortie clé : 6 pages, 96 faits, publication approuvée
- Appels LLM mesurés : 0 appel

## Ask Finova

*Répond aux questions de l'utilisateur sur la vue affichée ; lit les chiffres uniquement via des outils sur les faits ; chaque nombre de la réponse est contrôlé (grounding).*

- Mode : déterministe + LLM optionnel (conversation avec outils sur les faits, nombres contrôlés ; groq → gemini)
- Exécution : à la demande (`POST /api/ask`), pas de rapport de run
- Tests unitaires (LLM simulé), `tests/test_ask_chat.py` : 18/18 réussis, dont 3/3 tests de grounding (exécutés le 2026-11-12T20:21:38)
- Contrôle en direct : **10/10 réponses fondées**, 9 rédigées par le LLM (les autres en repli déterministe) ; modèle groq (openai/gpt-oss-120b), le 2026-11-06 05:32:30.
- Méthode : chaque nombre de la réponse doit figurer dans les faits FinOVA du pays focus et des pairs (même année), être une année de la spec ou un nombre d'un libellé d'unité ; le contrôle ne vérifie pas que le nombre est attribué au bon indicateur.

| Question | Mode | Fondée | Nombres hors faits | Réponse |
|---|---|---|---|---|
| Quel est le taux de détention d'un compte en Tunisie ? | llm | oui | — | En 2024, le taux de détention d’un compte en Tunisie est de 37,8 %. Cette valeur provient du tableau de bord Finova pour l’année 2024. Si vous avez besoin d’autres indicateurs ou de comparaisons, n’hésitez pas à me le de |
| Comment la Tunisie se compare-t-elle au Maroc pour la détention d'un compte ? | llm | oui | — | En 2024, la Tunisie affiche un taux de détention d’un compte de 37,8 %, contre 44,4 % au Maroc. Le Maroc se situe donc environ sept points de pourcentage au‑dessus de la Tunisie. Cette différence reflète un niveau d’incl |
| Quel est l'écart entre les hommes et les femmes ? | llm | oui | — | En 2024, l’écart de détention de compte entre les hommes et les femmes en Tunisie est de +23,0 pt. Cela signifie que les hommes sont plus susceptibles de posséder un compte que les femmes de ce même écart. L’indicateur m |
| Combien d'adultes utilisent les paiements numériques ? | llm | oui | — | En 2024, 23,7 % des adultes en Tunisie utilisent les paiements numériques. Cette proportion reflète la part des adultes qui ont effectué ou reçu un paiement numérique au cours de l'année. Aucun autre chiffre n’est dispon |
| Combien y a-t-il d'agences bancaires pour 100 000 adultes ? | deterministic | oui | — | En 2024, le réseau d'agences est de 22,37 / 100k adultes. |
| Pourquoi les adultes n'ont-ils pas de compte ? | llm | oui | — | En 2024, 9,2 % des adultes déclarent que les institutions financières sont trop éloignées, 12,4 % estiment que les services sont trop chers, et 13,3 % n’ont pas les documents requis. Ces trois obstacles – distance, coût  |
| Quelle part des adultes épargne auprès d'une institution financière ? | llm | oui | — | En 2024, 48,2 % des adultes en Tunisie déclarent épargner auprès d’une institution financière. Cette proportion reflète l’ensemble des formes d’épargne recensées dans le pays. Aucun autre chiffre n’est disponible pour ce |
| Le taux de détention a-t-il progressé depuis 2021 ? | llm | oui | — | Oui, le taux de détention d’un compte a progressé depuis 2021, affichant une hausse de +1,0 point en 2024. En 2024, le taux s’établit à 37,8 %. Cette évolution indique une légère amélioration de l’inclusion financière. |
| Et pour le Maroc, quel est le taux de détention d'un compte ? | llm | oui | — | Le taux de détention d’un compte au Maroc est de 44,4 % en 2024. |
| What is the main barrier to account ownership? | llm | oui | — | Le principal obstacle à la détention d’un compte en Tunisie est le coût perçu des services financiers, qui représente 12,4 % de la population en 2024. En comparaison, la distance des institutions financières constitue 9, |

## Approche de référence

Recalcul naïf de 4 indicateurs directement depuis les CSV bruts (`scripts/baseline_reference.py`), comme un analyste le ferait dans un tableur : filtrer le pays et l'année, lire la colonne, multiplier par 100 ou soustraire deux groupes. Comparaison avec `kpi_values` à la tolérance de l'Auditor.

Mesure : 2026-11-12T20:21:36

| Indicateur | Valeurs comparées | Identiques | Temps Excel (manuel) |
|---|---|---|---|
| `account_ownership` | 22 | 22 | non mesuré |
| `gender_gap` | 21 | 21 | non mesuré |
| `digital_payment_rate` | 19 | 19 | non mesuré |
| `branch_density` | 70 | 70 | non mesuré |

| Approche | Périmètre | Temps mesuré |
|---|---|---|
| Recalcul naïf (pandas) | 4 indicateurs, 5 pays, toutes années | 0,84 s |
| Lecture de `kpi_values` | mêmes valeurs, déjà calculées et auditées | 0,01 s |
| Agent Semantic & KPI | 44 KPI, 1 620 lignes kpi_values (1 267 disponibles, 111 avec revue) | 5,50 s |
| Agent Auditor | recalcul indépendant et contrôles de toutes les lignes | 4,90 s |
| Excel (manuel) | 4 indicateurs | non mesuré |

Résultat : **132/132 valeurs identiques** (tolérance 1e-09), 0 écart(s), 0 valeur(s) publiée(s) introuvable(s) dans le calcul naïf. Le pipeline ajoute ce que le calcul naïf n'apporte pas : statut de publication, moyenne des pairs avec couverture, traçabilité jusqu'au fichier brut et audit indépendant.
