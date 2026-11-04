# Rapport d'audit — BIFlow (Route 1, Route 2, FinOVA, « Mes données »)

- **Date** : 2026-11-04 (mesures prises entre 12 h 57 et 13 h 15)
- **Version auditée** : branche `el-final`, commit `dee7f1f` (+ commit de ce rapport)
- **Périmètre** : pipeline Route 1 (collecte → audit), Route 2 (analyse, spec FinOVA, constats), API et
  interface FinOVA (9 pages dont « Mes données » et « Audit et confiance »), Ask Finova, dashboard
  historique `dashboard/`, dépendances.
- **Méthode** : reconstruction réelle du pipeline, Route 2 et audit des constats, évaluation de
  l'Auditor par injection de fautes, sondes de sécurité, suite de tests complète, `npm audit`,
  vérification navigateur (Playwright). Tous les nombres ci-dessous proviennent des commandes
  listées en annexe, exécutées pendant cette session ; aucun chiffre n'est repris de l'ancien rapport.
- **Verdict global** : **conforme et publiable en local**. Audit des données `pass_with_warnings`
  (17 réussis, 2 avertissements, 0 échec), 0 valeur bloquée, 15/15 constats acceptés, 9/9 fautes
  injectées détectées. Les 9 constats de sécurité de l'audit précédent sont corrigés. Un nouveau
  constat modéré (ECharts du dashboard historique) reste ouvert.

---

## 1. Synthèse

| Indicateur | Valeur |
|---|---|
| Run audité | `part_d_audit_report` (snapshot `v5`, catalogue 1.7.0) |
| Lignes KPI auditées (`kpi_values`) | 1 620 |
| Verdict d'audit | `pass_with_warnings` — 17 réussis, 2 avertissements, 0 échec |
| Publication | 1 509 approuvées, 111 approuvées avec réserve, 0 bloquée |
| Constats (Route 2) | 15 audités, 15 acceptés, 0 rejeté, 2 non auditables |
| Injection de fautes | 9 / 9 détectées |
| Tests | 1 248 réussis, 0 échec |
| Constats de sécurité S1–S9 | 9 corrigés, 0 ouvert |
| Nouveaux constats | 1 modéré retiré du service (N1), 3 informatifs |

---

## 2. Périmètre examiné

| Élément | Volume / état |
|---|---|
| Code Python (`src/`) | 53 fichiers suivis, 17 130 lignes |
| Tests Python | 53 fichiers `tests/test_*.py`, 1 248 cas |
| Front FinOVA (`dashboard_app/web/src`) | 12 fichiers, build Vite réussi |
| Warehouse | 90 732 faits (Findex 64 328, FAS 15 753, PIB 10 651), 219 pays, 0 fait utilisateur |
| Dépendances Python | 81 paquets verrouillés, 1 594 empreintes SHA-256 (`requirements.lock`) |

---

## 3. Audit des données (run `part_d_audit_report`)

Reconstruction `python main.py run --rebuild --no-llm` sur les blobs du snapshot publié `v5`
(Findex `35f3fa934adf…`, FAS `f60b4d1b3de6…`, PIB `b746f41a1c59…`), durée 18,6 s.

| Contrôle | Résultat | Lignes concernées |
|---|---|---|
| A1 à A6 (recalcul, nullité, pairs, complétude, brut → fait, sources utilisateur) | réussis | 0 |
| B1 à B9 (unités, bornes, entités, pairs, identifiants, empreintes, contenu, catalogue, qualité) | réussis | 0 |
| C1 vague d'enquête partielle | réussi | 0 |
| C2 moyenne des pairs incomplète | **avertissement** | 84 |
| C3 constats qualité sur une entrée | réussi | 0 |
| C4 variation dans le bruit d'enquête | **avertissement** | 101 |

Publication : 1 509 approuvées, 111 approuvées avec réserve, 0 bloquée. Motifs des réserves :
`partial_peer_coverage` 84, `no_peer_observation` 27. Les deux avertissements sont des réserves de
lecture (couverture des pairs, bruit d'enquête), pas des erreurs de calcul.

Catalogue 1.7.0 : seule nouveauté, un libellé français `name_fr` pour les 44 KPI. Après
reconstruction, les valeurs `kpi_values` (KPI, pays, année, valeur, statut), les faits officiels, le
verdict et les 17 textes de constats sont identiques à ceux du catalogue 1.6.0.

## 4. Audit des constats (Route 2)

| Vue | Audités | Acceptés | Rejetés | Non auditables |
|---|---|---|---|---|
| Vue publiée (Tunisie 2024, run `route2_20261104T125802503588`) | 15 | 15 | 0 | 2 (`poverty:INS-poverty-smig`, `poverty:INS-poverty-rate`) |
| Vue générée Algérie 2012 (année sans enquête) | 9 | 9 | 0 | 0 |

Les deux constats non auditables citent des références statiques (SMIG, pauvreté INS) qui ne sont pas
des KPI du catalogue. Pour Algérie 2012, les années citées sont 2011 (vague Findex lue) et 2012
(indicateurs FAS), jamais une année postérieure.

## 5. Évaluation de l'Auditor par injection de fautes

`python scripts/evaluate_auditor.py --out data/audit` (copie isolée des données, 48,9 s),
évaluation datée du 2026-11-04 12:59:47, run de référence `part_d_audit_report` ; référence sans
faute : `pass_with_warnings` (17 / 2 / 0).

| Faute injectée | Contrôle attendu | Détectée |
|---|---|---|
| Valeur KPI modifiée (+0,05) | A1 | oui |
| Mauvaise unité (densité en %) | B1 | oui |
| Ligne agrégat WLD dans `kpi_values` | B3 | oui |
| Zéro au lieu de NULL | A2 | oui |
| `snapshot_id` incohérent | B5 | oui |
| Empreinte source modifiée | B6 | oui |
| KPI provisoire dans le catalogue | B8 | oui |
| Constat citant un mauvais chiffre | F1 | oui |
| Constat avec un nombre non cité | F1 | oui |

**9 / 9 fautes détectées.** Le résultat est affiché sur la page « Audit et confiance » avec sa date ;
la page signale un résultat antérieur au dernier audit.

---

## 6. Sécurité — statut des constats S1 à S9

| ID | Constat (audit du 2026-10-26) | Statut | Commit | Vérification dans cette session |
|---|---|---|---|---|
| S1 | Cache LLM désérialisé avec `pickle.load` | **Corrigé** | `e64e45f` | Aucune occurrence de `pickle` dans `src/` ; cache JSON (`dumpd` / `load` avec liste explicite de classes) ; test : un `.pkl` piégé n'est jamais lu, un JSON pointant vers `os.system` est refusé |
| S2 | Dépendances non verrouillées | **Corrigé** | `e64e45f` | `requirements.lock` : 81 paquets, 1 594 empreintes ; installation `--require-hashes` testée dans un environnement neuf ; généré sous Windows / Python 3.10 (régénération documentée) |
| S3 | Aucun dépôt Git | **Corrigé** | `bb4e681` (2026-09-26) | Dépôt Git, 59 commits sur `el-final` au commit `dee7f1f` |
| S4 | Infobulles ECharts en HTML avec libellés de données | **Corrigé** | `e64e45f` | `escapeHtml` sur chaque libellé ; tests Node (libellé `<img onerror>`) et contrôle source des formateurs |
| S5 | Validation du contrat limitée aux cartes | **Corrigé** | `e64e45f` | Séries, classements, comparaisons et table vérifiés valeur par valeur (Python et `validate.ts`) ; 19 contrats altérés refusés côté Python (cartes et tableaux imbriqués), 8 tests Node |
| S6 | Export CSV sans neutralisation des formules | **Corrigé** | `9cf4898` | Cellules texte commençant par `=`, `+`, `-`, `@` préfixées d'une apostrophe (en-têtes et index compris), nombres inchangés |
| S7 | Chemins de lineage sans restriction de racine | **Corrigé** | `e64e45f` | Chemin hors du projet (ou via `..`) : ni lu ni empreinté, motif `raw_source_path_outside_project` / `lineage_warehouse_path_invalid` |
| S8 | Pas de Content-Security-Policy | **Corrigé** | `e64e45f` | En-tête `Content-Security-Policy` (`default-src 'self'`, aucun script ni style en ligne) et `X-Content-Type-Options: nosniff` ; navigateur : 0 violation CSP sur la connexion, les 9 pages et le panneau Ask Finova, à 1 440 et 768 px |
| S9 | `docs/` ignoré par Git | **Corrigé** | `a654c8d` | `.gitignore` n'exclut plus que `docs/sources/` (sources téléchargées) |

## 7. Nouveaux constats

| ID | Sévérité | Constat | Statut / recommandation |
|---|---|---|---|
| N1 | **Modérée** | `npm audit` (dashboard historique, désormais `legacy/dashboard/`) : ECharts < 6.1.0, avis XSS GHSA-fgmj-fm8m-jvvx. Correctif = passage majeur à ECharts 6.1 (rupture). Le front FinOVA n'utilise pas ECharts (`npm audit` : 0 vulnérabilité). | **Retiré du service.** Le dashboard historique est déplacé dans `legacy/dashboard/`, remplacé par FinOVA (`dashboard_app`) : il n'est plus construit ni servi, et la Route 1 n'écrit plus dans son dossier (`outputs/dashboard/dashboard.json`). La dépendance vulnérable reste dans le code archivé (atténuée par S4) ; ne pas le remettre en service sans passer à ECharts 6.1. |
| N2 | Info | La CSP autorise Google Fonts (`fonts.googleapis.com`, `fonts.gstatic.com`) : requête tierce à chaque visite. Les pages de développement `/docs` et `/redoc` sont exemptées de CSP (scripts du CDN Swagger). | Héberger la police Inter localement ; désactiver `/docs` hors développement. |
| N3 | Info | Ask Finova en mode IA envoie la question et les faits officiels du tableau de bord au fournisseur LLM (Groq, puis Gemini). Aucune source utilisateur, aucun chemin ni clé n'est transmis ; budget d'appels par session. | À mentionner aux utilisateurs ; mode sans clé disponible. |
| N4 | Info | `requirements.lock` est propre à Windows / Python 3.10. | Régénérer par plateforme (commande documentée dans le README). |

## 8. Page « Mes données » (API de dépôt CSV)

| Point | Constat vérifié |
|---|---|
| S6 | Corrigé (`9cf4898`) : exports CSV neutralisés ; la copie du dépôt dans `data/uploads/` et le blob du snapshot restent identiques à l'octet près (contrôle brut → fait de l'Auditor). |
| Limites de dépôt | `uploads.max_file_mb` = 200 (HTTP 413 au-delà) ; extension `.csv` uniquement ; types MIME texte/CSV uniquement (HTTP 415 sinon) ; contenu binaire refusé ; nom de source `^[a-z][a-z0-9_]{1,40}$`, jamais une source officielle ; identifiant de dépôt UUID (aucun chemin libre) ; zone d'attente `outputs/uploads_pending/` nettoyée après 24 h. Fichiers jamais exécutés ni ouverts par un tableur. |
| Sources officielles hors ligne | Le recalcul lance `main.py run --no-llm --offline-official` : Findex, FAS et PIB sont repris du snapshot publié, sans réseau. Test : le nouveau snapshot ne diffère que par la source utilisateur, les empreintes officielles sont identiques, tout appel réseau fait échouer le test. Démonstration du 2026-11-04 : ajout puis retrait, valeurs Tunisie 2024 et verdict identiques avant et après. |
| Isolation des recalculs | Un seul recalcul à la fois (HTTP 409) ; processus séparé de l'API ; état sur disque `outputs/jobs/<id>.json` (relu après redémarrage) ; délai `uploads.job_timeout_min` = 15 min puis erreur claire ; job orphelin (API redémarrée) clos en erreur ; sous-processus tué si le job s'interrompt ; écritures du fichier d'état sérialisées (accès concurrent sous Windows). |
| Séparation des données | Les faits utilisateur (`source = user:<nom>`) ne sont ni dans les cartes KPI officielles, ni dans les décomptes de la page « Audit et confiance », ni dans les réponses d'Ask Finova (test dédié). |

---

## 9. Tests et validation

| Vérification | Résultat |
|---|---|
| Suite complète `pytest` | **1 248 réussis**, 0 échec (1 avertissement : fonction `load` de langchain en bêta) |
| Tests ciblés sécurité / dépôt / audit | 61 réussis |
| Build FinOVA (`npm run build`) | réussi |
| `npm audit --omit=dev` | FinOVA : 0 vulnérabilité ; dashboard historique (`legacy/`, retiré du service) : 1 modérée (N1) |
| Navigateur (Playwright, 1 440 et 768 px) | 0 violation CSP ; erreurs console uniquement sur la page de connexion : 404 des vidéos de fond non versionnées (repli sur le fond statique) |

## 10. Risques résiduels et priorités

1. **N1** — retiré du service (`legacy/dashboard/`) ; à ne réactiver qu'après passage à ECharts 6.1.
2. Vidéos de la page de connexion absentes du dépôt (404, repli statique) : les héberger ou retirer la référence.
3. **N2** — héberger la police localement pour une CSP sans origine tierce.
4. Réserves de données C2 / C4 : présentées comme telles dans l'interface (« approuvé avec réserve », variations dans le bruit d'enquête).

## 11. Verdict

Le pipeline, la Route 2 et l'interface FinOVA sont conformes : 0 échec d'audit, 0 valeur bloquée,
15/15 constats acceptés, 9/9 fautes détectées, 1 248 tests réussis. Les constats de sécurité S1–S9
sont tous corrigés ; le seul constat de sévérité modérée (N1) concerne le dashboard historique, retiré du service
(`legacy/dashboard/`), pas l'interface FinOVA.

---

## Annexe — commandes exécutées (session du 2026-11-04)

| # | Commande | Résultat utilisé |
|---|---|---|
| 1 | `date "+%Y-%m-%d %H:%M"` ; `git rev-parse --short HEAD` | date, commit `dee7f1f` |
| 2 | `python main.py run --rebuild --no-llm --run-id part_d_audit_report` | verdict, contrôles, publication, empreintes des sources, durée |
| 3 | Route 2 (`run_route2`) puis audit des constats (`insights_from_finova` + `audit_insights`) sur la vue publiée et la vue générée DZA 2012 | §4 |
| 4 | `python scripts/evaluate_auditor.py --out data/audit` | §5 |
| 5 | Requête DuckDB en lecture seule sur `kpi_values`, `fact`, `country_dim` et lecture de `data/audit/audit_report.json` | lignes, motifs de réserve, faits, pays |
| 6 | `grep -rn "import pickle\|pickle\.load" src/` | S1 |
| 7 | `grep -c` des paquets et empreintes de `requirements.lock` ; `uv venv` + `uv pip install --require-hashes -r requirements.lock` | S2 |
| 8 | `git log --reverse` ; `git rev-list --count HEAD` ; `git log -p -- .gitignore` | S3, S9 |
| 9 | `curl -sI http://127.0.0.1:8000/api/health` | S8 (en-têtes) |
| 10 | Playwright : connexion, 9 pages et panneau Ask Finova à 1 440 et 768 px (écouteur `securitypolicyviolation`) | S8 (navigateur), §9 |
| 11 | `pytest` ciblé (`test_llm`, `test_legacy_dashboard_escape`, `test_dashboard`, `test_kpi`, `test_analysis`, `test_dashboard_api`, `test_sources_api`, `test_user_integration`, `test_audit_api`) | S1, S4–S8, §8 |
| 12 | `npm audit --omit=dev` dans `dashboard_app/web` et `legacy/dashboard` | N1 |
| 13 | `git ls-files` + `wc -l` (fichiers et lignes) | §2 |
| 14 | `npm run build` puis `pytest -q` (suite complète) | §9 |
