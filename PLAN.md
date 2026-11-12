# PLAN — Finova Route 2 : Analyst, Dashboard, UI

- **Date** : 2026-10-29
- **Statut** : approuvé — phases 0 à 5 livrées (voir sections 11–12 pour les correctifs).
- **Périmètre** : agents Route 2 « Analyst » et « Dashboard », contrat de spec, API FastAPI, UI React `dashboard_app/`.
- **Hors périmètre** : XAI, Route 1, catalogue KPI, publication/approbation.

---

## 0. Objectif

Livrer la Route 2 validée :

```
Orchestrator -> Route 1 (Collector -> Profiler -> Quality [PASS -> ETL | FAIL -> stop + rapport d'erreur] -> ETL -> DuckDB)
             -> Route 2 (BI Semantic/KPI -> Analyst || Dashboard)
```

avec 7 pages UI (Login, Overview, Inclusion & Inequalities, Access & Credit, Why exclusion?, Poverty & SMIG, Data & Pipeline), quatre fournisseurs de données tracés (semantic, warehouse, reference, placeholder) et un chat « Ask Finova » sans calcul LLM.

---

## 1. Constats préalables (vérifiés sur le dépôt et le warehouse)

### 1.1 Trois fichiers de la liste « New files » existent déjà

| Fichier demandé | État réel | Décision proposée |
|---|---|---|
| `src/biflow/agents/dashboard.py` | Existe (100 l.), `DashboardAgent` produit le contrat `schema_version 1.0` consommé par `dashboard/`, testé par `tests/test_dashboard.py` | **Étendre additivement** : ajouter `DashboardSpecAgent` dans le même module ; `DashboardAgent` et son contrat restent inchangés |
| `src/biflow/tools/analysis.py` | Existe (834 l.), dataset déterministe Route 2, testé par `tests/test_analysis.py` | **Réutiliser tel quel** (source unique des faits KPI) ; ne pas dupliquer |
| `tests/test_dashboard.py` | Existe (208 l.) | **Ne pas modifier** (contrainte « existing tests ») ; nouveaux tests dans `tests/test_dashboard_spec.py` |

Conséquence : 2 fichiers de la commande ne seront pas « créés » mais « étendus sans régression », et le nouveau fichier de test Dashboard s'appelle `test_dashboard_spec.py`. **Cette déviation doit être approuvée.**

### 1.2 Valeurs acceptation déjà présentes dans le warehouse (lecture seule vérifiée)

| Attendu | Observé | Statut |
|---|---|---|
| Compte TUN 2024 | 37,844486 % | OK |
| Compte 2021 / 2017 | 36,853 % / 36,907 % (+0,99 pt) | OK |
| Paiement numérique `g20_any` 2024 | 23,6812 % (fact) | OK côté KPI catalog |
| Agences /100k | 22,368 | OK |
| ATM /100k 2024 / 2017 | 35,439 / 29,777 (+19,0 %) | OK |
| Genre 2024 | femmes 26,61 % / hommes 49,57 % = 22,96 pp (2021 : 16,39 pp) | OK |
| Pairs 2024 | DZA 35,29 / EGY 43,11 / JOR 46,46 / MAR 44,39 | OK |
| MAR − TUN | +6,5418 pp | OK |
| `fin17a` / `fin22a` / `fin24aP` 2024 | 21,61 % / 3,55 % / 88,39 % | Disponible |
| Urbain / rural 2024 | 46,74 % / 30,19 % | Disponible |
| Groupes | genre, revenu, âge, éducation, activité, urbanicité (12 valeurs) | Disponible |
| Barrières `fin11a-f` | **0 ligne** dans `fact` | Placeholder « To load » confirmé |
| Dépôts/crédits % PIB | **absents** du warehouse (6 séries FAS seulement) | Placeholder « To load » confirmé |

### 1.3 Écart de données à corriger avant l'UI

`country_year.digital_payment` vaut **11,90 %** (ancien mapping `dig_acc`) alors que le KPI catalog `digital_payment_rate` vaut **23,68 %** (`g20_any`). Le code ETL est déjà corrigé (`etl.py:656`) mais **le warehouse n'a pas été migré**. Le rebuild demandé (`python main.py run --from quality --no-llm`) est donc obligatoire en phase 0, et l'UI **ne lira jamais** la colonne large `digital_payment` (elle utilisera le KPI semantic).

### 1.4 Contraintes d'environnement

- `.venv-audit` : Python 3.14, LangGraph présent, **`fastapi`/`uvicorn` absents**, `langchain-google-genai`/`langchain-groq` absents, pas de `.env`.
- Front : Node 24, npm 11 ; `dashboard_app/web` n'existe pas encore.
- Aucun dépôt Git ; `data/` et `outputs/` ignorés (ne jamais committer de données).

---

## 2. Décisions à valider (impact fonctionnel)

1. **Fichiers déjà existants** : approche additive (§1.1) plutôt que remplacement.
2. **Épargne formelle vs informelle** : `save_any_t_d − fin17a` n'est pas une mesure officielle d'épargne informelle. Proposition : afficher côte à côte « épargne (toute) » et « épargne en institution financière », **sans barre « informelle » dérivée**, avec note méthodologique. Même logique pour l'emprunt.
3. **`fin24aP`** : la colonne est étiquetée « Paiement numerique (vague 2024) » dans `dictionary.py` alors que la définition Findex 2025 est « could obtain emergency money ». `dictionary.py` reste intact : la carte affiche un badge de revue « libellé à vérifier » et la valeur brute.
4. **Chat Ask Finova** : routage d'intentions **déterministe** (liste fermée), LLM uniquement pour la formulation, avec vérification numérique stricte ; aucune requête SQL libre, aucun chiffre hors faits.
5. **Année** : mode par défaut = dernière année disponible (2024) ; si l'utilisateur choisit une année sans observation, affichage `unavailable` avec l'année réellement utilisée, **jamais de substitution silencieuse**.
6. **Référence statique** : chaque valeur (SMIG, pauvreté INS 2021, benchmarks Arab LMIC/LMIC/World, FX, UNDP/OIF) doit porter `value, unit, year, source, static: true, caveat`. **Sources à confirmer** (§10).

---

## 3. Fichiers

### 3.1 Nouveaux

| Fichier | Rôle |
|---|---|
| `PLAN.md` | Ce document |
| `REQUEST_CATALOG.md` | KPI à demander au propriétaire du catalogue (ATM, dépôts, crédits, PIB, barrières, `fin24aP`) |
| `src/biflow/tools/dashboard_spec.py` | Modèles Pydantic de la spec (pages, widgets, chips de provenance, notices, diff) + validation fail-closed |
| `src/biflow/tools/warehouse_reader.py` | Interface read-only DuckDB pour séries **hors catalogue** (fact dimensions, country_year), requêtes paramétrées |
| `src/biflow/agents/analyst.py` | Faits déterministes, auto-insight, carte XAI, réponses Ask, texte LLM vérifié |
| `src/biflow/route2_graph.py` | `run_route2()` : semantic -> (analyst ∥ dashboard), LangGraph + repli séquentiel |
| `config/reference/finova_reference.yaml` | SMIG, INS, benchmarks, FX, UNDP/OIF (chaque entrée sourcée) |
| `dashboard_app/api/__init__.py`, `main.py`, `schemas.py` | FastAPI read-only : `GET /api/spec`, `GET /api/runs`, `POST /api/ask` |
| `dashboard_app/web/` | React + Vite + TS : 7 pages, composants SVG (dumbbell, gap), thème Finova, chat docké |
| `tests/test_dashboard_spec.py` | Spec, provenance, historique/diff, validations |
| `tests/test_warehouse_reader.py` | Lecture read-only, années réelles, To load, isolation |
| `tests/test_analyst.py` | Faits, XAI, Ask, contrôle des nombres, fallback sans LLM |
| `tests/test_route2_graph.py` | Parité LangGraph/séquentiel, parallélisme, artefacts, LLM off |
| `tests/test_api.py` | Endpoints, schémas, read-only, absence de réseau |

### 3.2 Modifiés (édits minimaux autorisés)

| Fichier | Édit |
|---|---|
| `src/biflow/state.py` | clés optionnelles `user_question`, `analysis`, `dashboard_spec` |
| `src/biflow/agents/__init__.py` | 2 exports : `AnalystAgent`, `DashboardSpecAgent` |
| `src/biflow/agents/dashboard.py` | ajout de `DashboardSpecAgent` (classe séparée) + historique/diff |
| `config/config.yaml` | `analyst` (LLM narrative, peer list, reference path), `dashboard` (spec_output, history_dir, ask), `llm.routing.analyst` |
| `requirements.txt`, `pyproject.toml` | `fastapi`, `uvicorn` (dev/run) |
| `README.md` | nouvelle section « Finova UI — Route 2 » (installation, run, rebuild warehouse) |

### 3.3 Interdits (inchangés)

`collector.py`, `profiler.py`, `quality.py`, `etl.py`, `semantic_kpi.py` (agent et tools), `tools/kpi.py`, `tools/kpi_provenance.py`, `tools/dictionary.py`, `graph.py`, `semantic_graph.py`, `config/kpi_catalog.v1.yaml`, `tests/*` existants.

---

## 4. Modèle de spec (Pydantic)

```
ProvenanceChip  kind: semantic|warehouse|reference|placeholder
                label, detail, sources[], definition_status, requires_review, review_reasons[]
WhySheet        definition, source, filter, year_used, definition_status, review_reasons[]
KpiCardSpec     kpi_id, label, value|null, unit, year_used, availability_status,
                chip, why, review_reasons[], delta{vs_year, value_pp}|null
SeriesSpec      id, label, unit, points[{year, value|null, status, reason}], chip
DumbbellSpec    groups[{group, dimension, left, right, gap_pp, year, status}], chip
FunnelSpec      steps[{id, label, value|null, unit, year, status}], chip
ReferenceItem   id, label, value, unit, year, source, static: true, caveat
Notice          code, severity, message
SnapshotDiff    baseline_run_id|null, changes[{kpi_id, from, to, delta, kind}]
DashboardSpec   schema_version, generated_at, run_id, country, year, pages[], history, provenance
```

Règles de validation (fail-closed, sur le modèle de `dashboard_contract.py`) : valeur non finie interdite, `available` ⇒ valeur numérique, `unavailable` ⇒ `null`, `evidence_id` unique, chip obligatoire pour chaque widget, `fin24aP` ⇒ `requires_review=true`.

---

## 5. Contrats API

| Endpoint | Méthode | Réponse |
|---|---|---|
| `/api/spec` | GET | Spec précalculée par `DashboardSpecAgent` (lecture seule, filtre `country`,`year`) |
| `/api/runs` | GET | Historique `outputs/dashboard/history/*.json` trié + résumé du dernier run |
| `/api/ask` | POST | `{question, iso3, year}` → `{answer, facts[], citations[], used_llm, fallback_reason}` |

Contraintes : bind `127.0.0.1`, CORS limité au dev Vite, paramètres validés (ISO3 allowlist, année entière), aucune écriture disque, aucun accès réseau, aucun SQL libre.

---

## 6. Phases (suite complète de tests après chaque phase ; arrêt et rapport)

### Phase 0 — Environnement, données, PLAN
1. Valider `PLAN.md`.
2. Baseline : `pytest tests -q` (attendu 575 pass / 1 échec env. `langchain_google_genai`).
3. **Rebuild** : `python main.py run --from quality --no-llm` ; vérifier quality PASS et `digital_payment = 23.68`.
4. Ajouter/installer `fastapi`, `uvicorn` ; vérifier import.
5. Créer `REQUEST_CATALOG.md`.

**Critère de sortie** : warehouse cohérent, baseline reproductible, dépendances prêtes.

### Phase 1 — Spec + warehouse_reader + DashboardSpecAgent
1. `tools/dashboard_spec.py` (modèles + validation).
2. `tools/warehouse_reader.py` (interface unique, read-only, latest-available explicite).
3. `DashboardSpecAgent` : spec 7 pages, chips, notices, historique `outputs/dashboard/history/<run_id>.json`, diff avec le run précédent.
4. Tests `test_dashboard_spec.py`, `test_warehouse_reader.py`.

**Critère de sortie** : spec complète générée sur TUN 2024, valeurs identiques au warehouse, To load corrects, tests verts.

### Phase 2 — AnalystAgent
1. Faits déterministes par page (Overview, Inégalités, Accès, Exclusion, Pauvreté).
2. Auto-insight + carte « Evidence → Interpretation → Recommendation » (chaque phrase cite un id de fait, mention « association, pas causalité »).
3. Ask : routeur d'intentions fermé → faits → texte template, puis LLM optionnel avec **contrôle strict des nombres** (tout nombre absent des faits ⇒ template).
4. Tests `test_analyst.py` (LLM interdit/mocké, aucune substitution).

**Critère de sortie** : aucun chiffre non issu des faits, fallback sans LLM reproductible.

### Phase 3 — `route2_graph.py`
1. `run_route2()` : semantic (dataset partagé) → Analyst ∥ Dashboard → artefacts.
2. Parité LangGraph / séquentiel, LLM forcé off pour les nombres, erreurs sans reprise.
3. Tests `test_route2_graph.py`.

**Critère de sortie** : deux branches exécutées une fois, artefacts complets, parité vérifiée.

### Phase 4 — FastAPI + React
1. API + `tests/test_api.py`.
2. `dashboard_app/web` : thème Finova, 7 pages, top bar, chip de provenance, pilules « Why? » (bottom sheet), dumbbell/gap SVG, heatmap « To load », simulateur de frais (front uniquement), chat docké.
3. `npm install` / `npm run build`, proxy `/api`, vérification navigateur desktop + tablette.
4. Section README.

**Critère de sortie** : 7 pages navigables, données réelles, build TS strict sans erreur, API sans réseau.

### Phase 5 — QA acceptance
1. Rejouer la liste d'acceptation (Tunisia 2024) page par page.
2. Vérifier : année réellement utilisée, `unavailable`/To load, provisoire signalé, `fin24aP` averti, peer bars, +6,54 pp, +19 %, gap 23,0 pp / 16,4 pp.
3. Responsive, absence de débordement, suite complète verte (hors échec env. connu).

**Critère de sortie** : rapport QA + captures, écarts documentés.

---

## 7. Stratégie de tests

- Aucun réseau ; LLM interdit ou mocké (`build_agent_llm` patché).
- Warehouse de test : fixtures existantes (`tests/test_kpi.py`) ou DuckDB temporaire créé en fixture.
- API : `fastapi.testclient.TestClient` avec chemins temporaires.
- Chaque nouveau module a ses tests ; les tests existants ne sont pas modifiés.
- Vérifications clés : non-substitution d'année, `null` ≠ 0, unités pp, provenance obligatoire, read-only DuckDB.

---

## 8. Risques et mitigations

| # | Risque | Mitigation |
|---|---|---|
| R1 | Collisions `dashboard.py` / `analysis.py` / `test_dashboard.py` | Approche additive + nouveau fichier de test (§1.1), accord requis |
| R2 | Colonne large `digital_payment` obsolète (11,90) | Rebuild phase 0 ; l'UI n'utilise que le KPI semantic |
| R3 | Libellé `fin24aP` erroné dans le dictionnaire | Badge de revue, dictionnaire non modifié |
| R4 | Séries manquantes (dépôts JOR/MAR, crédits % PIB, barrières) | `latest_available` explicite + To load, jamais 0 |
| R5 | Providers LLM absents | Fallback template déterministe, tests sans LLM |
| R6 | Valeurs de référence non sourcées | YAML avec source/année/caveat, validation utilisateur |
| R7 | Installations `fastapi`/`npm` indisponibles | Vérification en phase 0, repli documenté |
| R8 | Fidélité Figma non vérifiable ici | Respect strict des tokens/structure fournis + revue captures |
| R9 | Verrous Windows (history/export) | Écritures atomiques + retries, comme `export_dashboard_json` |
| R10 | Latence de provenance (re-hash par requête) | Spec précalculée + cache process dans l'API |
| R11 | Login sans authentification | UI seule, bind local, mention explicite README |
| R12 | Régression Route 1/Route 2 | Interdits respectés, suite complète après chaque phase |

---

## 9. Mapping acceptance (Tunisia 2024)

| Exigence | Source | Vérifié |
|---|---|---|
| Compte 37,84 % | semantic `account_ownership` | oui |
| +1,0 pt vs 2021 ; 36,91 % en 2017 | semantic `compare_years` / série | oui (0,99 pt) |
| Paiement numérique 23,68 % | semantic `digital_payment_rate` | oui |
| Agences 22,37 /100k | semantic `branch_density` | oui |
| ATM 35,44 (+19 % vs 2017) | warehouse `country_year.atm_per_100k` | oui |
| Genre 26,6 / 49,6 = 23,0 pp (2021 : 16,4) | warehouse `fact` gender + `gender_gap_pp` | oui |
| Pairs 35,3 / 43,1 / 46,5 / 44,4 | warehouse `country_year` | oui |
| MAR − TUN +6,54 pp | semantic `compare_countries` | oui |

---

## 10. Questions ouvertes (à trancher avant phase 4)

1. **Fichiers existants** : valides-tu l'approche additive et `tests/test_dashboard_spec.py` ?
2. **Épargne/emprunt formel vs informel** : OK pour deux barres non dérivées (pas de « informel » calculé) ?
3. **Valeurs de référence** : fournis-tu SMIG (montant/année), seuil de pauvreté INS 2021, FX, benchmarks Arab LMIC/LMIC/World, étude UNDP/OIF — ou dois-je les rechercher et les sourcer ?
4. **Port API** : `127.0.0.1:8000` par défaut, Vite sur `5173` avec proxy `/api` — OK ?

---

**Prochaine action attendue : ton approbation (ou corrections) sur ce PLAN. Aucun code ne sera écrit avant.**

---

## 11. Correctif — portée pays des références statiques (2026-10-29)

- **Statut** : approuvé et implémenté le 2026-10-30 — voir le résultat en fin de section 12.
- **Motif** : sur la vue générée `JOR 2024`, quatre références propres à la Tunisie
  apparaissent hors de la page Pauvreté (elle-même correctement indisponible) :
  - Vue d'ensemble → bloc « Contexte macro » : `fx_tnd_usd_2024` (3,107 TND/USD)
    et `smig_2025` (448,24 TND/mois) ;
  - Pourquoi l'exclusion ? → bloc « Contexte vérifié » : `poverty_rate_urban_2021`
    (12,7 %) et `poverty_rate_rural_2021` (24,8 %), source INS ENBCNV 2021.
  Les valeurs sont exactes mais concernent la Tunisie, pas le pays sélectionné : elles ne
  doivent jamais apparaître sur une portée non tunisienne.

### Changements prévus

1. `src/biflow/tools/dashboard_spec.py` (fichier non interdit ; aucun module Route 1/Route 2
   ni `config/kpi_catalog.v1.yaml` n'est touché) :
   - Vue d'ensemble : n'ajouter `fx_tnd_usd_2024` et `smig_2025` au bloc macro que si
     `iso3 == "TUN"` (même condition que la page Pauvreté) ; les autres pays gardent le
     PIB par habitant.
   - Exclusion : n'ajouter les deux cartes pauvreté INS que si `iso3 == "TUN"` ; les cadres
     UNDP/OIF restent affichés (valeur nulle → « indisponible », jamais 0), sous-titre adapté
     hors Tunisie (« cadres analytiques, pas une mesure d'exclusion »).
   - Contrat généré : hors `TUN`, retirer les quatre faits `*-REF-*` tunisiens de la liste
     `facts` afin qu'aucun consommateur (Ask Finova inclus) ne puisse les citer.
   - La vue publiée Tunisie 2024 ne change pas.
2. `dashboard_app/web/src/pages.tsx` : afficher `page.unavailable_reason` sous le message
   générique quand il existe, pour expliquer la portée pays au lieu de laisser seule la
   phrase « Page momentanément indisponible ».
3. Tests : nouveau `tests/test_dashboard_spec_scope.py` (aucun réseau, aucun écrit dans `data/`) :
   - `JOR` : bloc macro sans FX/SMIG, bloc exclusion sans pauvreté INS, `facts` sans `REF-`,
     page Pauvreté indisponible avec motif ;
   - `TUN` : ces quatre éléments toujours présents (non-régression du contrat publié).
   Tests existants inchangés et verts.
4. Vérification : `pytest` ciblé, reconstruction UI (`npm run build`), captures `JOR 2024`
   (Vue d'ensemble, Exclusion, Pauvreté) et `TUN 2024` inchangée, en-tête API
   `X-Finova-Source` contrôlé.

**Prochaine action attendue : approbation de cette section 11 avant toute modification.**

---

## 12. Correctif — années sans enquête Findex et lenteur des vues générées (2026-10-30)

- **Statut** : approuvé et implémenté le 2026-10-30 — voir le résultat en fin de section 12.
- **Constat mesuré** (hors serveur, sur la base réelle) :
  - L'enquête Findex est menée par **vagues** : 2011, 2014, 2017, 2021, 2024
    (Tunisie : 2014 → 2024 ; Maroc : 2017 → 2024). Les autres années ne contiennent
    que les indicateurs bancaires annuels (FMI FAS) et le PIB.
  - Sur une année sans vague, la génération **plante** : `ValidationError`
    « chart account_ownership_groups lacks data for kind dumbbell » → l'API renvoie une
    erreur 500 et l'UI affiche « Tableau de bord indisponible ». Reproduit pour
    `TUN 2022` (échec après 36,5 s) et `MAR 2011` (échec après 31,8 s).
  - Une année avec vague fonctionne : `TUN 2021` généré en **34,8 s**, six pages
    disponibles. Seule `TUN 2024` est servie instantanément (fichier publié).
  - Le sélecteur d'années propose 2011–2024 pour tous les pays, sans distinguer les
    années d'enquête : d'où l'impression que « seule une année a des données ».

### Changements prévus

1. `src/biflow/tools/dashboard_spec.py` :
   - avant validation, retirer les graphiques sans aucune donnée exploitable
     (dumbbell, funnel, gap, heatmap, bar, line) au lieu de produire un contrat invalide ;
   - si une page ne conserve ni métrique ni graphique exploitable, la marquer
     `available=False` avec un motif explicite :
     « Aucune enquête Findex pour 2022 : l'enquête est menée par vagues (2011, 2014,
     2017, 2021, 2024). »
   - Vue d'ensemble : reste disponible (PIB et pairs) avec une notice « année hors
     enquête » ; Accès et crédit reste disponible si FAS existe ; pipeline inchangé.
2. `dashboard_app/api/app.py` : capturer `ValidationError` dans `generated()` et répondre
   503 avec un message lisible (jamais le détail Pydantic brut).
3. Contrat : ajouter `survey_years` (années réellement observées par Findex pour le pays),
   calculé par l'API pour la vue publiée comme pour les vues générées (champ additif).
4. UI (`dashboard_app/web/src/`) :
   - sous le sélecteur : « Années d'enquête Findex : 2014, 2017, 2021, 2024 » ;
   - bandeau « Année hors enquête » avec renvoi vers les indicateurs bancaires ;
   - message de chargement « peut prendre jusqu'à une minute » ;
   - afficher `page.unavailable_reason` (repris de la section 11).
5. Tests : nouveau `tests/test_dashboard_spec_scope.py`, entrepôt synthétique, sans réseau :
   - `TUN 2022` sans Findex : contrat valide, pages inclusion/exclusion indisponibles avec
     motif, accès disponible, `survey_years` exact ;
   - `TUN 2021` : pages disponibles ; `MAR 2011` : pas de 500 ;
   - `JOR 2024` : absence des références tunisiennes (section 11) ;
   - tests existants inchangés et verts.
6. Vérification : `pytest` ciblé puis suite complète, `npm run build`, captures
   `TUN 2022`, `JOR 2011`, `TUN 2024`, en-têtes API contrôlés.

**Statut : implémenté et vérifié le 2026-10-30** (sections 11 et 12 approuvées).

### Résultat de la mise en œuvre

- `dashboard_spec.py` : `_chart_buildable()` retire les graphiques vides ; une année sans
  vague Findex (aucune observation `source = findex` disponible) marque
  inclusion/exclusion `available=False` avec le motif « vagues » ; la vue d'ensemble
  reçoit une notice `survey_absent`. Les références tunisiennes (SMIG, FX, INS 2021) sont
  limitées à `iso3 == "TUN"` ; le titre réseau physique et l'écart pairs suivent le pays
  sélectionné.
- `analyst.py` : le constat « Détention d'un compte en … » commence par le pays
  sélectionné (même ordre pour la Tunisie, donc tests existants inchangés).
- `app.py` : `survey_years` calculé depuis le warehouse (`fact`, `source='findex'`,
  cache par pays + empreinte de la base) et ajouté à toute réponse ; `ValidationError`
  → 503 avec message lisible.
- UI : bandeau « Années d'enquête Findex », motif d'indisponibilité affiché, libellés
  pays neutres (sous-titre pauvreté, note pairs), message de chargement ≤ 1 min.
- Vérifications : suite complète **620 passed, 1 échec d'environnement préexistant**
  (`test_llm.py::test_build_agent_llm_skips_wrong_key_format`, paquet
  `langchain_google_genai` absent) ; sous-ensemble affecté **108 passed** ; `npm run build`
  OK ; API : `TUN 2022` et `JOR 2024` répondent 200 (avant : 404/500), `survey_years`
  exact ; UI vérifiée dans Chrome pour TUN 2022, TUN 2024 et JOR 2024.

## 13. Correctif — lenteur et écran vide des vues générées (2026-10-30)

- **Statut** : implémenté le 2026-10-30, en attente de la vérification finale.
- **Constat mesuré** : une vue générée coûtait **132 s** dans `AnalysisService.build`
  (5 pays × 6 KPI × toutes les années, trends/classements/comparaisons recalculés alors
  que le contrat n'utilise que les séries du pays choisi). L'UI n'affichait qu'un
  squelette discret puis un bandeau sans progression : impression de page vide.
  La page « Pauvreté » d'un pays hors Tunisie est, elle, indisponible **par conception**
  (références INS/SMIG tunisiennes uniquement).

### Changements

1. `src/biflow/tools/analysis.py` : options additives `series_iso3`,
   `include_trends`, `include_rankings`, `include_comparisons` (défauts inchangés pour
   tous les appelants existants).
2. `dashboard_app/api/app.py` :
   - la génération API ne demande que les séries du pays sélectionné et désactive les
     sections inutilisées ;
   - instances `AnalysisService` réutilisées entre requêtes (cache KPI partagé), cache
     pipeline/référence par empreinte du warehouse ;
   - cache disque `outputs/dashboard/generated/{ISO3}_{année}_{empreinte}.json`
     (écriture atomique) : une vue déjà générée est servie instantanément, même après
     redémarrage ;
   - préchauffage optionnel (`FINOVA_PREWARM=1`) des scopes 2024, 2021 et 2017 pour les
     cinq pays de démonstration, en tâche de fond.
3. UI : écran de chargement explicite (spinner + secondes écoulées + explication),
   bannière de changement de scope, libellé neutre « Page non disponible pour cette
   sélection ».
4. Tests : nouveau `tests/test_analysis_scope_options.py` (sections désactivées, séries
   limitées au pays, validation de `series_iso3`).

### Résultat de la mise en œuvre

- Génération hors serveur : `MAR 2024` **35,4 s** (avant ≈ 140 s), `DZA 2024` 31,5 s,
  `MAR 2021` 19,8 s (cache KPI partagé).
- Préchargement : 18 scopes écrits dans `outputs/dashboard/generated/` (2024, 2021,
  2017 pour les cinq pays, plus quelques années complémentaires). Après redémarrage du
  serveur, une vue préchargée répond en **70 à 160 ms** (`TUN 2021`, `EGY 2024`,
  `MAR 2015`) et `Ask Finova` en **41 ms**.
- Serveur relancé avec `FINOVA_PREWARM=1` ; le front buildé référence bien
  `index-a9WYCE7T.js`.
- Vérifications navigateur : `TUN 2024` (fichier publié) puis bascule `MAR 2024`
  instantanée ; `MAR 2015` (non préchargé) affiche le bandeau « Préparation des chiffres
  pour Maroc 2015… (0 s) » puis la page complète ; la page Pauvreté affiche désormais
  « Page non disponible pour cette sélection » avec le motif INS/SMIG propre à la
  Tunisie.
- Tests ciblés : `test_analysis_scope_options`, `test_dashboard_spec_scope`,
  `test_dashboard_api`, `test_analysis_graph::test_full_route_writes_every_artifact` →
  **20 tests distincts verts** (les nouvelles options sont exclues du dump
  `analysis_request` pour préserver le contrat existant).
- Suite complète : **624 passed, 1 failed en 45 min**. L'unique échec est
  l'environnement préexistant `test_llm.py::test_build_agent_llm_skips_wrong_key_format`
  (paquet `langchain_google_genai` absent), sans lien avec ces changements.


