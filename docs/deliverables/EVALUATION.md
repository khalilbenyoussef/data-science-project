# Évaluation des agents et approche de référence

- **Généré le** : 2026-11-05T19:04:13
- **Run audité (Route 1)** : `part_d_audit_report`
- **Snapshot** : `v5`
- **Version du catalogue KPI** : 1.7.0
- **Run Route 2 (spec publiée)** : `route2_20261104T125802503588`
- **Sources lues** : `outputs/reports/<run>/*.json`, `data/audit/evaluation.json`, `data/audit/audit_report.json`, `outputs/evaluation/agents.json`, `outputs/evaluation/ask_live.json`, `outputs/evaluation/baseline.json`, `docs/deliverables/manual_baseline.yaml`
- Document généré par `scripts/build_deliverables.py` : ne pas modifier à la main.

## Fraîcheur des mesures

- Dernier audit : 2026-11-04T12:57:50
- Injection de fautes : 2026-11-04T12:59:47
- Évaluation des agents (scripts/evaluate_agents.py) : 2026-11-05T18:20:31
- Contrôle en direct d’Ask Finova : 2026-11-05T18:20:31
- Approche de référence (scripts/baseline_reference.py) : 2026-11-05T18:12:24

## Synthèse par agent

| Agent | Mode | Statut | Durée | Lignes entrée → sortie | Sortie clé | Appels LLM |
|---|---|---|---|---|---|---|
| Collector | déterministe | réussi | 0.13 s | non disponible → 60 361 | 3 source(s) collectée(s) | 0 appel |
| Snapshot | déterministe | réussi | 0.11 s | non disponible → 60 361 | snapshot v5 (rebuild) | 0 appel |
| Profiler | déterministe | réussi | 2.31 s | 60 361 → 60 361 | findex 8 577 × 36 ; fas 32 209 × 57 ; gdp 19 575 × 6 | 0 appel |
| Quality | déterministe + LLM optionnel | réussi | 1.20 s | 60 361 → non disponible | score 0.936, gate réussi | 0 appel |
| ETL | déterministe | réussi | 2.21 s | 60 361 → 90 732 | 90 732 lignes fact, 263 pays | 0 appel |
| Semantic & KPI | déterministe | réussi | 5.55 s | 90 732 → 1 620 | 44 KPI, 1 620 lignes kpi_values (1 267 disponibles, 111 avec revue) | 0 appel |
| Auditor (BI Auditor / XAI) | déterministe + LLM optionnel | réussi | 4.53 s | 1 620 → non disponible | verdict pass_with_warnings (17 réussis, 2 avertissements, 0 échecs) | 0 appel |
| Analyst (FinOVA) | déterministe | réussi | 0.01 s | 96 → 17 | 17 constats sur 96 faits, carte XAI oui | 0 appel |
| Dashboard spec | déterministe | réussi | 0.55 s | non disponible → 96 | 6 pages, 96 faits, publication approved | 0 appel |
| Ask Finova | déterministe + LLM optionnel | à la demande | non disponible | non disponible → non disponible | réponses à la demande, nombres contrôlés contre les faits | non disponible |

## Collector

*Collecte les sources officielles (Findex, FAS, PIB WDI) et les sources utilisateur confirmées ; calcule l'empreinte SHA-256 de chaque fichier.*

- Mode : déterministe
- Run : `demo_20261105T190335` — statut réussi, durée 0.13 s, 0 avertissement(s), 0 erreur(s)
- Sortie clé : 3 source(s) collectée(s)
- Appels LLM mesurés : 0 appel
- run courant reconstruit depuis le snapshot publié : dernier Collector exécuté

## Snapshot

*Versionne les fichiers bruts (blobs dédupliqués par SHA-256) ; sans donnée nouvelle, le run s'arrête.*

- Mode : déterministe
- Run : `part_d_audit_report` — statut réussi, durée 0.11 s, 0 avertissement(s), 0 erreur(s)
- Sortie clé : snapshot v5 (rebuild)
- Appels LLM mesurés : 0 appel
- Snapshot publié après l'audit : `v5` (published)

## Profiler

*Profile chaque source : dimensions, valeurs manquantes, types, colonnes de métadonnées, valeurs atypiques (IsolationForest).*

- Mode : déterministe
- Run : `part_d_audit_report` — statut réussi, durée 2.31 s, 0 avertissement(s), 0 erreur(s)
- Sortie clé : findex 8 577 × 36 ; fas 32 209 × 57 ; gdp 19 575 × 6
- Appels LLM mesurés : 0 appel
- Lignes profilées : 60 361

## Quality

*Contrôle qualité : score par source, gate (seuil configuré), anomalies classées par sévérité, diagnostics de plausibilité, exclusion des sources utilisateur non conformes.*

- Mode : déterministe + LLM optionnel (plan de remédiation rédigé, sans effet sur le score ni le gate ; groq → gemini)
- Run : `part_d_audit_report` — statut réussi, durée 1.20 s, 0 avertissement(s), 0 erreur(s)
- Sortie clé : score 0.936, gate réussi
- Appels LLM mesurés : 0 appel
- Score global 0.936 (seuil 0.70), gate réussi
- Anomalies : critiques 0, élevées 0, moyennes 2, faibles 0
- Diagnostics : 25 ; sources utilisateur exclues : 0

## ETL

*Harmonise les sources (codes pays ISO3, années, unités) et construit le modèle en étoile.*

- Mode : déterministe
- Run : `part_d_audit_report` — statut réussi, durée 2.21 s, 0 avertissement(s), 0 erreur(s)
- Sortie clé : 90 732 lignes fact, 263 pays
- Appels LLM mesurés : 0 appel
- Lignes fact par source : fas 15 753, findex 64 328, gdp 10 651

## Semantic & KPI

*Calcule chaque KPI du catalogue pour le pays focus et les pairs, sur chaque année valide ; attribue un statut de publication.*

- Mode : déterministe
- Run : `part_d_audit_report` — statut réussi, durée 5.55 s, 0 avertissement(s), 0 erreur(s)
- Sortie clé : 44 KPI, 1 620 lignes kpi_values (1 267 disponibles, 111 avec revue)
- Appels LLM mesurés : 0 appel

## Auditor (BI Auditor / XAI)

*Vérification indépendante : recalcul depuis fact sans le code KPI, contrôles de cohérence et de traçabilité, verdict d'audit, explications par valeur ; décide la publication du snapshot.*

- Mode : déterministe + LLM optionnel (reformulation de quelques explications, rejetée si un nombre n'est pas justifié ; groq → gemini)
- Run : `part_d_audit_report` — statut réussi, durée 4.53 s, 0 avertissement(s), 0 erreur(s)
- Sortie clé : verdict pass_with_warnings (17 réussis, 2 avertissements, 0 échecs)
- Appels LLM mesurés : 0 appel
- Contrôles : 17 réussis, 2 avertissements, 0 échecs sur 1 620 lignes
- Publication : 1 509 approuvées, 111 avec réserve, 0 bloquées

### Injection de fautes (9/9 détectées)

Mesure : 2026-11-04T12:59:47

| Faute injectée | Contrôle attendu | Détectée | Verdict |
|---|---|---|---|
| Valeur KPI modifiee (+0,05) | `A1_recomputed_values` | oui | fail |
| Mauvaise unite (densite en percent) | `B1_one_unit_per_kpi` | oui | fail |
| Ligne agregat WLD dans kpi_values | `B3_country_entities_only` | oui | fail |
| Zero au lieu de NULL | `A2_unavailable_rows_are_null` | oui | fail |
| snapshot_id incoherent | `B5_snapshot_and_run_ids` | oui | fail |
| Hash source modifie (rapport qualite) | `B6_source_hashes` | oui | fail |
| KPI provisoire dans le catalogue | `B8_catalog_definitions` | oui | fail |
| Insight citant un mauvais chiffre | `F1_insights_grounded` | oui | pass_with_warnings |
| Insight avec un nombre non cite | `F1_insights_grounded` | oui | pass_with_warnings |

## Analyst (FinOVA)

*Écrit les constats et la carte XAI à partir des faits exportés ; tout nombre d'une phrase doit exister dans les faits (verify_numbers).*

- Mode : déterministe (narration LLM désactivée : analyst.narrate = false)
- Run : `route2_20261104T125802503588` — statut réussi, durée 0.01 s, 0 avertissement(s), 0 erreur(s)
- Sortie clé : 17 constats sur 96 faits, carte XAI oui
- Appels LLM mesurés : 0 appel
- Audit des constats (run `route2_20261104T125802503588`) : 15 audités, 15 acceptés, 0 rejetés, 2 non auditables

## Dashboard spec

*Construit le contrat FinOVA 2.0 validé (pages, métriques, graphiques, faits, avertissements) ; ne calcule aucun KPI et n'approuve aucune publication.*

- Mode : déterministe
- Run : `route2_20261104T125802503588` — statut réussi, durée 0.55 s, 2 avertissement(s), 0 erreur(s)
- Sortie clé : 6 pages, 96 faits, publication approved
- Appels LLM mesurés : 0 appel

## Ask Finova

*Répond aux questions de l'utilisateur sur la vue affichée ; lit les chiffres uniquement via des outils sur les faits ; chaque nombre de la réponse est contrôlé (grounding).*

- Mode : déterministe + LLM optionnel (conversation avec outils sur les faits, nombres contrôlés ; groq → gemini)
- Exécution : à la demande (`POST /api/ask`), pas de rapport de run
- Tests unitaires (LLM simulé), `tests/test_ask_chat.py` : 18/18 réussis, dont 4/4 tests de grounding (exécutés le 2026-11-05T18:13:34)
- Contrôle en direct : **10/10 réponses fondées**, 9 rédigées par le LLM (les autres en repli déterministe) ; modèle groq (openai/gpt-oss-120b), le 2026-11-05T18:20:31.
- Méthode : chaque nombre de la réponse doit figurer dans les faits FinOVA du pays focus et des pairs (même année), être une année de la spec ou un nombre d'un libellé d'unité ; le contrôle ne vérifie pas que le nombre est attribué au bon indicateur.

| Question | Mode | Fondée | Nombres hors faits | Réponse |
|---|---|---|---|---|
| Quel est le taux de détention d'un compte en Tunisie ? | llm | oui | — | En 2024, le taux de détention d’un compte en Tunisie est de 37.8 % (source : tableau de bord Finova). Cette donnée reflète la proportion d’adultes disposant d’un compte bancaire. Aucun autre chiffre n’est fourni dans le  |
| Comment la Tunisie se compare-t-elle au Maroc pour la détention d'un compte ? | llm | oui | — | En 2024, le taux de détention d’un compte est de 37,8 % en Tunisie. Au même moment, le Maroc affiche 44,4 % de détention d’un compte. Ainsi, le Maroc dépasse la Tunisie de quelques points de pourcentage. |
| Quel est l'écart entre les hommes et les femmes ? | llm | oui | — | En 2024, l’écart de détention de compte entre les hommes et les femmes en Tunisie s’élève à +23,0 points de pourcentage. (source : Finova, indicateur « Écart de compte — Genre », 2024). |
| Combien d'adultes utilisent les paiements numériques ? | llm | oui | — | En 2024, 23,7 % des adultes en Tunisie ont effectué ou reçu un paiement numérique. Cette proportion reflète l’usage des services de paiement digital parmi la population adulte. Aucun autre chiffre n’est disponible pour l |
| Combien y a-t-il d'agences bancaires pour 100 000 adultes ? | llm | oui | — | En 2024, la Tunisie comptait 22.37 agences bancaires pour 100 000 adultes. Cette densité reflète la disponibilité des services bancaires dans le pays. |
| Pourquoi les adultes n'ont-ils pas de compte ? | deterministic | oui | — | En 2024, 37.8 % des adultes en Tunisie détiennent un compte. (+1.0 pt vs 2021) |
| Quelle part des adultes épargne auprès d'une institution financière ? | llm | oui | — | En 2024, 48,2 % des adultes en Tunisie épargnent auprès d’une institution financière. |
| Le taux de détention a-t-il progressé depuis 2021 ? | llm | oui | — | Oui, le taux de détention d’un compte a progressé. En 2024 il s’établit à 37,8 % (Tunisie, 2024) et il a augmenté d’un point de pourcentage par rapport à 2021 (variation +1,0 pt, 2024). Cela indique une légère améliorati |
| Et pour le Maroc, quel est le taux de détention d'un compte ? | llm | oui | — | Le taux de détention d’un compte au Maroc en 2024 est de 44.4 %. Cette valeur n’a pas évolué par rapport à 2021, avec une variation de +0.0 point de pourcentage. |
| What is the main barrier to account ownership? | llm | oui | — | En 2024, le principal obstacle à la détention d’un compte en Tunisie est l’absence de documents requis, avec 13,3 % des personnes non bancarisées. Ce taux dépasse celui des services trop chers (12,4 %) et de la distance  |

## Approche de référence

Recalcul naïf de 4 indicateurs directement depuis les CSV bruts (`scripts/baseline_reference.py`), comme un analyste le ferait dans un tableur : filtrer le pays et l'année, lire la colonne, multiplier par 100 ou soustraire deux groupes. Comparaison avec `kpi_values` à la tolérance de l'Auditor.

Mesure : 2026-11-05T18:12:24

| Indicateur | Valeurs comparées | Identiques | Temps Excel (manuel) |
|---|---|---|---|
| `account_ownership` | 22 | 22 | non mesuré |
| `gender_gap` | 21 | 21 | non mesuré |
| `digital_payment_rate` | 19 | 19 | non mesuré |
| `branch_density` | 70 | 70 | non mesuré |

| Approche | Périmètre | Temps mesuré |
|---|---|---|
| Recalcul naïf (pandas) | 4 indicateurs, 5 pays, toutes années | 0.96 s |
| Lecture de `kpi_values` | mêmes valeurs, déjà calculées et auditées | 0.01 s |
| Agent Semantic & KPI | 44 KPI, 1 620 lignes kpi_values (1 267 disponibles, 111 avec revue) | 5.55 s |
| Agent Auditor | recalcul indépendant et contrôles de toutes les lignes | 4.53 s |
| Excel (manuel) | 4 indicateurs | non mesuré |

Résultat : **132/132 valeurs identiques** (tolérance 1e-09), 0 écart(s), 0 valeur(s) publiée(s) introuvable(s) dans le calcul naïf. Le pipeline ajoute ce que le calcul naïf n'apporte pas : statut de publication, moyenne des pairs avec couverture, traçabilité jusqu'au fichier brut et audit indépendant.
