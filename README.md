# BIFlow — Automatisation d'un pipeline BI multi-agents

Pipeline Business Intelligence automatique en deux routes :

- **Route 1 — Données** : données brutes → snapshot → profilage → qualité → ETL
  → KPI → audit, orchestré par LangGraph ; les agents LLM (Gemini, Groq) restent
  optionnels et ne calculent aucun chiffre.
- **Route 2 — Analyse** : warehouse → Semantic & KPI → **BI Analyst** →
  **dashboard FinOVA** (`dashboard_app/`), entièrement déterministe (aucun LLM,
  aucun recalcul, aucune interpolation).

Domaine : **Économie & Finance / inclusion financière**.

> **Nouvelle installation** : suivre « Démarrage » (prérequis, fichiers à obtenir
> séparément, commandes dans l'ordre), puis `.\start.ps1`.

Sources de données :

| Source | Rôle | Fichier |
|---|---|---|
| World Bank **Global Findex** | demande / usage des services financiers | `data/raw/findex.csv` |
| IMF **Financial Access Survey (FAS)** | offre (agences, ATM, dépôts, crédits) | `data/raw/fas.csv` |
| World Bank **WDI** (PIB) | contexte macroéconomique | `data/raw/gdp.csv` |

## État d'avancement

- [x] **P0 — Socle** : configuration, package `biflow`, couche LLM multi-provider,
      vérification des clés.
- [x] **P1 — Données** : collector, profiler, quality gate, ETL (nœuds LangGraph).
- [x] **P2 — Semantic & KPI** : couche KPI déterministe (44 KPI du catalogue
      1.6.0, 6 actions, provenance et revue) et étape `semantic_kpi` après l'ETL
      (table `kpi_values`). Le catalogue 1.4.0 reprend les séries de
      `REQUEST_CATALOG.md` : 7 séries FAS (ATM, déposants, emprunteurs, comptes,
      encours en % du PIB), 5 séries Findex (fonds d'urgence et leurs sources,
      mobile money, comptes inactifs) et la détention de compte par sous-groupe
      (un KPI par groupe : genre, revenu, âge, éducation, activité, milieu).
      Le catalogue 1.5.0 ajoute les six raisons de ne pas avoir de compte
      bancaire (`fin11a`–`fin11f`, part de tous les adultes 15+, vague 2024).
      Le catalogue 1.6.0 ajoute les écarts `education_gap`, `laborforce_gap` et
      `urban_gap` (même contrat que `gender_gap` : différence de deux sous-groupes
      de la même année).
- [x] **P3 — Route 2** : BI Analyst déterministe, contrat dashboard et front
      React/ECharts.
- [x] **Audit / XAI** : étape `auditor` (vérification indépendante, publication,
      explications, rapport d'audit, contrat d'audit des insights).
- [x] **Sources utilisateur** : `add-source` (CSV de structure libre, mapping
      confirmé, gate qualité propre).

La Route 1 n'est pas modifiée par la Route 2 : graphe, agents et CLI existants
conservent leur comportement.

## Architecture

```
main.py / scripts/check_llm.py / scripts/evaluate_auditor.py
src/biflow/
  config.py        configuration YAML + chemins
  llm.py           providers, fallback, cache, compteur de tokens
  state.py         etat partage du pipeline
  graph.py         graphe LangGraph Route 1 + repli sequentiel
  semantic_graph.py  route semantique a la demande (une requete KPI)
  analysis_graph.py graphe Route 2 (BI Analyst -> Dashboard)
  agents/          base, collector, snapshot, profiler, quality, etl, semantic_kpi, auditor
                   + bi_analyst, analyst, dashboard (Route 2)
  tools/           dictionnaire d'indicateurs, kpi, semantic_kpi, kpi_values, snapshots,
                   audit_checks, audit_explain, audit_text, audit_report, insights,
                   user_sources ; analysis, dashboard_contract, dashboard_spec (Route 2)
  utils/           io, logger, pays (ISO3)
config/config.yaml     chemins, LLM, orchestrateur, KPI, sources, seuils, analyst, dashboard
config/kpi_catalog.v1.yaml  definitions declaratives des KPI (version 1.7.0, libelles francais name_fr)
data/                  raw, snapshots, staging, processed, profiles, quality, audit
dashboard_app/         dashboard FinOVA : API FastAPI (api/) + front React/Vite (web/)
legacy/dashboard/      ancien front React/ECharts, retire du service (remplace par FinOVA)
outputs/               reports, profiles, logs, cache LLM
```

## Pipeline (S06 → S12)

| Etape | Agent | Sorties principales |
|---|---|---|
| S06 | `collector` | `data/raw/*.csv` + SHA-256, telechargement WDI pagine (FAS via API en option) |
| S07 | `snapshot` | `data/snapshots/` : nouvelle version `vN` si le contenu change, sinon `no_change` |
| S08 | `profiler` | `outputs/profiles/profile_*.{json,md}`, couverture indicateurs |
| S09 | `quality` | `data/quality/quality_report.{json,md}` (run_id, snapshot_id, SHA-256 des sources), gate PASS/FAIL |
| S10 | `etl` | `data/processed/*.parquet`, `warehouse.duckdb`, `lineage.json` |
| S11 | `semantic_kpi` | table DuckDB `kpi_values` + `data/processed/kpi_values.parquet` |
| S12 | `auditor` | verdict d'audit, `kpi_values.publication_status`, `kpi_explanations`, `data/audit/` |

Chaque execution ecrit un rapport dans `outputs/reports/<run_id>/` ; `run.json`
liste aussi chaque tentative d'agent (`attempts`).

- **Quality gate** : un FAIL arrête le pipeline avant l'ETL (et donc les KPI).
  C'est une décision, jamais retentée.
- **Retry** : un agent en erreur est relancé `orchestrator.max_retries` fois
  (1 par défaut) après `retry_backoff_s × n` secondes. Au dernier échec, le
  pipeline s'arrête, les sorties publiées précédemment restent en place et
  chaque tentative est tracée dans `run.json` et `errors`.

### Snapshots des sources brutes (`snapshot`)

Le collector réécrit `data/raw/*.csv` et l'ETL remplace ses tables : l'historique
est conservé dans `data/snapshots/` :

```
data/snapshots/
  index.json              versions, statut, version publiée
  blobs/<sha256>.csv      chaque fichier brut stocké une seule fois (copie exacte)
  vN/manifest.json        created_at, run_id, content_key ; par source : blob,
                          sha256, content_sha256, rows, size_bytes, original_path
```

- L'empreinte de contenu ignore l'ordre des lignes (BOM et fins de ligne
  normalisés). Si elle est identique à la version publiée, le run se termine en
  `no_change` après le snapshot : profil, qualité, ETL et KPI ne sont pas relancés
  et aucun artefact publié n'est réécrit.
- Sinon une version `vN` est créée (`pending`) puis publiée seulement après
  l'Auditor et si l'audit n'a aucun échec. En cas d'échec d'un agent, de quality
  gate FAIL, d'audit en échec (`audit_failed`) ou de run partiel (`--to
  semantic_kpi`), elle passe `not_published` et la version publiée reste en place.
- `--rebuild` rejoue `snapshot → auditor` sur les blobs de la version publiée
  (nouveau `run_id`, pas de collecte) ; chaque audit est consigné dans
  `index.json` (`audits` : `run_id`, `verdict`, `created_at`). Un audit en échec
  marque l'entrée `audit_failed` sans déplacer le pointeur `published`.
- Les blobs référencés par une version de `index.json` sont conservés, les autres
  supprimés. `snapshot_id` est enregistré dans l'état, `run.json`, `lineage.json`,
  `quality_report.json` et `kpi_values`.

### FAS via IMF Data API (optionnel)

`sources.fas.api.enabled: false` par défaut : `fas.csv` statique reste la source.
Activé, le collector interroge l'API SDMX 3.0
(`https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/FAS/~/{pays}.{clé}`,
`Accept: text/csv`) pour chaque série de `sources.fas.api.series`, convertit la
réponse (une ligne par observation) au format large de `fas.csv` sans toucher aux
valeurs, et écrit `data/raw/fas_api.csv`, qui remplace alors `fas.csv` pour ce run.
Une échelle autre que `0` (unités) ou une fréquence non annuelle est refusée.
Si l'API est injoignable, le fichier déjà collecté est conservé (le snapshot
publié reste donc valide).

L'API sert FAS 8.0.0 : les codes diffèrent de l'export local FAS 5.0.0. Seules
deux séries sont mappées, vérifiées le 2026-10-29 (valeurs TUN 2019-2023
identiques à `fas.csv`) : `FA26N.PHTADLT_NUM` → `FA26._Z._Z._T.PHTADLT_NUM.A` et
`FA18N.PHTADLT_NUM` → `FA18._Z._Z._T.PHTADLT_NUM.A`. Les autres séries (déposants,
emprunteurs, comptes, % du PIB) ont plusieurs ventilations possibles en 8.0.0 et
restent non mappées : avec l'API activée, elles manquent et le collector le signale.

### Étape KPI (`semantic_kpi`)

En mode pipeline, l'agent calcule chaque KPI du catalogue pour `kpi.focus` et
`kpi.peers`, sur chaque année valide du catalogue, via `SemanticKpiTools`
(lecture seule des faits, aucun LLM). Table `kpi_values` :

| Colonne | Contenu |
|---|---|
| `kpi_id`, `iso3`, `year` | clé (`iso3 = 'PEERS'` pour la moyenne des pairs) |
| `value`, `unit` | valeur calculée ; `NULL` si indisponible (jamais 0) |
| `availability_status`, `reason` | `available` / `unavailable` / `requires_review` |
| `definition_status` | `verified`, `verified_metadata`, `derived_verified`, `provisional` |
| `requires_review`, `review_reasons` | provenance, définition provisoire, alertes qualité |
| `peer_status`, `peers_included`, `missing_peers`, `aggregation_method` | lignes PEERS : `complete` / `partial` / `none` |
| `catalog_version`, `catalog_sha256`, `run_id` | traçabilité |

La ligne `PEERS` est une moyenne **simple, non pondérée** des pairs disponibles
(`aggregation_method = simple_mean_4_peers` avec 4 pairs). Elle n'est marquée
pour revue que si un pair manque (`partial_peer_coverage`, ou
`no_peer_observation` si aucun pair n'a de valeur) ; les raisons de revue des
pairs inclus sont héritées.

KPI du catalogue 1.2.0 : `account_ownership`, `branch_density`,
`digital_payment_rate`, `saving_rate` et `borrowing_rate` (mesures « any »,
glossaire lignes 121 et 3), `unbanked_share`, `formal_saving_rate` (`fin17a`),
`formal_borrowing_rate` (`fin22a`, carte de crédit incluse), `gender_gap`,
`income_gap`, `age_gap` (points de pourcentage, mêmes pays et année).

### BI Auditor / XAI (`auditor`)

Agent déterministe exécuté après `semantic_kpi`. Il n'utilise pas le code de
calcul des KPI (test d'imports) : il relit le catalogue, interprète les formules
par liste blanche et interroge `fact` en lecture seule.

| Contrôles | Contenu | Effet |
|---|---|---|
| A1-A5 recalcul | chaque valeur recalculée depuis `fact` (tolérance `1e-9`), NULL réels (pas de zéro caché), moyennes PEERS, complétude, fait = fichier brut du snapshot selon la transformation déclarée | échec |
| B1-B2 unités | une unité par KPI ; percent [0,100], points [-100,100], densités >= 0 | échec |
| B3-B4 entités | aucun agrégat ni code non-pays hors PEERS ; PEERS = pairs configurés | échec |
| B5-B7 traçabilité | même `snapshot_id` / `run_id` dans l'index, le lineage, le rapport qualité et `kpi_values` ; SHA-256 des sources = noms et contenu des blobs ; empreinte du contenu du warehouse recalculée | échec |
| B8-B9 catalogue, qualité | aucune définition provisoire ni code non vérifié, preuves présentes, catalogue identique ; quality gate PASS | échec |
| C1-C4 avertissements | vague 2022 partielle, pairs partiels, diagnostic qualité sur une entrée, variation d'une vague sous `auditor.min_meaningful_change_pp` (« dans le bruit d'enquête » : ~1 000 entretiens par pays, aucune erreur type dans le fichier) | avertissement |
| F1 insights | claims et nombres des insights de l'Analyst | avertissement |

Publication par ligne (`kpi_values.publication_status`) : `blocked` si un échec
touche la ligne (ou tout le run, ou un pair inclus d'une ligne PEERS),
`approved_with_review_note` si seulement des avertissements ou des raisons de
revue, `approved` sinon (un NULL réel est publié comme « indisponible »).
C4 est informatif et ne change pas le statut.

Explications : une par ligne (table `kpi_explanations`,
`data/audit/explanations.jsonl`) avec fichier et SHA-256 de la source, clé et
valeur brute, transformation, formule et version du catalogue, dépendances
(sous-groupes d'un écart, détention de compte pour `unbanked_share`, chaque pair
pour PEERS), constats qualité, raisons de revue, statut, et phrases FR/EN issues
de gabarits. Seuls les 3 exemples du rapport peuvent être reformulés par LLM
(`llm.routing.auditor`) : chaque nombre de la réponse doit figurer avec le même
arrondi dans le gabarit, sinon le gabarit est conservé. Avec `--no-llm`, seuls
les gabarits sont utilisés.

Insights (contrat de l'agent Analyst, `biflow.tools.insights.Insight`) :
`{insight_id, text, claims: [{kpi_id, iso3, year, value, unit}], recommendation,
confidence}`. Chaque claim doit correspondre à une ligne approuvée de
`kpi_values` (même arrondi, unité, année) ; chaque nombre du texte doit être la
valeur ou l'année d'un claim, ou l'écart entre deux claims du même KPI (deux
années d'un pays ou deux pays d'une année). Sinon l'insight est rejeté avec sa
raison. L'Auditor lit ces insights dans la clé d'état `audit_insights` (la clé
`insights` reste celle du FinOVA Analyst). Après l'analyste, la Route 2 convertit
ses insights en claims (seuls les faits du catalogue KPI deviennent des claims) et
consigne les comptes acceptés / rejetés dans `data/audit/audit_report.{json,md}`
(section « Insights de la Route 2 »), sans changement d'interface.

### Clés de configuration

| Clé | Défaut | Rôle |
|---|---|---|
| `kpi.focus` | `TUN` | pays focus de l'étape KPI |
| `kpi.peers` | `[DZA, EGY, JOR, MAR]` | groupe de pairs (ligne `PEERS`) |
| `orchestrator.max_retries` | `1` | nouveaux essais d'un agent en erreur |
| `orchestrator.retry_backoff_s` | `1.0` | attente avant l'essai n (`n × backoff`) |
| `snapshots.enabled` | `true` | versionnement des sources brutes |
| `snapshots.root` | `data/snapshots` | `index.json`, `blobs/`, `vN/manifest.json` |
| `sources.fas.api.enabled` | `false` | collecte FAS via l'API IMF au lieu de `fas.csv` |
| `sources.fas.api.series` | 2 séries vérifiées | série locale → clé SDMX (sans le pays) |
| `sources.fas.api.path` | `data/raw/fas_api.csv` | sortie de la collecte API |
| `sources.gdp.indicators` | `NY.GDP.MKTP.CD`, `NY.GDP.PCAP.CD`, `NY.GDP.MKTP.KD.ZG` | indicateurs WDI collectés |
| `auditor.tolerance` | `1.0e-9` | écart maximal valeur publiée / recalculée |
| `auditor.min_meaningful_change_pp` | `2.0` | seuil « dans le bruit d'enquête » (points) |
| `auditor.llm_examples` | `3` | exemples du rapport reformulables par LLM |
| `llm.routing.auditor` | `[groq, gemini]` | reformulation seulement, vérifiée |
| `paths.audit` | `data/audit` | rapport d'audit, explications, évaluation |
| `uploads.dir` | `data/uploads` | copies des fichiers utilisateur |
| `uploads.mappings_dir` | `config/sources` | mappings confirmés, chargés automatiquement |
| `uploads.max_file_mb` | `200` | taille maximale d'un fichier ajouté |
| `countries.name_to_iso3` | `{}` | alias de noms de pays (correspondance exacte) |
| `llm.routing.mapper` | `[groq, gemini]` | suggestion des rôles de colonnes, revalidée |

## Ajouter vos propres données

Vous pouvez ajouter vos propres fichiers **CSV**, même si leur structure diffère
de Findex, FAS ou WDI. Les sources officielles ne sont jamais modifiées : le
fichier est copié dans `data/uploads/<nom>.csv` et son mapping confirmé est
enregistré dans `config/sources/<nom>.yaml` (deux dossiers ignorés par git).
Au `python main.py run` suivant, la source est versionnée (nouveau snapshot),
profilée, contrôlée par son **propre** quality gate, chargée par l'ETL
(`source = user:<nom>`, codes `<nom>.<indicateur>`) et vérifiée par l'Auditor.
Si elle échoue au contrôle qualité, elle est **exclue** avec un avertissement
(source, raison, score dans `run.json`, le rapport qualité et le journal du
rapport d'audit) et le pipeline officiel continue et publie.

```bash
python main.py add-source --file mon_fichier.csv --name ma_source --dry-run   # rapport seul
python main.py add-source --file mon_fichier.csv --name ma_source             # interactif
python main.py add-source --file mon_fichier.csv --name ma_source --mapping mapping.yaml  # non interactif
python main.py add-source --file mon_fichier.csv --name ma_source --yes --draft brouillon.yaml
python main.py remove-source --name ma_source    # retire le mapping (la copie est conservée)
```

**Détection** (déterministe) : encodage vérifié sur tout le fichier, séparateur
(`;` `,` tabulation `|`), ligne d'en-tête (un titre au-dessus est ignoré),
virgule décimale, milliers en groupes de 3 (`1 234,5`), et disposition :

| Disposition | Exemple d'en-tête |
|---|---|
| `long` (une ligne par observation) | `Pays;Année;Indicateur;Valeur` |
| `wide_by_year` (colonnes années) | `iso3,indicator,2021,2022,2023` |
| `wide_by_indicator` (une colonne par indicateur) | `country,year,bank_agents,atm_count` |

**Mapping proposé** : règles d'abord (synonymes FR/EN/arabe : pays, country,
codewb, balad ; année, year, sana ; valeur, value, qima...), puis, si un rôle
reste indéterminé, suggestion LLM optionnelle (`llm.routing.mapper`) limitée aux
rôles de colonnes et toujours revalidée. **L'unité n'est jamais devinée** : elle
est demandée pour chaque indicateur. Pays : codes ISO3 ou noms (anglais,
français, arabe, alias `countries.name_to_iso3` ou confirmés dans le mapping),
correspondance exacte seulement ; un nom inconnu ou un agrégat est listé et
exclu, jamais deviné.

**Dry-run** : % de cellules retenues, pays non reconnus, années, valeurs non
numériques, doublons, aperçu de 10 observations canoniques et résultat du
contrôle qualité de la source. Un mapping confirmé est réutilisé sans question
pour un fichier aux mêmes colonnes (empreinte des en-têtes, ordre et casse
ignorés) ; des colonnes différentes déclenchent une nouvelle confirmation.

**Valeurs** : conservées telles qu'écrites. Seule une conversion déclarée dans
le mapping est appliquée (`transform: percent_to_fraction` ou
`fraction_to_percent`). Limites : `uploads.max_file_mb` (200 Mo), fichiers CSV
texte uniquement, refus d'un fichier sans colonne pays ou année, messages en
français.

### Exemple 1 : format long, point-virgule et virgule décimale

```
Pays;Année;Indicateur;Valeur
Tunisie;2024;Clients microfinance (milliers);1 230,75
Maroc;2024;Clients microfinance (milliers);2 104,0
```

`python main.py add-source --file clients.csv --name microfinance` détecte
`long`, `;`, décimale `,`, reconnaît Tunisie → TUN et Maroc → MAR, puis demande
l'unité (ex. `milliers_clients`). Mapping non interactif équivalent :
[`docs/examples/microfinance_mapping.yaml`](docs/examples/microfinance_mapping.yaml).

### Exemple 2 : colonnes années et codes ISO3

```
iso3,indicator,2021,2022,2023
TUN,mobile_money_users_pct,12.5,14.0,15.2
MAR,mobile_money_users_pct,9.1,,10.3
```

Disposition `wide_by_year` ; la cellule vide reste absente (jamais 0). Si
l'unité déclarée est `percent`, les valeurs restent en pourcentage ; pour les
stocker en fraction, déclarer `transform: percent_to_fraction`.

### Exemple 3 : une colonne par indicateur, noms de pays

```
country,year,bank_agents,atm_count
Tunisia,2023,1200,2100
Atlantis,2023,1,2
```

Disposition `wide_by_indicator` : deux indicateurs (`network.bank_agents`,
`network.atm_count`), une unité demandée pour chacun ; « Atlantis » est listé
comme pays inconnu et exclu.

### Faire d'un indicateur utilisateur un KPI

Un indicateur utilisateur n'est pas un KPI tant qu'une entrée n'est pas ajoutée
au catalogue utilisateur `config/kpi_catalog.user.yaml` (chemin modifiable par la
variable d'environnement `BIFLOW_USER_CATALOG` ; fusionné au chargement ; version et hash du catalogue officiel inchangés, `kpi_values`
enregistre `catalog_sha256` et `user_catalog_sha256`). Contrat : statut
`user_declared`, source `user:<nom>`, formule `value` (aucune mise à l'échelle),
unité = unité déclarée. Ces lignes sont publiées au mieux
`approved_with_review_note` avec la raison `user_provided_source`.

```yaml
catalog_id: biflow_user_kpis
references:
  user_upload_agents: {path: data/uploads/agents.csv, locator: "config/sources/agents.yaml, colonne agents",
                       evidence: "fichier depose, unite declaree count"}
kpis:
  agents_count:
    definition_version: "1.0.0"
    name: Agents bancaires (source utilisateur)
    business_objective: financial_inclusion
    definition: Nombre d'agents bancaires declare par l'utilisateur.
    verification: {status: user_declared, evidence: [user_upload_agents], uncertainties: [Source non verifiee par BIFlow.]}
    source: {dataset: "user:agents", indicator: agents.agents, official_indicator: null}
    warehouse: {fact_table: fact, indicator_code: agents.agents, source: "user:agents", input_unit: count,
                dimension: all, dimension_value: all}
    formula: {from_fact: value}
    unit: count
    denominator: {population: non applicable, basis: user_declared}
    subgroup: total_population
    reference_period: annee declaree
    valid_years: [2023, 2024]
    year_evidence: user_upload_agents
    aggregation: {country_year: unique_observation, over_time: none, subgroup_rollup: none}
    missing_data_policy: preserve_missing_v1
    aggregation_policy: compatible_denominators_v1
    traceability_policy: retain_input_lineage_v1
    publication_review_policy: review_flagged_dependencies_v1
    dependencies: []
```

L'Auditor relit chaque cellule source dans le snapshot selon le mapping (A5) et
compare tous les faits utilisateur aux observations du mapping (A6).

## Mode banquier

Un banquier dépose ses propres indicateurs (niveau pays) et les lit à côté des
chiffres officiels, sans jamais les mélanger : les données officielles ne sont pas
modifiées et chaque valeur utilisateur porte la puce **« Données utilisateur ·
non vérifiée par BIFlow »**. Fichier de démonstration :
`docs/examples/banque_fictive_exemple.csv` (**données fictives**, « exemple
fictif » dans chaque libellé ; Tunisie et Maroc, 2021-2024).

1. **Mes données → « Ajouter un fichier »** : structure détectée, rôles proposés.
2. **Étape 3 « Indicateurs »** : unité obligatoire (jamais devinée), puis, si
   vous le souhaitez, un **indicateur officiel comparable**. La liste ne propose
   que les KPI du catalogue de **même unité** (après conversion) ; le choix affiche
   la définition officielle et le dénominateur, et la case **« Mon indicateur
   mesure la même chose (même population, même définition) »** est obligatoire :
   sans elle, le KPI comparable n'est pas enregistré. Même unité ne veut pas dire
   même définition : c'est vous qui la déclarez. Dans l'exemple : « Distributeurs
   (ATM) du réseau pour 100 000 adultes » → `atm_density`, « Agences pour 100 000
   adultes » → `branch_density`, et un indicateur en % sans comparable.
3. **Vérification, confirmation** : le fichier est copié dans `data/uploads/`, le
   pipeline est recalculé hors ligne (sources officielles reprises du snapshot).
4. **Vue d'ensemble → « Vos indicateurs face aux données officielles »** : bloc
   séparé des cartes officielles. Votre valeur de l'année choisie (sinon la
   dernière année antérieure, année affichée) à côté du KPI officiel approuvé de
   la même année (sinon la dernière vague, année affichée) ; définition
   officielle sous chaque ligne ; « années différentes : comparaison indicative »
   si les années diffèrent ; aucune valeur si les unités ne correspondent plus.
   Note permanente : « Comparaison indicative : définition déclarée par
   l'utilisateur ».
5. **Pistes « à partir de vos données »** (règle `user_vs_official` de
   `config/recommendations.yaml`, 5 pts pour les %, 10 % relatif sinon) : sous-liste
   séparée des pistes officielles, seulement quand votre année est l'année
   officielle utilisée. Jamais écrites dans `docs/deliverables/`.
6. **Ask Finova** : l'outil `get_user_indicator` lit vos données en lecture
   seule ; toute réponse qui les cite commence par « D'après vos données (non
   vérifiées par BIFlow) ». Avec `llm.ask.allow_user_data_to_llm: false` (défaut),
   une question sur vos données reçoit une réponse en mode simple, calculée
   localement, et le panneau explique pourquoi ; aucune valeur utilisateur n'est
   envoyée au LLM (ni outil, ni historique).
7. **PDF** : la case « Inclure l'annexe : vos données » ajoute une section
   séparée « Annexe : vos données » au rapport des constats (valeurs,
   comparaisons, pistes « à partir de vos données »), chaque valeur étiquetée.
8. **Retirer la source** (Mes données → « Supprimer ») : ses lignes quittent
   l'entrepôt au recalcul suivant.

### Limites

- **Connexion de démonstration** : l'écran d'accueil n'authentifie personne ; il
  n'y a ni comptes, ni droits, ni séparation entre utilisateurs. À ne pas exposer
  sur un réseau partagé avec des données réelles.
- **Niveau pays uniquement** : un fichier doit avoir une colonne pays et une
  colonne année. Pas encore de gouvernorat, d'agence ni de client.
- **Données locales** : fichiers, mappings et entrepôt restent sur la machine
  (`data/`, `config/sources/`, ignorés par Git). Exception : si vous activez
  `llm.ask.allow_user_data_to_llm`, les valeurs lues par Ask Finova sont envoyées
  au fournisseur LLM configuré (Groq ou Gemini).
- **Définitions déclarées, pas vérifiées** : BIFlow vérifie l'unité et la
  structure, pas que votre indicateur mesure la même population que le KPI
  officiel ; la comparaison reste indicative.
- **Formats** : CSV texte uniquement (pas d'Excel), une valeur par pays, année et
  indicateur.

## Route 2 — BI Analyst et Dashboard

La Route 2 lit le warehouse en **lecture seule** et passe uniquement par les
contrats sémantiques KPI (`list`, `describe`, `calculate`, `latest_available`,
`compare_countries`, `compare_years`). Elle ne contient ni LLM, ni SQL ad hoc,
ni calcul parallèle.

| Etape | Agent | Sorties |
|---|---|---|
| S10 | `bi_analyst` | `analysis_dataset.json`, `bi_analyst.json`, `bi_analyst.md` |
| S11 | `dashboard` | `dashboard_data.json`, `outputs/dashboard/dashboard.json` |

Le **BI Analyst** produit des constats déterministes (`F-001`, …) rattachés à
des identifiants de preuve (`EV-…`, `TR-…`, `CMP-…`). Le **Dashboard** valide
le contrat (schéma `1.0`) puis l'exporte de façon atomique pour le front.

```powershell
# Rapport BI Analyst seul
python main.py analyze --country TUN,MAR,DZA --mode latest --run-id demo

# Analyste + donnees du dashboard
python main.py dashboard --country TUN,MAR,DZA --kpis account_ownership,saving_rate `
  --mode year --year 2024 --reference TUN --top 5 --run-id demo
```

> Le front historique React/ECharts (`dashboard/`) est **remplacé par FinOVA
> (`dashboard_app`)** : il est conservé dans `legacy/dashboard/` pour mémoire,
> n'est plus construit ni servi, et la Route 1 n'écrit plus dans son dossier
> (`outputs/dashboard/dashboard.json`). Voir « Dashboard Finova » plus bas.

Options : `--country` (répétable ou CSV), `--kpis`, `--mode latest|year`,
`--year`, `--reference`, `--top`, `--no-series`, `--run-id`.

- **Aucune valeur n'est inventée** : une observation absente reste `null` avec
  `availability_status="unavailable"` et un motif ; aucun zéro de remplissage,
  aucune interpolation.
- **Comparaisons** : différence absolue `droite − gauche`, en points de
  pourcentage pour les KPI en `percent`.
- **Revue et publication** : `publication_status="not_evaluated"` est conservé
  de bout en bout ; les motifs `requires_review` restent affichés (badges,
  bandeau, notices, pied de page).
- **Provenance** : SHA-256 du warehouse, lineage, rapport qualité, liaison de
  contenu et écarts de sources sont exposés dans les rapports et l'interface.

## Démarrage

Procédure vérifiée sur un clone neuf de `el-final` (Windows 11, Python 3.10.11,
Node 24) : installation, pipeline, Route 2 et dashboard en une quinzaine de minutes.

### Prérequis

- **Git** ;
- **Python 3.10** : `requirements.lock` a été généré pour Windows / Python 3.10.
  Si plusieurs versions sont installées, créer le venv explicitement avec
  `py -3.10 -m venv .venv` (le lanceur `py` peut choisir une version plus récente
  par défaut). Autre version ou autre système : voir « Installation reproductible »
  plus bas, ou installer `requirements.txt` ;
- **Node.js >= 18** pour le front FinOVA (`npm ci`). Les tests Node du dashboard
  historique (`legacy/`) demandent Node >= 22.6 ; sans lui, ils sont ignorés ;
- **un accès réseau** au premier lancement : le PIB (WDI) est téléchargé
  automatiquement depuis l'API World Bank.

### Fichiers à obtenir séparément (absents de Git)

| Fichier | Obligatoire | Où le mettre | Où l'obtenir |
|---|---|---|---|
| `findex.csv` | **oui** | `data/raw/findex.csv` | World Bank Global Findex 2025, *Download data* : <https://www.worldbank.org/en/publication/globalfindex/download-data> (base au niveau pays, colonnes `countrynewwb, codewb, …, year, group, group2, account_t_d, …, fin11a…fin11f`) |
| `fas.csv` | **oui** | `data/raw/fas.csv` | IMF Financial Access Survey : <https://data.imf.org/Datasets/FAS> (export large `SERIES_CODE` + années, séparateur `;`, deux lignes d'en-tête) |
| `gdp.csv` | non | `data/raw/gdp.csv` | téléchargé tout seul par le Collector (API World Bank, indicateur `NY.GDP.MKTP.CD`) |
| `.env` | non | racine du projet | `Copy-Item .env.example .env`, puis renseigner `GROQ_API_KEY` et/ou `GOOGLE_API_KEY` (clés personnelles, jamais commitées). Sans clé, le pipeline et le dashboard fonctionnent ; seuls le quality gate assisté et Ask Finova en mode IA sont désactivés |
| vidéos de connexion | non | `dashboard_app/web/public/media/login/login-01.mp4` … `login-04.mp4`, **avant** `npm run build` (ou directement dans `dashboard_app/web/dist/media/login/`) | à demander à l'équipe (124 Mo, `*.mp4` ignoré par Git). Sans elles, la page de connexion garde son fond statique |

Les documents de travail de `docs/sources/` (fiches Findex et FAS d'où viennent
ces liens) ne sont pas versionnés non plus. Pour reproduire exactement les
chiffres publiés (`AUDIT_REPORT.md`), utiliser les fichiers de l'équipe ; leurs
empreintes SHA-256 :

```
35f3fa934adf940c3ec20603b64e8ed81b4315ff550bdb08d61968e38fc0bf66  data/raw/findex.csv
f60b4d1b3de68e15b6b29c286b2954942d6d226c86e1f13c42e372965ac5e9b5  data/raw/fas.csv
b746f41a1c591493feca1490d64f937ca00c227e7661b6694779735e79886c17  data/raw/gdp.csv   (téléchargé, 2026-11-04)
```

(`Get-FileHash data\raw\findex.csv` sous PowerShell, `sha256sum` sous Linux.)
Sans `findex.csv` ou `fas.csv`, `main.py run` s'arrête au Collector avec
« source statique introuvable : …\data\raw\<fichier> ».

### Installation et lancement — Windows (PowerShell)

```powershell
# 1. Cloner
git clone --branch el-final <url-du-depot> data-science-project
cd data-science-project

# 2. Environnement Python (pip récent obligatoire : le pip 23 livré avec
#    Python 3.10 refuse le verrou, « all requirements must have their versions pinned »)
py -3.10 -m venv .venv            # ou : python -m venv .venv  si python = 3.10
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install --require-hashes -r requirements.lock

# 3. Clés LLM (optionnelles)
Copy-Item .env.example .env       # puis renseigner GROQ_API_KEY / GOOGLE_API_KEY
.\.venv\Scripts\python scripts/check_llm.py   # sans clé : « Aucun provider operationnel » (attendu)

# 4. Données brutes : déposer findex.csv et fas.csv dans data\raw\ (voir tableau)

# 5. Route 1 : pipeline complet (collector -> ... -> semantic_kpi -> auditor), ~1 min
.\.venv\Scripts\python main.py run
#    attendu : « statut : success », gate=PASS, verdict pass_with_warnings

# 6. Route 2 : contrat publié du dashboard (Tunisie 2024), ~1 min
$env:PYTHONPATH = "src"
.\.venv\Scripts\python -c "from biflow.route2_graph import run_route2; run_route2(use_llm=False)"

# 7. Front FinOVA
cd dashboard_app\web; npm ci; npm run build; cd ..\..

# 8. Dashboard : http://127.0.0.1:8000
.\start.ps1                       # .\stop.ps1 pour l'arrêter
#    si les scripts sont bloqués : powershell -ExecutionPolicy Bypass -File .\start.ps1

# 9. Tests (~11 min)
$env:PYTHONPATH = "src"; .\.venv\Scripts\python -m pytest -q
```

### Installation et lancement — Linux / macOS (bash)

`requirements.lock` est propre à Windows : installer `requirements.txt` (ou
régénérer le verrou, voir « Installation reproductible »). `start.ps1` est un
script Windows : lancer uvicorn directement.

```bash
git clone --branch el-final <url-du-depot> data-science-project && cd data-science-project
python3.10 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env                       # clés optionnelles
# déposer findex.csv et fas.csv dans data/raw/
.venv/bin/python main.py run
PYTHONPATH=src .venv/bin/python -c "from biflow.route2_graph import run_route2; run_route2(use_llm=False)"
(cd dashboard_app/web && npm ci && npm run build)
PYTHONPATH=src .venv/bin/python -m uvicorn dashboard_app.api.app:app --host 127.0.0.1 --port 8000
PYTHONPATH=src .venv/bin/python -m pytest -q
```

### Commandes utiles

```powershell
python main.py steps
python main.py run --only quality
python main.py run --from etl
python main.py run --to etl --no-llm      # s'arrete apres l'ETL, sans KPI
python main.py run --only semantic_kpi    # recalcule kpi_values (sans audit)
python main.py run --rebuild              # rejoue snapshot -> auditor sur la version publiee
python main.py explain --kpi account_ownership --iso3 TUN --year 2024
python main.py explain --kpi gender_gap --iso3 TUN --year 2024 --compare-year 2021 --lang en
python main.py explain --kpi branch_density --iso3 TUN --year 2024 --compare-iso3 PEERS
python main.py add-source --file mon_fichier.csv --name ma_source --dry-run
python scripts/evaluate_auditor.py        # injection de fautes -> data/audit/evaluation.md
python main.py dashboard --country TUN,MAR,DZA --mode latest   # contrat Route 2 historique
```

## Sorties

- `data/raw/` : sources brutes et empreintes SHA-256 ;
- `data/snapshots/` : versions des sources brutes (index, blobs, manifestes) ;
- `outputs/profiles/` : profils JSON/Markdown et diagnostics de couverture ;
- `data/quality/` : rapport qualité JSON/Markdown (`run_id`, `created_at`,
  `inputs.<source>.sha256`), anomalies et gate PASS/FAIL ;
- `data/processed/` : tables Parquet, `warehouse.duckdb` (dont `kpi_values`),
  `kpi_values.parquet` et `lineage.json` ;
- `data/audit/` : `audit_report.json` / `audit_report.md` (verdict, contrôles,
  avertissements, décisions de publication, journal des décisions, 3 exemples),
  `explanations.jsonl`, `evaluation.md` / `evaluation.json` (injection de fautes) ;
- `outputs/reports/<run_id>/` : rapport standardisé de chaque agent et `run.json`.

`main.py run` renvoie le code 0 pour `success` et `no_change`, 2 sinon
(`failed`, `quality_failed`, `audit_failed`). `main.py explain` lit uniquement la
table `kpi_explanations` (aucun recalcul, aucun réseau).

Le rapport qualité est lié au run : quand son `run_id` et les SHA-256 des
sources correspondent à `lineage.json`, les KPI ne portent plus la raison de
revue `quality_provenance_unverified` ; un désaccord donne
`quality_provenance_mismatch` (par exemple `--from etl` avec un rapport qualité
d'un run précédent).

## Sorties Route 2

- `outputs/reports/<run_id>/analysis_dataset.json` : dataset déterministe
  (observations, séries, tendances, classements, comparaisons, couverture,
  notices, provenance) ;
- `outputs/reports/<run_id>/bi_analyst.{json,md}` : rapport et constats
  rattachés aux preuves ;
- `outputs/reports/<run_id>/dashboard_data.json` : contrat validé ;
- `outputs/dashboard/dashboard.json` : copie exportée du contrat (l'ancien front
  qui la lisait est retiré, voir `legacy/dashboard/`) ;
- `outputs/reports/<run_id>/run.json` : résumé du run Route 2.

## Données et périmètre

- Findex : vagues 2011, 2014, 2017, 2021, 2022 (partielle), 2024 ; les agrégats
  régionaux sont conservés mais signalés comme non-pays.
- Année sans enquête Findex (ex. Algérie 2012) : les cartes, graphiques et
  insights Findex lisent la dernière vague au plus tard à l'année choisie (2011),
  jamais une vague postérieure ; chaque valeur porte `year` (année utilisée) et
  `year_requested`, la vue porte `findex_wave` et le tableau de bord affiche un
  bandeau. Les indicateurs FAS et WDI gardent l'année choisie. Sans vague
  antérieure (Tunisie avant 2014, Maroc avant 2017), les valeurs Findex restent
  indisponibles.
- FAS : séries `FA26N.PHTADLT_NUM`, `FA18N.PHTADLT_NUM`,
  `FA29N_COMBANK.PTADLT_NUM`, `FA21N_COMBANK.PTADLT_NUM`,
  `LOANACCN_COMBANK.PTADLT_NUM`, `FA30N_COMBANK.PTADLT_NUM` ; 2025 exclue car
  incomplète.
- WDI : PIB, PIB par habitant (USD courants) et croissance du PIB
  `NY.GDP.MKTP.KD.ZG` (% annuel, prix constants 2015), lignes sans code ISO3
  ignorées. `gdp_growth_pct` reprend directement cet indicateur : il n'est plus
  calculé depuis le PIB en USD courants (les effets de change comptaient comme
  de la croissance). Les taux négatifs sont conservés.
- Findex, sous-groupes : `gender` (men / women), `income` (richest 60% /
  poorest 40%), `age_cat` (age 25+ / ages 15-24). `country_year` contient
  `account_male/female`, `account_richest_60/poorest_40`,
  `account_age_25_plus/15_24` et les écarts `gender_gap_pp`, `income_gap_pp`,
  `age_gap_pp` (NULL si un sous-groupe manque). Le pivot filtre sur la dimension
  et sa valeur pour éviter toute collision entre groupes.
- Codes non ISO3 normalisés : `KOS -> XKX`, `WBG -> PSE` ; agrégats `EAP`,
  `WLD`, etc. conservés dans `country_dim` mais identifiés comme agrégats.

## Choix techniques

- **LangGraph** : graphe d'états explicite et traçabilité ; repli séquentiel si
  l'import LangGraph est indisponible.
- **LLM pour le quality gate** : routage primaire/fallback, température 0,
  sorties JSON validées, cache disque et plafond d'appels. Les décisions
  PASS/FAIL restent déterministes.
- **ETL déterministe** : pandas / DuckDB pour l'harmonisation, les jointures et
  le modèle en étoile ; le LLM ne calcule aucun chiffre.
- **Traçabilité** : SHA-256 des sources, volumes rejetés, contrôles ETL et
  `lineage.json`.

## Livrables P1

Code et architecture, pipeline automatisé, documentation des sources,
Data Quality Report, tables du modèle en étoile, lineage et tests unitaires.

## Findex digital indicator definitions (verified 2026-10-22)

| Raw/fact code | Meaning | `country_year` column |
|---|---|---|
| `dig_acc` | Adults with a digitally enabled account: mobile money, or a bank/similar account allowing payments by card or phone. This measures account ownership/enabling, not transaction frequency. | `digitally_enabled_account` |
| `g20_any` | Adults who made or received a digital payment in the past year. The measure includes several payment purposes, not just remittances. | `digital_payment` |

For total-population estimates, the population is adults aged 15+; facts also
retain the survey subgroups. Both raw/fact measures remain fractions. The wide
table continues to display percentages (`100 * value`), preserving missing values.

Sources: [World Bank indicator `dig-acc`](https://genderdata.worldbank.org/en/indicator/dig-acc),
[Little Data Book 2025, glossary p. 160](https://thedocs.worldbank.org/en/doc/be6615202d1f08a25855c8ac2d615122-0050012025/related/Little-Data-Book-2025-Web.pdf),
and [Global Findex 2025 glossary, sheet `Glossary`, row 118, code `g20.any`](https://thedocs.worldbank.org/en/doc/be6615202d1f08a25855c8ac2d615122-0050012025/related/GlobalFindex2025-glossary.xlsx).
The official portal/glossary use hyphens/dots in codes; the local CSV uses underscores.

Schema correction: `digital_payment` previously contained `dig_acc`; it now
contains `g20_any`. The misleading `remittance_use` column is removed rather
than retained as a false remittance measure. Consumers must update references;
existing warehouse files are not migrated by this code change.

No remittance-specific or digital-account transaction-frequency KPI has been
verified from these two columns. Do not infer either one or substitute one
measure when the other is missing. This verification does not certify other
Findex labels or every historical wave's detailed questionnaire construction.

## Findex labels verified in the 2025 glossary (2026-10-29)

Checked against the official Global Findex 2025 glossary (sheet `Glossary`,
sha256 `8eb99754…f923`); row numbers are kept in
`tools/dictionary.py:FINDEX_GLOSSARY_ROWS`.

| Codes | Meaning | Rows |
|---|---|---|
| `fin17a` | Saved at a bank or similar financial institution (past year) | 24 |
| `fin22a` | Borrowed from a bank or similar financial institution, credit card included (past year) | 31 |
| `fin24aP`, `fin24aN`, `fin24aSD_ND` | Emergency funds within 30 days: possible / not possible / possible and not or somewhat difficult | 44, 45, 43 |
| `fin24sav`, `fin24fam`, `fin24work`, `fin24bor`, `fin24sell`, `fin24other` | Main source of emergency funds: savings, family/friends, work, loan, sale of assets, other | 34-39 |
| `fin11a`-`fin11f` | Reasons for not having an account (distance, cost, documents, insufficient funds, family member has one, trust) | 6-11 |

`fin24aP`, `fin24sav` and `fin24bor` were previously labelled as digital payment,
saving and borrowing; they measure financial resilience and feed no KPI. All
values are fractions of all adults aged 15+. A code that cannot be verified is
listed in `FINDEX_UNVERIFIED`, labelled `(unverified)` and rejected by the KPI
catalog (none today).

## Source schema validation

Quality checks use the mandatory column lists from the ETL. Missing columns,
null/blank keys, malformed country/indicator/annual FAS series codes, and
nonnumeric, nonfinite or fractional key years are critical errors. FAS also
requires at least one four-digit year column. Country aliases and aggregate
codes retain their existing treatment; unknown three-letter codes retain warnings.

Minimum structural indicator coverage is one selected Findex column, one
configured FAS series, and one configured GDP indicator code. The Quality Agent
passes its source configuration into these checks. Standalone checks without
source configuration use dictionary indicators (Findex/GDP) or structural FAS
series coverage. Missing optional indicators are listed in schema metrics.
No complete annual panel, survey-wave list, or non-null value per indicator is
required. Existing row-count, missingness, duplicate and range scoring still
applies; missing observations alone are not new critical schema errors.

## FAS percentage plausibility diagnostics

`quality.fas_pct_gdp_threshold` defaults to `1000.0` (% GDP). Finite values
strictly above this diagnostic threshold are flagged only for
`OUTD_COMBANK.POGDP` (`deposits_pct_gdp`) and `OUTL_COMBANK.POGDP`
(`loans_pct_gdp`). The check covers all four-digit year columns in the raw
source, including years outside the ETL analysis period.

Flags appear under `diagnostics` in the quality JSON, in a separate Markdown
section, and in `quality_diagnostics.csv`. Each records country/ISO3, year,
original series code and value, numeric value, unit, threshold and review reason.
They are separate from structural/scored `issues` and do not change scores,
critical issue counts or gate decisions. No value is dropped, clamped or rescaled.
The threshold is a review trigger, not an official IMF validity limit; the
underlying values and their denominators still require source verification.

## Dashboard Finova — `dashboard_app/`

Tableau de bord standalone : API **FastAPI en lecture seule** + front
**React/Vite/TypeScript** (SVG maison). Il expose le contrat de la Route 2 tel
que produit par le pipeline, sans LLM et sans recalcul côté client.

Pré-requis : warehouse et rapport qualité déjà construits
(`python main.py run --from quality --no-llm`) et Node.js >= 18.

### 1. Produire le contrat publié

```powershell
$env:PYTHONPATH = "src"
python -c "from biflow.route2_graph import run_route2; run_route2(use_llm=False)"
```

Écrit `dashboard_app/public/data/finova.json`, un `finova_spec.json` par run
dans `outputs/reports/<run_id>/` et un snapshot dans
`outputs/dashboard/history/` (Tunisie 2024 par défaut, `config/config.yaml`).
Avec `dashboard.pregenerate_peers: true`, les vues des pairs (`kpi.peers`) pour
l'année publiée sont ensuite écrites dans le cache `outputs/dashboard/generated/`
de l'API (résultat dans `run.json`, clé `pregenerated`).

### 2. Lancer le dashboard

Windows, en une commande (depuis la racine du projet) :

```powershell
.\start.ps1               # vérifie .venv et le build, puis ouvre http://127.0.0.1:8000
.\start.ps1 -NoBrowser    # sans ouvrir le navigateur ; -Port 8001 pour un autre port
.\stop.ps1                # arrête uniquement le serveur lancé par start.ps1
```

`start.ps1` vérifie que `.venv\Scripts\python.exe` et `dashboard_app\web\dist`
existent, refuse de démarrer si le port 8000 est déjà occupé (il affiche le nom
et le PID du processus qui le tient), fixe `PYTHONPATH=src`, lance uvicorn sur
`127.0.0.1:8000` en arrière-plan (journaux dans `outputs\logsinova-server.*.log`),
attend `/api/health` puis ouvre le navigateur. Le PID est écrit dans `.finova.pid`
(non versionné) ; `stop.ps1` n'arrête que ce processus (et son processus enfant),
jamais un autre programme sur le port. Si PowerShell refuse les scripts locaux :
`powershell -ExecutionPolicy Bypass -File .\start.ps1`.

Manuellement (toutes plateformes) :

```powershell
$env:PYTHONPATH = "src"
$env:FINOVA_PREWARM = "1"   # optionnel : prépare en tâche de fond les vues 2024/2021/2017
python -m uvicorn dashboard_app.api.app:app --host 127.0.0.1 --port 8000
# http://127.0.0.1:8000  (API + UI buildée si dashboard_app/web/dist existe)
```

Les vues générées à la demande sont mises en cache dans
`outputs/dashboard/generated/` (une entrée par pays et année ; la clé réunit la
date du warehouse, l'empreinte du catalogue et celle du code qui construit la vue
et ses insights, modifications non commitées comprises : une vue périmée n'est
jamais servie, les anciens fichiers sont simplement ignorés) : la première ouverture d'un pays prend 20 à 40 secondes, les
suivantes sont immédiates, y compris après redémarrage du serveur.

Développement front avec proxy `/api` vers le port 8000 :

```powershell
cd dashboard_app/web
npm ci
npm run dev        # http://127.0.0.1:5173
npm run build      # tsc --noEmit && vite build
```

Le login est une démonstration d'interface (aucune authentification réelle).

### 3. Endpoints

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/api/spec?iso3=TUN&year=2024` | contrat du scope demandé |
| GET | `/api/runs?limit=20` | derniers `outputs/reports/*/run.json` |
| POST | `/api/ask` | Ask Finova : conversation, chiffres lus par outils et vérifiés |
| GET | `/api/health` | présence du contrat et du warehouse |
| POST | `/api/sources/detect` | dépôt CSV (multipart) : structure, rôles proposés, configuration réutilisable |
| POST | `/api/sources/dry-run` | contrôle sans écriture : lignes retenues, pays inconnus, unités manquantes, aperçu |
| POST | `/api/sources/confirm` | enregistre la source et lance le recalcul (`job_id`) |
| GET | `/api/sources/jobs/{job_id}` | état du recalcul (étape, succès, exclusion qualité, échec d'audit) |
| GET | `/api/sources` | sources utilisateur : lignes, années, pays, score qualité, statut |
| DELETE | `/api/sources/{name}` | retire la source (copie conservée) et lance le recalcul |
| GET | `/api/sources/{name}/data` | valeurs publiées de la source (`fact`, source `user:<nom>`), lecture seule |
| GET | `/api/sources/comparable-kpis` | KPI officiels proposés à l'étape « Indicateurs » (unité, définition, dénominateur) |
| GET | `/api/sources/comparisons?iso3=&year=` | vos indicateurs face aux KPI officiels déclarés comparables, lecture seule |
| GET | `/api/recommendations?iso3=&year=` | pistes officielles, et à part les pistes « à partir de vos données » |
| GET | `/api/reports/insights.pdf?iso3=&year=&annexe=true` | rapport des constats ; `annexe=true` ajoute « Annexe : vos données » |
| GET | `/api/audit/summary` | page « Audit et confiance » : verdict, publication, motifs de réserve, audit des constats, évaluation |
| GET | `/api/audit/checks` | contrôles A1…C4 décrits en français, lignes concernées |
| GET | `/api/audit/explain?kpi_id=&iso3=&year=` | explication d'une valeur (même lecture que `main.py explain`) |

Le scope publié est servi tel quel (`X-Finova-Source: file`). Tout autre
pays/année est **construit à la demande** depuis le warehouse
(`X-Finova-Source: generated`), puis mémorisé ; le cache est invalidé si le
warehouse change. Cette génération réutilise le moteur KPI existant : le
premier appel sur un nouveau couple pays/année peut durer une à deux minutes,
les appels suivants sont instantanés. Aucune année n'est substituée : les
cartes affichent l'année réellement utilisée, ou « To load » / « Indisponible ».

Ask Finova (`POST /api/ask`, `src/biflow/agents/ask.py`) : avec une clé
(`GROQ_API_KEY` ou `GOOGLE_API_KEY`, routage `llm.routing.ask`, réglages
`llm.ask`), l'assistant converse et lit les chiffres uniquement via des outils
sur les faits des vues Finova (`get_kpi`, `compare_countries`, `compare_years`,
`explain` sur `kpi_explanations`, `list_kpis`, `current_scope`) ; tout nombre
absent des résultats d'outils du tour déclenche une régénération puis la réponse
déterministe. Le navigateur envoie les 10 derniers messages de la session et un
budget d'appels LLM est tenu par session. Vos données (« Mes données ») ne sont lues
que par l'outil `get_user_indicator` et toujours annoncées « D'après vos données (non
vérifiées par BIFlow) » ; avec `llm.ask.allow_user_data_to_llm: false` (défaut), ces
questions restent en mode simple, sans appel au LLM (voir « Mode banquier »). Sans clé : salutations, suggestions,
relances (« et en 2021 ? », « et le Maroc ? ») et formulations FR / EN / darija.

Page « Mes données » (sources CSV de l'utilisateur, API locale) : le fichier
déposé reste en attente (`outputs/uploads_pending/`) jusqu'à la confirmation,
puis est copié tel quel dans `data/uploads/` ; il n'est jamais exécuté ni ouvert
par un tableur. Le recalcul (un seul à la fois, état dans `outputs/jobs/`, délai
`uploads.job_timeout_min`) lance `python main.py run --no-llm --offline-official`
puis Route 2 : avec `--offline-official`, Findex, FAS et PIB sont repris du
snapshot publié, sans réseau, et seule la source utilisateur peut changer. Les
données utilisateur n'entrent jamais dans les cartes KPI officielles ni dans les
constats et pistes officiels ; elles apparaissent seulement, étiquetées, dans le
bloc « Vos indicateurs face aux données officielles », la sous-liste « À partir de
vos données », Ask Finova et l'annexe facultative du PDF. Les CSV exportés (rapports qualité, profils) préfixent
d'une apostrophe les cellules texte commençant par `=`, `+`, `-` ou `@` (S6).

Démonstration : `docs/examples/user_source_example.csv` contient des **données
fictives** (« exemple fictif » dans chaque libellé, ligne de commentaire en tête),
à déposer sur la page « Mes données » : années en colonnes, point-virgule,
virgule décimale, noms de pays en français, une valeur « n.d. », une cellule vide
et un pays à rattacher à la main (Mauritanie → MRT). Unités à choisir : nombre
pour les clients, % pour le taux de pénétration. Ces valeurs ne sont pas réelles.

Page « Audit et confiance » : lecture seule de `data/audit/audit_report.json`,
`kpi_values` et `kpi_explanations` (données officielles uniquement). L'évaluation
par injection de fautes n'est jamais lancée par l'API : elle est lue dans
`data/audit/evaluation.json` (`python scripts/evaluate_auditor.py`), avec sa date ;
si elle est antérieure au dernier audit, la page l'indique.

### Installation reproductible (dépendances verrouillées)

`requirements.txt` reste la liste lisible des dépendances. `requirements.lock`
fixe chaque paquet (dépendances transitives comprises) avec ses empreintes
SHA-256 : pip refuse tout fichier dont l'empreinte diffère.

```powershell
python -m pip install --upgrade pip   # pip 23.0 refuse ce verrou ; 26.3 vérifié
python -m pip install --require-hashes -r requirements.lock
```

Le verrou a été généré **sous Windows avec Python 3.10**, aux versions
installées et testées. Sur un autre système ou une autre version de Python,
le régénérer avec la même commande (outil `uv`, voir `requirements-dev.txt`) en
adaptant `--python-platform` / `--python-version` :

```powershell
python -m uv pip compile requirements.txt --generate-hashes --python-version 3.10 --python-platform windows -o requirements.lock
```

Sécurité de l'interface : l'API envoie une politique `Content-Security-Policy`
stricte (`default-src 'self'`, aucun script ni style en ligne ; seules exceptions :
la police Inter de Google Fonts et une icône SVG en `data:`). Le cache LLM est
stocké en JSON (`outputs/llm_cache/*.json`) ; les anciens fichiers `.pkl` ne sont
jamais relus. Les chemins lus dans `lineage.json` doivent rester dans le projet.

### 4. Tests

```powershell
$env:PYTHONPATH = "src"
python -m pytest tests/test_dashboard_api.py tests/test_dashboard_spec.py `
  tests/test_analyst.py tests/test_warehouse_reader.py tests/test_route2_graph.py -q
cd dashboard_app/web; npm run typecheck
```
