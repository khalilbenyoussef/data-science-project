# Rapport d'audit — BIFlow Route 1 + Route 2

- **Date** : 2026-10-26
- **Périmètre** : code Python, configuration, données traitées, agents Route 2, dashboard React, tests
- **Méthode** : revue statique ciblée, exécution réelle sur `data/`, suite de tests complète, validation navigateur desktop/mobile, inspection des artefacts de provenance
- **Verdict global** : **Route 2 conforme au cadrage et utilisable**, avec des réserves de gouvernance des données et quelques points de sécurité/reproductibilité à traiter avant toute publication. Aucun secret exposé, aucune vulnérabilité critique détectée.

---

## 1. Synthèse exécutive

La Route 2 demandée (warehouse → Semantic & KPI → BI Analyst → Dashboard) est livrée et fonctionne sur les données réelles :

| Indicateur de run (`route2_final`) | Valeur |
|---|---|
| Statut | `success` |
| Observations | 18 / 18 disponibles |
| Observations en revue | 18 |
| Constats | 50 (12 revue, 0 alerte, 38 info) |
| Publication | `not_evaluated` (non approuvée) |
| Erreurs | 0 |

- **BI Analyst** : 100 % déterministe, aucun LLM, constats rattachés à des preuves (`EV-…`, `TR-…`, `CMP-…`).
- **Dashboard** : React 18 + Vite 5 + ECharts 5, contrat JSON validé, aucun calcul de valeur côté front.
- **Route 1** : aucun agent modifié ; seules des extensions additives ont été faites (`state.py`, exports, sous-commandes CLI, sections de configuration).
- **Absence de données** : jamais remplacée par zéro, jamais interpolée ; statut `unavailable` et motif conservés.
- **Tests** : 70 nouveaux tests Route 2 ; suite complète **575 réussis, 1 échec environnemental** (`langchain_google_genai` absent de l'environnement, sans lien avec la Route 2).

**Réserves principales** : chaîne de provenance incomplète (lineage non portable, warehouse non empreinté, rapport qualité non rattaché), absence de dépôt Git, dépendances Python non verrouillées, cache LLM en pickle.

---

## 2. Périmètre et éléments examinés

| Élément | Volume / état |
|---|---|
| Code Python | 47 fichiers, ≈ 6 340 lignes dans `src/` |
| Tests Python | ≈ 3 682 lignes, 576 cas |
| Front | 12 fichiers TypeScript/TSX + CSS, build Vite |
| Warehouse | 79 251 faits, 3 592 lignes pays-année, 268 pays, 106 indicateurs |
| Sources brutes | `findex.csv` (2,6 Mo), `fas.csv` (129 Mo), `gdp.csv` (1,0 Mo) |
| Artefacts Route 2 | `analysis_dataset.json` 98 Ko, `bi_analyst.md` 21 Ko, `dashboard_data.json` 112 Ko |

Hors périmètre : audit d'intrusion externe, certification des définitions Findex/FAS, exécution des providers LLM (aucune clé fournie), audit de l'hébergement.

---

## 3. Conformité aux exigences

| Exigence | Statut | Preuve |
|---|---|---|
| Ne pas modifier la logique des autres agents | **Conforme** | Agents Route 1 inchangés ; tests d'isolation ; `STEP_ORDER` et `AGENT_CLASSES` inchangés |
| Implémenter BI Analyst + Dashboard selon l'architecture | **Conforme** | `bi_analyst.py`, `dashboard.py`, `analysis_graph.py`, `tools/analysis.py`, `tools/dashboard_contract.py` |
| Narration déterministe, sans LLM | **Conforme** | `get_llm()` neutralisé, `cfg.llm.enabled=False` forcé, `build_agent_llm` interdit dans les tests |
| Aucune valeur inventée | **Conforme** | `value=None` + `availability_status="unavailable"` + motif ; pas d'interpolation |
| Comparaisons = droite − gauche | **Conforme** | `difference_formula="right.value - left.value"`, `percentage_points` pour les pourcentages |
| Revue et publication préservées | **Conforme** | `publication_status="not_evaluated"`, `requires_review`, badges et notices |
| Front React + ECharts + Vite + JSON | **Conforme** | `dashboard/`, contrat `1.0`, export `dashboard/public/data/dashboard.json` |
| Arborescence et démarche du projet | **Conforme** | Agents dans `src/biflow/agents`, outils dans `src/biflow/tools`, CLI `main.py`, config `config.yaml`, tests `tests/`, rapports `outputs/reports/` |
| Validation sur `data/` | **Conforme** | Run `route2_final` sur `TUN, MAR, DZA` |

---

## 4. Architecture livrée

```
Warehouse DuckDB (lecture seule)
        │  SemanticKpiTools (6 KPI, 6 actions)
        ▼
AnalysisService ──► analysis_dataset.json
        │
        ├──► BiAnalystAgent ──► bi_analyst.{json,md} (constats + preuves)
        │
        └──► DashboardAgent ──► dashboard_data.json
                                   └──► dashboard/public/data/dashboard.json
                                              └──► React / ECharts
```

Contrôles structurants :

- contrats Pydantic stricts (`AnalysisRequest`, réponses KPI) ;
- validation du contrat dashboard **fail-closed** : nombre fini, cohérence disponibilité/valeur, identifiants de preuve uniques ;
- écritures JSON atomiques (temporaire + remplacement) ;
- DuckDB ouvert en `read_only=True`, requêtes paramétrées ;
- orchestration LangGraph **et** repli séquentiel testés à parité.

---

## 5. Sécurité

### Points positifs vérifiés

- **Aucun secret en dur** dans le code, la configuration ou les logs ; `.env` absent, `.env.example` neutre.
- **Aucun** `eval`, `exec`, `shell=True`, `os.system`, `yaml.load` non sûr, `verify=False`.
- **Injection SQL** : requêtes KPI paramétrées ; aucune concaténation de valeurs dans le SQL.
- **Front** : aucun `dangerouslySetInnerHTML`, aucun `innerHTML`, aucun lien externe ; React échappe les textes.
- **Réseau** : seul le Collector appelle l'API World Bank (HTTPS, certificats par défaut) ; la Route 2 n'a aucun chemin réseau.
- **Écritures** : validation avant export, temporaires et repli d'écriture en cas de verrou Windows.

### Constats

| # | Sévérité | Constat | Impact | Recommandation |
|---|---|---|---|---|
| S1 | **Moyenne** | Cache LLM désérialisé avec `pickle.load` (`src/biflow/llm.py:121`) | Un fichier `.pkl` altéré dans `outputs/llm_cache` peut exécuter du code au prochain run | Remplacer par un format de données (JSON/MessagePack) ou signer les entrées (HMAC) et restreindre les permissions du dossier |
| S2 | **Moyenne** | Dépendances Python non verrouillées (`>=` uniquement, pas de lock/hashes) | Builds non reproductibles, dérive de versions, surface supply-chain | Générer un lock (`uv`/`pip-compile`) avec hashes ; conserver `package-lock.json` côté front |
| S3 | **Moyenne** | Aucun dépôt Git dans le projet | Pas d'historique, de revue de diff ni de retour arrière fiable | Initialiser Git, protéger la branche principale, signer les releases |
| S4 | **Faible** | Tooltips ECharts construits en HTML avec des libellés issus des données (`BarComparison.tsx:38`, `TrendChart.tsx:40`) | Un nom de pays HTML malveillant dans le warehouse pourrait injecter du balisage dans l'infobulle | Échapper les libellés ou utiliser `renderMode: "richText"` |
| S5 | **Faible** | Validation du contrat limitée aux cartes ; les tableaux `series`, `rankings`, `comparisons`, `table` ne sont pas vérifiés valeur par valeur | Un JSON altéré peut atteindre les graphiques avec des types inattendus | Étendre `validate_dashboard_data` et `validate.ts` aux valeurs imbriquées |
| S6 | **Faible** | Export CSV sans neutralisation des préfixes de formule (`=`, `+`, `-`, `@`) | Risque d'injection de formule à l'ouverture dans Excel | Préfixer d'une apostrophe les cellules texte commençant par ces caractères |
| S7 | **Faible** | Chemins de provenance lus depuis `lineage.json` et empreintés sans restriction de racine | Un lineage altéré peut faire lire/hacher un fichier arbitraire accessible au processus | Restreindre les chemins à la racine projet ou à un allowlist |
| S8 | **Info** | Pas de Content-Security-Policy sur le dashboard | Défense en profondeur limitée si le front est exposé au-delà de localhost | Ajouter une CSP stricte au déploiement |
| S9 | **Info** | `docs/` est ignoré par `.gitignore` | La documentation de handoff n'est pas versionnée | Versionner `docs/` ou documenter explicitement son exclusion |

Aucun constat **critique** ou **élevé** de sécurité.

---

## 6. Gouvernance des données et provenance

### Constats factuels

1. **Lineage non portable** : `data/processed/lineage.json` référence des chemins absolus d'une autre machine (`C:\Mohamed ali Jabri\…`). Le run enregistré est `p5_audit_check` du 2026-10-22.
2. **Sources brutes** : les chemins enregistrés sont inaccessibles ici, d'où `raw_source_unavailable`. **Cependant**, les empreintes locales correspondent aux empreintes enregistrées :

   | Source | SHA-256 enregistré | SHA-256 local | Correspondance |
   |---|---|---|---|
   | findex | `35f3fa934adf…` | `35f3fa934adf…` | oui |
   | fas | `f60b4d1b3de6…` | `f60b4d1b3de6…` | oui |
   | gdp | `bc388c7bb5d8…` | `bc388c7bb5d8…` | oui |

3. **Liaison de contenu non vérifiée** : le lineage ne contient pas d'empreinte du warehouse. Le SHA-256 observé localement est `fa461c098b68…`.
4. **Rapport qualité non rattaché** : `quality_report.json` n'a ni `run_id` ni `inputs` ; il ne contient pas la clé `diagnostics`. Le score `0,9282` et le gate `PASS` ne peuvent donc pas être reliés au run de lineage.

### Conséquence

La Route 2 applique correctement le principe **fail-closed** : les 18 observations sont marquées « revue requise » et la publication reste `not_evaluated`. Il ne s'agit pas d'une corruption des valeurs, mais d'une **chaîne de preuve incomplète**.

### Recommandations (propriétaire Route 1)

- écrire des chemins **relatifs/portables** dans `lineage.json` ;
- ajouter `warehouse_sha256` aux sorties du lineage ;
- ajouter `run_id`, `inputs` et `diagnostics` (même vide) au rapport qualité ;
- régénérer lineage et rapport qualité sur la machine cible ;
- conserver `not_evaluated` jusqu'à revue humaine et signature des 18 observations.

---

## 7. Robustesse et exploitation

| Sujet | Constat |
|---|---|
| Verrou fichier Windows | Rencontré pendant la validation : le serveur Vite conservait `dashboard.json` sans partage de suppression. **Corrigé** dans le module Route 2 : 4 tentatives puis repli en écriture sur place, sans échec du run. |
| Parité d'orchestration | LangGraph et repli séquentiel testés pour chaque étape (`analyst`, `dashboard`, `all`). |
| Requête invalide | Échoue **avant** tout agent ; aucun fallback vers la Route 1, aucune reprise. |
| Échec d'agent | Run `failed`, erreur persistée dans `run.json`, pas de dashboard partiel exporté. |
| Lecture des données | DuckDB `read_only` ; empreinte du warehouse inchangée après les tests. |
| Front | Build TypeScript strict réussi (675,34 Ko JS / 223,69 Ko gzip ; CSS 12,42 Ko / 3,38 Ko gzip). |
| UX | Vérifié en 1440 px (6 cartes sur une ligne) et 515 px (1 colonne), sans débordement horizontal. |
| Accessibilité | `aria-label`, `aria-pressed`, `role="status"`, `role="alert"`, graphiques `role="img"` ; animations réduites respectées. |

---

## 8. Tests et validation

### Nouveaux tests (70 cas)

| Fichier | Couverture |
|---|---|
| `tests/test_analysis.py` | Contrats de requête, disponibilité, séries, tendances, classements, comparaisons, provenance, lecture seule, sérialisation |
| `tests/test_bi_analyst.py` | Constats déterministes, preuves, top-N, indisponibilité, absence de LLM, réutilisation du dataset, échec propre |
| `tests/test_dashboard.py` | Copie des valeurs, validation fail-closed, export atomique + verrou, agent, réutilisation, requête invalide |
| `tests/test_analysis_graph.py` | Parité LangGraph/séquentiel, étages, isolation Route 1, LLM forcé off, échecs sans reprise, artefacts |

### Suite complète

```text
1 failed, 575 passed in 207.81s
FAILED tests/test_llm.py::test_build_agent_llm_skips_wrong_key_format
```

L'échec est **environnemental** : `langchain_google_genai` n'est pas installé dans `.venv-audit`, donc le test ne peut pas construire le provider Gemini factice. Il est sans lien avec la Route 2 et n'indique pas une régression.

### Validation réelle

- `python main.py dashboard --country TUN,MAR,DZA --mode latest --run-id route2_final` → `success`.
- Valeurs TUN 2024 : compte 37,84 %, agences 22,37 / 100k adultes, paiement numérique 23,68 %, épargne 48,25 %, emprunt 43,51 %, sans compte 62,16 %.
- Classement compte 2024 : MAR 44,39 % > TUN 37,84 % > DZA 35,29 %.
- Aucun zéro de remplissage ; 18 observations en revue avec motifs.

---

## 9. Risques résiduels et priorités

| Priorité | Action | Responsable suggéré |
|---|---|---|
| **P1** | Compléter le schéma lineage/qualité (chemins portables, hash warehouse, run_id/inputs/diagnostics) | Équipe Route 1 |
| **P1** | Remplacer/signer le cache pickle | Équipe plateforme |
| **P1** | Verrouiller les dépendances Python et initialiser Git | Équipe projet |
| **P2** | Échapper les libellés des tooltips ECharts | Équipe front |
| **P2** | Étendre la validation aux tableaux imbriqués | Équipe Route 2 |
| **P2** | Neutraliser les formules dans les exports CSV | Équipe ETL |
| **P3** | CSP, revue des permissions de `outputs/`, versionnement de `docs/` | Équipe projet |

---

## 10. Verdict

- **Route 2 : acceptée techniquement.** Elle respecte l'architecture, le déterminisme, l'absence de LLM, la lecture seule et les règles de non-invention des valeurs.
- **Publication des données : non approuvée.** Le statut `not_evaluated` est conservé ; 18 observations exigent une revue humaine, et la chaîne de provenance doit être réparée côté Route 1.
- **Sécurité : aucun risque critique.** Les points S1–S3 doivent être traités avant une mise en production ou un partage large.
- **Traçabilité du code : insuffisante** tant que le projet n'est pas versionné dans Git.

Ce rapport ne constitue pas une certification des définitions Findex/FAS ni une approbation de publication.
