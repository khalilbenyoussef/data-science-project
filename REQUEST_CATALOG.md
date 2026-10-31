# REQUEST_CATALOG — séries à ajouter au catalogue KPI

- **Émetteur** : propriétaire Route 2 (Analyst / Dashboard / UI)
- **Destinataire** : propriétaire du catalogue (`config/kpi_catalog.v1.yaml`, version 1.0.0)
- **Date** : 2026-10-29
- **Contexte** : le dashboard Finova affiche ces séries via `tools/warehouse_reader.py` avec la mention « Warehouse — not in KPI catalog yet » et `requires_review=true`. Elles ne peuvent pas être certifiées ni publiées avant leur entrée au catalogue.

## Priorité 1 — disponibilité et accès (FAS)

| Série demandée | Table / code observé | Unité | Couverture observée | Widget |
|---|---|---|---|---|
| `atm_density` | `fact`, `country_year.atm_per_100k` | /100 000 adultes | 2011–2024 | Access & Credit, Overview |
| `depositors_per_1k` | `fact`, `country_year.depositors_per_1k` | /1 000 adultes | 2011–2024 (TUN absent) | Access & Credit |
| `borrowers_per_1k` | `fact`, `country_year.borrowers_per_1k` | /1 000 adultes | 2011–2024 | Access & Credit |
| `deposit_accounts_per_1k` | `fact` | comptes /1 000 adultes | 2011–2024 | Access & Credit |
| `loan_accounts_per_1k` | `fact` | comptes /1 000 adultes | 2011–2024 | Access & Credit |
| `deposits_pct_gdp` | `fact`, `OUTD_COMBANK.POGDP` | % du PIB | 2011–2024, TUN 2024 = 71,68 | Access & Credit |
| `loans_pct_gdp` | `fact`, `OUTL_COMBANK.POGDP` | % du PIB | 2011–2024, TUN 2024 = 67,77 | Access & Credit |

## Priorité 2 — usage formel et barrières (Findex)

| Série demandée | Table / code | Unité | Couverture | Remarque |
|---|---|---|---|---|
| `saved_at_fi` | `fact.fin17a` | % adultes | 2014, 2017, 2021, 2024 | épargne en institution financière |
| `borrowed_at_fi` | `fact.fin22a` | % adultes | 2014, 2017, 2021, 2024 | emprunt en institution financière |
| `emergency_funds` | `fact.fin24aP` | % adultes | 2014–2024 (2021 : 82,60 ; 2024 : 88,39) | **libellé à vérifier** : `dictionary.py` l'appelle « Paiement numerique », la définition Findex 2025 est « could obtain emergency money » |
| `fin24sav`, `fin24bor` | `fact` | % adultes | 2021, 2024 | définitions de vague à documenter |
| `barriers` (`fin11a`–`fin11f`) | **absent du warehouse** | % adultes | — | nécessite collecte/ETL avant tout affichage ; placeholder « To load » |

## Priorité 3 — inégalités

| Série demandée | Source | Unité | Remarque |
|---|---|---|---|
| `account_ownership` par sous-groupe | `fact` dimensions `gender`, `income`, `age_cat`, `education`, `laborforce`, `urbanicity` | % adultes | disponible ; le catalogue ne couvre que le total |
| `gender_gap_pp` | dérivé de `account_ownership` (hommes − femmes) | points de % | disponible dans `country_year.gender_gap_pp` |
| `digital_payment_rate` par sous-groupe | `fact.g20_any` | % adultes | disponible |

## Exigences de définition attendues

Pour chaque série : définition, unité, dénominateur (population adulte), période de référence, années valides, statut de vérification, politique de données manquantes (`preserve_missing_v1`) et source de preuve. Aucune série ne doit être publiée sans ces champs.

## Impact côté Route 2

Tant que ces séries ne sont pas au catalogue :

- elles restent isolées derrière `tools/warehouse_reader.py` (une seule interface) ;
- chaque widget affiche le chip « Warehouse — not in KPI catalog yet » et `requires_review=true` ;
- `loans_pct_gdp` / `deposits_pct_gdp` ne sont plus « To load » depuis le rebuild du 2026-10-29, mais restent non catalogués ;
- le remplacement se fera sans changement d'UI, par bascule de l'interface vers `SemanticKpiAgent`.
