# Catalogue des KPI

- **Généré le** : 2026-11-12T20:21:56
- **Run audité (Route 1)** : `20261112T201928`
- **Snapshot** : `v16`
- **Version du catalogue KPI** : 1.8.0
- **Run Route 2 (spec publiée)** : `route2_20261112T201947487351`
- **Sources lues** : `config/kpi_catalog.v1.yaml`, `table kpi_values`, `data/audit/audit_report.json (A1)`
- Document généré par `scripts/build_deliverables.py` : ne pas modifier à la main.

44 indicateurs officiels, catalogue `biflow_core_kpis` version 1.8.0 (mis à jour le 2026-11-05). Contrôle A1 de l'audit : pass — 1350 lignes pays recalculées depuis fact (tolérance 1e-09) ; 0 écart(s), 0 formule(s) non reconnue(s).

## Synthèse

| Identifiant | Nom | Unité | Source | Années valides | Lignes disponibles |
|---|---|---|---|---|---|
| `account_ownership` | Taux de détention d'un compte | percent | findex `account_t_d` | 2011, 2014, 2017, 2021, 2022, 2024 | 27 / 36 |
| `branch_density` | Densité des agences des banques commerciales | per_100k_adults | fas `FA26N.PHTADLT_NUM` | 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024 | 84 / 84 |
| `digital_payment_rate` | Paiement numérique effectué ou reçu | percent | findex `g20_any` | 2014, 2017, 2021, 2022, 2024 | 23 / 30 |
| `saving_rate` | Épargne (toute forme) | percent | findex `save_any_t_d` | 2014, 2017, 2021, 2022, 2024 | 23 / 30 |
| `borrowing_rate` | Emprunt (toute forme) | percent | findex `borrow_any_t_d` | 2014, 2017, 2021, 2022, 2024 | 23 / 30 |
| `unbanked_share` | Adultes sans compte | percent | findex `account_t_d` | 2011, 2014, 2017, 2021, 2022, 2024 | 27 / 36 |
| `formal_saving_rate` | Épargne auprès d'une institution financière | percent | findex `fin17a` | 2011, 2014, 2017, 2021, 2022, 2024 | 27 / 36 |
| `formal_borrowing_rate` | Emprunt auprès d'une institution financière | percent | findex `fin22a` | 2014, 2017, 2021, 2022, 2024 | 23 / 30 |
| `gender_gap` | Écart femmes-hommes de détention d'un compte | percentage_points | findex `account_t_d` | 2011, 2014, 2017, 2021, 2022, 2024 | 26 / 36 |
| `income_gap` | Écart de revenu de détention d'un compte | percentage_points | findex `account_t_d` | 2011, 2014, 2017, 2021, 2022, 2024 | 26 / 36 |
| `age_gap` | Écart d'âge de détention d'un compte | percentage_points | findex `account_t_d` | 2011, 2014, 2017, 2021, 2022, 2024 | 26 / 36 |
| `atm_density` | Densité des distributeurs automatiques | per_100k_adults | fas `FA18N.PHTADLT_NUM` | 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024 | 84 / 84 |
| `depositors_per_1k` | Déposants des banques commerciales | per_1k_adults | fas `FA29N_COMBANK.PTADLT_NUM` | 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024 | 39 / 84 |
| `borrowers_per_1k` | Emprunteurs des banques commerciales | per_1k_adults | fas `FA21N_COMBANK.PTADLT_NUM` | 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024 | 56 / 84 |
| `deposit_accounts_per_1k` | Comptes de dépôt des banques commerciales | per_1k_adults | fas `FA30N_COMBANK.PTADLT_NUM` | 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024 | 70 / 84 |
| `loan_accounts_per_1k` | Comptes de prêt des banques commerciales | per_1k_adults | fas `LOANACCN_COMBANK.PTADLT_NUM` | 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024 | 66 / 84 |
| `deposits_pct_gdp` | Encours des dépôts des banques commerciales | percent_of_gdp | fas `OUTD_COMBANK.POGDP` | 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024 | 84 / 84 |
| `loans_pct_gdp` | Encours des prêts des banques commerciales | percent_of_gdp | fas `OUTL_COMBANK.POGDP` | 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024 | 84 / 84 |
| `emergency_funds` | Fonds d'urgence mobilisables en 30 jours | percent | findex `fin24aP` | 2014, 2017, 2021, 2022, 2024 | 23 / 30 |
| `emergency_source_savings` | Source principale des fonds d'urgence : épargne | percent | findex `fin24sav` | 2021, 2022, 2024 | 12 / 18 |
| `emergency_source_borrowing` | Source principale des fonds d'urgence : prêt (banque, employeur ou prêteur privé) | percent | findex `fin24bor` | 2021, 2022, 2024 | 12 / 18 |
| `mobile_money_account` | Compte de monnaie mobile | percent | findex `mobileaccount_t_d` | 2014, 2017, 2021, 2022, 2024 | 19 / 30 |
| `inactive_accounts` | Compte inactif | percent | findex `inactive_t_d` | 2014, 2017, 2021, 2022, 2024 | 23 / 30 |
| `account_ownership_women` | Détention d'un compte - femmes | percent | findex `account_t_d` | 2011, 2014, 2017, 2021, 2022, 2024 | 26 / 36 |
| `account_ownership_men` | Détention d'un compte - hommes | percent | findex `account_t_d` | 2011, 2014, 2017, 2021, 2022, 2024 | 26 / 36 |
| `account_ownership_poorest_40` | Détention d'un compte - 40 % des ménages les plus pauvres | percent | findex `account_t_d` | 2011, 2014, 2017, 2021, 2022, 2024 | 26 / 36 |
| `account_ownership_richest_60` | Détention d'un compte - 60 % des ménages les plus riches | percent | findex `account_t_d` | 2011, 2014, 2017, 2021, 2022, 2024 | 26 / 36 |
| `account_ownership_age_15_24` | Détention d'un compte - adultes de 15 à 24 ans | percent | findex `account_t_d` | 2011, 2014, 2017, 2021, 2022, 2024 | 26 / 36 |
| `account_ownership_age_25_plus` | Détention d'un compte - adultes de 25 ans et plus | percent | findex `account_t_d` | 2011, 2014, 2017, 2021, 2022, 2024 | 26 / 36 |
| `account_ownership_primary_or_less` | Détention d'un compte - niveau primaire ou moins | percent | findex `account_t_d` | 2011, 2014, 2017, 2021, 2022, 2024 | 26 / 36 |
| `account_ownership_secondary_or_more` | Détention d'un compte - niveau secondaire ou plus | percent | findex `account_t_d` | 2011, 2014, 2017, 2021, 2022, 2024 | 26 / 36 |
| `account_ownership_out_of_laborforce` | Détention d'un compte - hors population active | percent | findex `account_t_d` | 2011, 2014, 2017, 2021, 2022, 2024 | 26 / 36 |
| `account_ownership_in_laborforce` | Détention d'un compte - population active | percent | findex `account_t_d` | 2011, 2014, 2017, 2021, 2022, 2024 | 26 / 36 |
| `account_ownership_rural` | Détention d'un compte - milieu rural | percent | findex `account_t_d` | 2024 | 6 / 6 |
| `account_ownership_urban` | Détention d'un compte - milieu urbain | percent | findex `account_t_d` | 2024 | 6 / 6 |
| `barrier_too_far` | Pas de compte : institutions financières trop éloignées | percent | findex `fin11a` | 2024 | 5 / 6 |
| `barrier_too_expensive` | Pas de compte : services financiers trop chers | percent | findex `fin11b` | 2024 | 5 / 6 |
| `barrier_no_documents` | Pas de compte : documents requis manquants | percent | findex `fin11c` | 2024 | 5 / 6 |
| `barrier_insufficient_funds` | Pas de compte : pas assez d'argent | percent | findex `fin11d` | 2024 | 5 / 6 |
| `barrier_family_has_account` | Pas de compte : un membre de la famille en a déjà un | percent | findex `fin11e` | 2024 | 5 / 6 |
| `barrier_no_trust` | Pas de compte : manque de confiance dans les institutions financières | percent | findex `fin11f` | 2024 | 5 / 6 |
| `education_gap` | Écart d'éducation de détention d'un compte | percentage_points | findex `account_t_d` | 2011, 2014, 2017, 2021, 2022, 2024 | 26 / 36 |
| `laborforce_gap` | Écart d'activité de détention d'un compte | percentage_points | findex `account_t_d` | 2011, 2014, 2017, 2021, 2022, 2024 | 26 / 36 |
| `urban_gap` | Écart urbain-rural de détention d'un compte | percentage_points | findex `account_t_d` | 2024 | 6 / 6 |

## Fiches

### Taux de détention d'un compte (`account_ownership`)

- **Définition** : Part des adultes qui détiennent un compte dans une banque ou une institution financière similaire, ou un compte de monnaie mobile.
  <br><sub>Source (EN) : Share of adults owning a bank or similar financial-institution account or a mobile-money account.</sub>
- **Formule** : `100 * value` depuis `fact` (`account_t_d`)
- **Unité** : percent
- **Dénominateur** : Ensemble des adultes de 15 ans et plus interrogés ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : all surveyed adults aged 15+ (survey_weighted_population_share)</sub>
- **Code source** : findex `account_t_d` (indicateur officiel `account`)
- **Années valides** : 2011, 2014, 2017, 2021, 2022, 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_book`, `etl_contract` ; recalcul A1 : conforme ; 36 lignes (33 approuvées, 3 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Detailed historical questionnaire comparability has not been independently reverified.

### Densité des agences des banques commerciales (`branch_density`)

- **Définition** : Nombre d'agences des banques commerciales pour 100 000 adultes, tel que publié par le FAS du FMI.
  <br><sub>Source (EN) : Number of commercial-bank branches per 100000 adults, as reported by IMF FAS.</sub>
- **Formule** : `value` depuis `fact` (`branch_density`)
- **Unité** : per_100k_adults
- **Dénominateur** : Population adulte retenue par le FAS ; nombre publié pour 100 000 adultes.
  <br><sub>Source (EN) : adult population used by FAS (published_count_per_100000_adults)</sub>
- **Code source** : fas `FA26N.PHTADLT_NUM`
- **Années valides** : 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024
- **Vérification** : statut `verified_metadata` ; preuves : `fas_raw_metadata`, `etl_contract` ; recalcul A1 : conforme ; 84 lignes (84 approuvées, 0 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Exact adult-age convention and national reporting breaks require FAS methodology review before cross-country rollups.

### Paiement numérique effectué ou reçu (`digital_payment_rate`)

- **Définition** : Part des adultes qui ont effectué ou reçu un paiement numérique au cours de l'année écoulée, pour les motifs de paiement retenus par le Findex.
  <br><sub>Source (EN) : Share of adults who made or received a digital payment in the past year, across the payment purposes included by Findex.</sub>
- **Formule** : `100 * value` depuis `fact` (`g20_any`)
- **Unité** : percent
- **Dénominateur** : Ensemble des adultes de 15 ans et plus interrogés ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : all surveyed adults aged 15+ (survey_weighted_population_share)</sub>
- **Code source** : findex `g20_any` (indicateur officiel `g20.any`)
- **Années valides** : 2014, 2017, 2021, 2022, 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary`, `etl_contract` ; recalcul A1 : conforme ; 30 lignes (28 approuvées, 2 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Detailed historical questionnaire comparability has not been independently reverified.

### Épargne (toute forme) (`saving_rate`)

- **Définition** : Part des adultes qui ont personnellement épargné ou mis de l'argent de côté, pour quelque raison et par quelque moyen d'épargne que ce soit, au cours de l'année écoulée.
  <br><sub>Source (EN) : Share of adults who personally saved or set aside any money, for any reason and using any mode of saving, in the past year.</sub>
- **Formule** : `100 * value` depuis `fact` (`save_any_t_d`)
- **Unité** : percent
- **Dénominateur** : Ensemble des adultes de 15 ans et plus interrogés ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : all surveyed adults aged 15+ (survey_weighted_population_share)</sub>
- **Code source** : findex `save_any_t_d` (indicateur officiel `save.any.t.d`)
- **Années valides** : 2014, 2017, 2021, 2022, 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary_save_any`, `etl_contract` ; recalcul A1 : conforme ; 30 lignes (28 approuvées, 2 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Detailed historical questionnaire comparability has not been independently reverified. Includes informal saving; formal_saving_rate covers saving at a financial institution only.

### Emprunt (toute forme) (`borrowing_rate`)

- **Définition** : Part des adultes qui ont emprunté de l'argent, seuls ou avec quelqu'un d'autre, pour quelque raison et auprès de quelque source que ce soit, au cours de l'année écoulée.
  <br><sub>Source (EN) : Share of adults who borrowed any money, alone or together with someone else, for any reason and from any source in the past year.</sub>
- **Formule** : `100 * value` depuis `fact` (`borrow_any_t_d`)
- **Unité** : percent
- **Dénominateur** : Ensemble des adultes de 15 ans et plus interrogés ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : all surveyed adults aged 15+ (survey_weighted_population_share)</sub>
- **Code source** : findex `borrow_any_t_d` (indicateur officiel `borrow.any.t.d`)
- **Années valides** : 2014, 2017, 2021, 2022, 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary_borrow_any`, `etl_contract` ; recalcul A1 : conforme ; 30 lignes (28 approuvées, 2 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Detailed historical questionnaire comparability has not been independently reverified. Includes informal lenders (family, friends, savings clubs); formal_borrowing_rate covers financial institutions only.

### Adultes sans compte (`unbanked_share`)

- **Définition** : Complément de la détention d'un compte dans la même population et la même année ; comprend les adultes qui n'ont ni compte bancaire ou assimilé, ni monnaie mobile.
  <br><sub>Source (EN) : Complement of account ownership in the same population and year; includes adults with neither a bank/similar account nor mobile money.</sub>
- **Formule** : `100 * (1 - value)` depuis `fact` (`account_t_d`) ; dépendances : `account_ownership`
- **Unité** : percent
- **Dénominateur** : Ensemble des adultes de 15 ans et plus interrogés ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : all surveyed adults aged 15+ (survey_weighted_population_share)</sub>
- **Code source** : findex `account_t_d`
- **Années valides** : 2011, 2014, 2017, 2021, 2022, 2024
- **Vérification** : statut `derived_verified` ; preuves : `findex_2025_book`, `etl_contract` ; recalcul A1 : conforme ; 36 lignes (33 approuvées, 3 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Measures account exclusion only; does not establish broader financial vulnerability or resilience.

### Épargne auprès d'une institution financière (`formal_saving_rate`)

- **Définition** : Part des adultes qui ont épargné ou mis de l'argent de côté dans une banque ou une institution financière similaire au cours de l'année écoulée.
  <br><sub>Source (EN) : Share of adults who saved or set aside any money at a bank or similar financial institution in the past year.</sub>
- **Formule** : `100 * value` depuis `fact` (`fin17a`)
- **Unité** : percent
- **Dénominateur** : Ensemble des adultes de 15 ans et plus interrogés ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : all surveyed adults aged 15+ (survey_weighted_population_share)</sub>
- **Code source** : findex `fin17a` (indicateur officiel `fin17a`)
- **Années valides** : 2011, 2014, 2017, 2021, 2022, 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary_fin17a`, `etl_contract` ; recalcul A1 : conforme ; 36 lignes (33 approuvées, 3 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Detailed historical questionnaire comparability has not been independently reverified. Excludes saving with a mobile money account (fin17b) and informal saving; not the any-saving measure (saving_rate).

### Emprunt auprès d'une institution financière (`formal_borrowing_rate`)

- **Définition** : Part des adultes qui ont emprunté de l'argent auprès d'une banque ou d'une institution financière similaire, ou au moyen d'une carte de crédit, au cours de l'année écoulée.
  <br><sub>Source (EN) : Share of adults who borrowed any money from a bank or similar financial institution, or using a credit card, in the past year.</sub>
- **Formule** : `100 * value` depuis `fact` (`fin22a`)
- **Unité** : percent
- **Dénominateur** : Ensemble des adultes de 15 ans et plus interrogés ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : all surveyed adults aged 15+ (survey_weighted_population_share)</sub>
- **Code source** : findex `fin22a` (indicateur officiel `fin22a`)
- **Années valides** : 2014, 2017, 2021, 2022, 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary_fin22a`, `etl_contract` ; recalcul A1 : conforme ; 30 lignes (28 approuvées, 2 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Detailed historical questionnaire comparability has not been independently reverified. The official definition includes borrowing using a credit card; it excludes mobile-money borrowing (fin22a.22a1.22g.d) and informal lenders.

### Écart femmes-hommes de détention d'un compte (`gender_gap`)

- **Définition** : Détention d'un compte des hommes moins détention d'un compte des femmes, même pays et même année d'enquête, en points de pourcentage.
  <br><sub>Source (EN) : Account ownership of men minus account ownership of women, same country and survey year, in percentage points.</sub>
- **Formule** : `100 * (value[men] - value[women])` depuis `fact` (`account_t_d`)
- **Unité** : percentage_points
- **Dénominateur** : Adultes de 15 ans et plus de chacun des sous-groupes comparés ; différence entre les parts pondérées des sous-groupes.
  <br><sub>Source (EN) : adults aged 15+ in each compared subgroup (difference_of_survey_weighted_subgroup_shares)</sub>
- **Code source** : findex `account_t_d` (indicateur officiel `account.t.d`)
- **Années valides** : 2011, 2014, 2017, 2021, 2022, 2024
- **Vérification** : statut `derived_verified` ; preuves : `findex_2025_book`, `findex_subgroups`, `etl_contract` ; recalcul A1 : conforme ; 36 lignes (33 approuvées, 3 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Difference of two survey estimates; sampling error of each subgroup is not propagated. Detailed historical questionnaire comparability has not been independently reverified.

### Écart de revenu de détention d'un compte (`income_gap`)

- **Définition** : Détention d'un compte des 60 % des ménages les plus riches moins celle des 40 % les plus pauvres, même pays et même année d'enquête, en points de pourcentage.
  <br><sub>Source (EN) : Account ownership of the richest 60% minus the poorest 40% of households, same country and survey year, in percentage points.</sub>
- **Formule** : `100 * (value[richest 60%] - value[poorest 40%])` depuis `fact` (`account_t_d`)
- **Unité** : percentage_points
- **Dénominateur** : Adultes de 15 ans et plus de chacun des sous-groupes comparés ; différence entre les parts pondérées des sous-groupes.
  <br><sub>Source (EN) : adults aged 15+ in each compared subgroup (difference_of_survey_weighted_subgroup_shares)</sub>
- **Code source** : findex `account_t_d` (indicateur officiel `account.t.d`)
- **Années valides** : 2011, 2014, 2017, 2021, 2022, 2024
- **Vérification** : statut `derived_verified` ; preuves : `findex_2025_book`, `findex_subgroups`, `etl_contract` ; recalcul A1 : conforme ; 36 lignes (33 approuvées, 3 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Difference of two survey estimates; sampling error of each subgroup is not propagated. Detailed historical questionnaire comparability has not been independently reverified.

### Écart d'âge de détention d'un compte (`age_gap`)

- **Définition** : Détention d'un compte des adultes de 25 ans et plus moins celle des adultes de 15 à 24 ans, même pays et même année d'enquête, en points de pourcentage.
  <br><sub>Source (EN) : Account ownership of adults aged 25+ minus adults aged 15-24, same country and survey year, in percentage points.</sub>
- **Formule** : `100 * (value[age 25+] - value[ages 15-24])` depuis `fact` (`account_t_d`)
- **Unité** : percentage_points
- **Dénominateur** : Adultes de 15 ans et plus de chacun des sous-groupes comparés ; différence entre les parts pondérées des sous-groupes.
  <br><sub>Source (EN) : adults aged 15+ in each compared subgroup (difference_of_survey_weighted_subgroup_shares)</sub>
- **Code source** : findex `account_t_d` (indicateur officiel `account.t.d`)
- **Années valides** : 2011, 2014, 2017, 2021, 2022, 2024
- **Vérification** : statut `derived_verified` ; preuves : `findex_2025_book`, `findex_subgroups`, `etl_contract` ; recalcul A1 : conforme ; 36 lignes (33 approuvées, 3 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Difference of two survey estimates; sampling error of each subgroup is not propagated. Detailed historical questionnaire comparability has not been independently reverified.

### Densité des distributeurs automatiques (`atm_density`)

- **Définition** : Nombre de distributeurs automatiques de billets (DAB) pour 100 000 adultes, tel que publié par le FAS du FMI.
  <br><sub>Source (EN) : Number of automated teller machines (ATMs) per 100000 adults, as reported by IMF FAS.</sub>
- **Formule** : `value` depuis `fact` (`atm_density`)
- **Unité** : per_100k_adults
- **Dénominateur** : Population adulte retenue par le FAS ; nombre publié pour 100 000 adultes.
  <br><sub>Source (EN) : adult population used by FAS (published_count_per_100000_adults)</sub>
- **Code source** : fas `FA18N.PHTADLT_NUM`
- **Années valides** : 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024
- **Vérification** : statut `verified_metadata` ; preuves : `fas_raw_metadata_atm_density`, `etl_contract` ; recalcul A1 : conforme ; 84 lignes (84 approuvées, 0 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Exact adult-age convention and national reporting breaks require FAS methodology review before cross-country rollups. FA18N counts all ATMs; the warehouse stores every FAS row under bank_type=commercial_banks, a storage convention, not a restriction of the series.

### Déposants des banques commerciales (`depositors_per_1k`)

- **Définition** : Nombre de déposants des banques commerciales pour 1 000 adultes, tel que publié par le FAS du FMI.
  <br><sub>Source (EN) : Number of depositors with commercial banks per 1000 adults, as reported by IMF FAS.</sub>
- **Formule** : `value` depuis `fact` (`depositors_per_1k`)
- **Unité** : per_1k_adults
- **Dénominateur** : Population adulte retenue par le FAS ; nombre publié pour 1 000 adultes.
  <br><sub>Source (EN) : adult population used by FAS (published_count_per_1000_adults)</sub>
- **Code source** : fas `FA29N_COMBANK.PTADLT_NUM`
- **Années valides** : 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024
- **Vérification** : statut `verified_metadata` ; preuves : `fas_raw_metadata_depositors_per_1k`, `etl_contract` ; recalcul A1 : conforme ; 84 lignes (70 approuvées, 14 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Exact adult-age convention and national reporting breaks require FAS methodology review before cross-country rollups.

### Emprunteurs des banques commerciales (`borrowers_per_1k`)

- **Définition** : Nombre d'emprunteurs des banques commerciales pour 1 000 adultes, tel que publié par le FAS du FMI.
  <br><sub>Source (EN) : Number of borrowers from commercial banks per 1000 adults, as reported by IMF FAS.</sub>
- **Formule** : `value` depuis `fact` (`borrowers_per_1k`)
- **Unité** : per_1k_adults
- **Dénominateur** : Population adulte retenue par le FAS ; nombre publié pour 1 000 adultes.
  <br><sub>Source (EN) : adult population used by FAS (published_count_per_1000_adults)</sub>
- **Code source** : fas `FA21N_COMBANK.PTADLT_NUM`
- **Années valides** : 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024
- **Vérification** : statut `verified_metadata` ; preuves : `fas_raw_metadata_borrowers_per_1k`, `etl_contract` ; recalcul A1 : conforme ; 84 lignes (70 approuvées, 14 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Exact adult-age convention and national reporting breaks require FAS methodology review before cross-country rollups.

### Comptes de dépôt des banques commerciales (`deposit_accounts_per_1k`)

- **Définition** : Nombre de comptes de dépôt dans les banques commerciales pour 1 000 adultes, tel que publié par le FAS du FMI.
  <br><sub>Source (EN) : Number of deposit accounts with commercial banks per 1000 adults, as reported by IMF FAS.</sub>
- **Formule** : `value` depuis `fact` (`deposit_accounts_per_1k`)
- **Unité** : per_1k_adults
- **Dénominateur** : Population adulte retenue par le FAS ; nombre publié pour 1 000 adultes.
  <br><sub>Source (EN) : adult population used by FAS (published_count_per_1000_adults)</sub>
- **Code source** : fas `FA30N_COMBANK.PTADLT_NUM`
- **Années valides** : 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024
- **Vérification** : statut `verified_metadata` ; preuves : `fas_raw_metadata_deposit_accounts_per_1k`, `etl_contract` ; recalcul A1 : conforme ; 84 lignes (84 approuvées, 0 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Exact adult-age convention and national reporting breaks require FAS methodology review before cross-country rollups.

### Comptes de prêt des banques commerciales (`loan_accounts_per_1k`)

- **Définition** : Nombre de comptes de prêt dans les banques commerciales pour 1 000 adultes, tel que publié par le FAS du FMI.
  <br><sub>Source (EN) : Number of loan accounts with commercial banks per 1000 adults, as reported by IMF FAS.</sub>
- **Formule** : `value` depuis `fact` (`loan_accounts_per_1k`)
- **Unité** : per_1k_adults
- **Dénominateur** : Population adulte retenue par le FAS ; nombre publié pour 1 000 adultes.
  <br><sub>Source (EN) : adult population used by FAS (published_count_per_1000_adults)</sub>
- **Code source** : fas `LOANACCN_COMBANK.PTADLT_NUM`
- **Années valides** : 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024
- **Vérification** : statut `verified_metadata` ; preuves : `fas_raw_metadata_loan_accounts_per_1k`, `etl_contract` ; recalcul A1 : conforme ; 84 lignes (80 approuvées, 4 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Exact adult-age convention and national reporting breaks require FAS methodology review before cross-country rollups.

### Encours des dépôts des banques commerciales (`deposits_pct_gdp`)

- **Définition** : Encours des dépôts dans les banques commerciales en pourcentage du PIB, tel que publié par le FAS du FMI (ratio non recalculé).
  <br><sub>Source (EN) : Outstanding deposits with commercial banks as a percentage of GDP, as published by IMF FAS (ratio not recomputed).</sub>
- **Formule** : `value` depuis `fact` (`deposits_pct_gdp`)
- **Unité** : percent_of_gdp
- **Dénominateur** : PIB du même pays et de la même année, tel qu'utilisé par le FAS ; ratio au PIB publié.
  <br><sub>Source (EN) : GDP of the same country and year, as used by FAS (published_ratio_to_gdp)</sub>
- **Code source** : fas `OUTD_COMBANK.POGDP`
- **Années valides** : 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024
- **Vérification** : statut `verified_metadata` ; preuves : `fas_raw_metadata_deposits_pct_gdp`, `etl_contract` ; recalcul A1 : conforme ; 84 lignes (84 approuvées, 0 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Exact adult-age convention and national reporting breaks require FAS methodology review before cross-country rollups. Values above quality.fas_pct_gdp_threshold are flagged by the fas_pct_gdp_plausibility diagnostic; only those rows require review.

### Encours des prêts des banques commerciales (`loans_pct_gdp`)

- **Définition** : Encours des prêts des banques commerciales en pourcentage du PIB, tel que publié par le FAS du FMI (ratio non recalculé).
  <br><sub>Source (EN) : Outstanding loans from commercial banks as a percentage of GDP, as published by IMF FAS (ratio not recomputed).</sub>
- **Formule** : `value` depuis `fact` (`loans_pct_gdp`)
- **Unité** : percent_of_gdp
- **Dénominateur** : PIB du même pays et de la même année, tel qu'utilisé par le FAS ; ratio au PIB publié.
  <br><sub>Source (EN) : GDP of the same country and year, as used by FAS (published_ratio_to_gdp)</sub>
- **Code source** : fas `OUTL_COMBANK.POGDP`
- **Années valides** : 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024
- **Vérification** : statut `verified_metadata` ; preuves : `fas_raw_metadata_loans_pct_gdp`, `etl_contract` ; recalcul A1 : conforme ; 84 lignes (84 approuvées, 0 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Exact adult-age convention and national reporting breaks require FAS methodology review before cross-country rollups. Values above quality.fas_pct_gdp_threshold are flagged by the fas_pct_gdp_plausibility diagnostic; only those rows require review.

### Fonds d'urgence mobilisables en 30 jours (`emergency_funds`)

- **Définition** : Part des adultes qui déclarent qu'il leur est possible (difficile, assez difficile ou pas très difficile) de réunir des fonds d'urgence en 30 jours.
  <br><sub>Source (EN) : Share of adults who say it is possible (difficult, somewhat difficult or not very difficult) for them to come up with emergency funds within 30 days.</sub>
- **Formule** : `100 * value` depuis `fact` (`fin24aP`)
- **Unité** : percent
- **Dénominateur** : Ensemble des adultes de 15 ans et plus interrogés ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : all surveyed adults aged 15+ (survey_weighted_population_share)</sub>
- **Code source** : findex `fin24aP` (indicateur officiel `fin24aP`)
- **Années valides** : 2014, 2017, 2021, 2022, 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary_fin24aP`, `etl_contract` ; recalcul A1 : conforme ; 30 lignes (28 approuvées, 2 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Detailed historical questionnaire comparability has not been independently reverified. The emergency amount follows the Findex questionnaire of each wave; values are not converted across waves.

### Source principale des fonds d'urgence : épargne (`emergency_source_savings`)

- **Définition** : Part de l'ensemble des adultes qui déclarent pouvoir réunir des fonds d'urgence en 30 jours et citent l'épargne comme source principale.
  <br><sub>Source (EN) : Share of all adults who say they could come up with emergency funds in 30 days and name savings as their main source.</sub>
- **Formule** : `100 * value` depuis `fact` (`fin24sav`)
- **Unité** : percent
- **Dénominateur** : Ensemble des adultes de 15 ans et plus interrogés ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : all surveyed adults aged 15+ (survey_weighted_population_share)</sub>
- **Code source** : findex `fin24sav` (indicateur officiel `fin24sav`)
- **Années valides** : 2021, 2022, 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary_fin24sav`, `etl_contract` ; recalcul A1 : conforme ; 18 lignes (17 approuvées, 1 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : The denominator is all adults aged 15+, not only adults able to raise emergency funds. Only the main source is recorded; sources are mutually exclusive within one wave.

### Source principale des fonds d'urgence : prêt (banque, employeur ou prêteur privé) (`emergency_source_borrowing`)

- **Définition** : Part de l'ensemble des adultes qui déclarent pouvoir réunir des fonds d'urgence en 30 jours et citent comme source principale un prêt d'une banque, d'un employeur ou d'un prêteur privé.
  <br><sub>Source (EN) : Share of all adults who say they could come up with emergency funds in 30 days and name a loan from a bank, employer or private lender as their main source.</sub>
- **Formule** : `100 * value` depuis `fact` (`fin24bor`)
- **Unité** : percent
- **Dénominateur** : Ensemble des adultes de 15 ans et plus interrogés ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : all surveyed adults aged 15+ (survey_weighted_population_share)</sub>
- **Code source** : findex `fin24bor` (indicateur officiel `fin24bor`)
- **Années valides** : 2021, 2022, 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary_fin24bor`, `etl_contract` ; recalcul A1 : conforme ; 18 lignes (17 approuvées, 1 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : The denominator is all adults aged 15+, not only adults able to raise emergency funds. Excludes family or friends (fin24fam), which Findex records as a separate source.

### Compte de monnaie mobile (`mobile_money_account`)

- **Définition** : Part des adultes qui déclarent avoir personnellement utilisé un service de monnaie mobile au cours de l'année écoulée.
  <br><sub>Source (EN) : Share of adults who report personally using a mobile money service in the past year.</sub>
- **Formule** : `100 * value` depuis `fact` (`mobileaccount_t_d`)
- **Unité** : percent
- **Dénominateur** : Ensemble des adultes de 15 ans et plus interrogés ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : all surveyed adults aged 15+ (survey_weighted_population_share)</sub>
- **Code source** : findex `mobileaccount_t_d` (indicateur officiel `mobileaccount.t.d`)
- **Années valides** : 2014, 2017, 2021, 2022, 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary_mobileaccount`, `etl_contract` ; recalcul A1 : conforme ; 30 lignes (25 approuvées, 5 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Defined by use of a mobile money service in the past year, not by registration alone. Detailed historical questionnaire comparability has not been independently reverified.

### Compte inactif (`inactive_accounts`)

- **Définition** : Part de l'ensemble des adultes qui ont un compte mais ne déclarent ni dépôt ni retrait sur ce compte (paiement numérique compris) au cours de l'année écoulée.
  <br><sub>Source (EN) : Share of all adults who have an account but report neither a deposit into nor a withdrawal from it (including any digital payment) in the past year.</sub>
- **Formule** : `100 * value` depuis `fact` (`inactive_t_d`)
- **Unité** : percent
- **Dénominateur** : Ensemble des adultes de 15 ans et plus interrogés ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : all surveyed adults aged 15+ (survey_weighted_population_share)</sub>
- **Code source** : findex `inactive_t_d` (indicateur officiel `inactive.t.d`)
- **Années valides** : 2014, 2017, 2021, 2022, 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary_inactive`, `etl_contract` ; recalcul A1 : conforme ; 30 lignes (28 approuvées, 2 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : The denominator is all adults aged 15+, not account owners only. Detailed historical questionnaire comparability has not been independently reverified.

### Détention d'un compte - femmes (`account_ownership_women`)

- **Définition** : Part des femmes qui détiennent un compte dans une banque ou une institution financière similaire, ou un compte de monnaie mobile.
  <br><sub>Source (EN) : Share of women who own a bank or similar financial-institution account or a mobile-money account.</sub>
- **Formule** : `100 * value` depuis `fact` (`account_t_d`)
- **Unité** : percent
- **Dénominateur** : Adultes de 15 ans et plus interrogés du sous-groupe « femmes » ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : surveyed adults aged 15+ in the subgroup gender = women (survey_weighted_population_share)</sub>
- **Code source** : findex `account_t_d` (indicateur officiel `account.t.d`)
- **Années valides** : 2011, 2014, 2017, 2021, 2022, 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary_account`, `findex_subgroups`, `etl_contract` ; recalcul A1 : conforme ; 36 lignes (33 approuvées, 3 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Subgroup survey estimate; its sampling error is larger than the total-population estimate and is not propagated. Detailed historical questionnaire comparability has not been independently reverified.

### Détention d'un compte - hommes (`account_ownership_men`)

- **Définition** : Part des hommes qui détiennent un compte dans une banque ou une institution financière similaire, ou un compte de monnaie mobile.
  <br><sub>Source (EN) : Share of men who own a bank or similar financial-institution account or a mobile-money account.</sub>
- **Formule** : `100 * value` depuis `fact` (`account_t_d`)
- **Unité** : percent
- **Dénominateur** : Adultes de 15 ans et plus interrogés du sous-groupe « hommes » ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : surveyed adults aged 15+ in the subgroup gender = men (survey_weighted_population_share)</sub>
- **Code source** : findex `account_t_d` (indicateur officiel `account.t.d`)
- **Années valides** : 2011, 2014, 2017, 2021, 2022, 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary_account`, `findex_subgroups`, `etl_contract` ; recalcul A1 : conforme ; 36 lignes (33 approuvées, 3 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Subgroup survey estimate; its sampling error is larger than the total-population estimate and is not propagated. Detailed historical questionnaire comparability has not been independently reverified.

### Détention d'un compte - 40 % des ménages les plus pauvres (`account_ownership_poorest_40`)

- **Définition** : Part des 40 % des ménages les plus pauvres qui détiennent un compte dans une banque ou une institution financière similaire, ou un compte de monnaie mobile.
  <br><sub>Source (EN) : Share of the poorest 40% of households who own a bank or similar financial-institution account or a mobile-money account.</sub>
- **Formule** : `100 * value` depuis `fact` (`account_t_d`)
- **Unité** : percent
- **Dénominateur** : Adultes de 15 ans et plus interrogés du sous-groupe « 40 % des ménages les plus pauvres » ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : surveyed adults aged 15+ in the subgroup income = poorest 40% (survey_weighted_population_share)</sub>
- **Code source** : findex `account_t_d` (indicateur officiel `account.t.d`)
- **Années valides** : 2011, 2014, 2017, 2021, 2022, 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary_account`, `findex_subgroups`, `etl_contract` ; recalcul A1 : conforme ; 36 lignes (33 approuvées, 3 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Subgroup survey estimate; its sampling error is larger than the total-population estimate and is not propagated. Detailed historical questionnaire comparability has not been independently reverified.

### Détention d'un compte - 60 % des ménages les plus riches (`account_ownership_richest_60`)

- **Définition** : Part des 60 % des ménages les plus riches qui détiennent un compte dans une banque ou une institution financière similaire, ou un compte de monnaie mobile.
  <br><sub>Source (EN) : Share of the richest 60% of households who own a bank or similar financial-institution account or a mobile-money account.</sub>
- **Formule** : `100 * value` depuis `fact` (`account_t_d`)
- **Unité** : percent
- **Dénominateur** : Adultes de 15 ans et plus interrogés du sous-groupe « 60 % des ménages les plus riches » ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : surveyed adults aged 15+ in the subgroup income = richest 60% (survey_weighted_population_share)</sub>
- **Code source** : findex `account_t_d` (indicateur officiel `account.t.d`)
- **Années valides** : 2011, 2014, 2017, 2021, 2022, 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary_account`, `findex_subgroups`, `etl_contract` ; recalcul A1 : conforme ; 36 lignes (33 approuvées, 3 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Subgroup survey estimate; its sampling error is larger than the total-population estimate and is not propagated. Detailed historical questionnaire comparability has not been independently reverified.

### Détention d'un compte - adultes de 15 à 24 ans (`account_ownership_age_15_24`)

- **Définition** : Part des adultes de 15 à 24 ans qui détiennent un compte dans une banque ou une institution financière similaire, ou un compte de monnaie mobile.
  <br><sub>Source (EN) : Share of adults aged 15-24 who own a bank or similar financial-institution account or a mobile-money account.</sub>
- **Formule** : `100 * value` depuis `fact` (`account_t_d`)
- **Unité** : percent
- **Dénominateur** : Adultes de 15 ans et plus interrogés du sous-groupe « adultes de 15 à 24 ans » ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : surveyed adults aged 15+ in the subgroup age_cat = ages 15-24 (survey_weighted_population_share)</sub>
- **Code source** : findex `account_t_d` (indicateur officiel `account.t.d`)
- **Années valides** : 2011, 2014, 2017, 2021, 2022, 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary_account`, `findex_subgroups`, `etl_contract` ; recalcul A1 : conforme ; 36 lignes (33 approuvées, 3 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Subgroup survey estimate; its sampling error is larger than the total-population estimate and is not propagated. Detailed historical questionnaire comparability has not been independently reverified.

### Détention d'un compte - adultes de 25 ans et plus (`account_ownership_age_25_plus`)

- **Définition** : Part des adultes de 25 ans et plus qui détiennent un compte dans une banque ou une institution financière similaire, ou un compte de monnaie mobile.
  <br><sub>Source (EN) : Share of adults aged 25+ who own a bank or similar financial-institution account or a mobile-money account.</sub>
- **Formule** : `100 * value` depuis `fact` (`account_t_d`)
- **Unité** : percent
- **Dénominateur** : Adultes de 15 ans et plus interrogés du sous-groupe « adultes de 25 ans et plus » ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : surveyed adults aged 15+ in the subgroup age_cat = age 25+ (survey_weighted_population_share)</sub>
- **Code source** : findex `account_t_d` (indicateur officiel `account.t.d`)
- **Années valides** : 2011, 2014, 2017, 2021, 2022, 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary_account`, `findex_subgroups`, `etl_contract` ; recalcul A1 : conforme ; 36 lignes (33 approuvées, 3 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Subgroup survey estimate; its sampling error is larger than the total-population estimate and is not propagated. Detailed historical questionnaire comparability has not been independently reverified.

### Détention d'un compte - niveau primaire ou moins (`account_ownership_primary_or_less`)

- **Définition** : Part des adultes de niveau d'études primaire ou moins qui détiennent un compte dans une banque ou une institution financière similaire, ou un compte de monnaie mobile.
  <br><sub>Source (EN) : Share of adults with primary education or less who own a bank or similar financial-institution account or a mobile-money account.</sub>
- **Formule** : `100 * value` depuis `fact` (`account_t_d`)
- **Unité** : percent
- **Dénominateur** : Adultes de 15 ans et plus interrogés du sous-groupe « niveau primaire ou moins » ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : surveyed adults aged 15+ in the subgroup education = prim edu or less (survey_weighted_population_share)</sub>
- **Code source** : findex `account_t_d` (indicateur officiel `account.t.d`)
- **Années valides** : 2011, 2014, 2017, 2021, 2022, 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary_account`, `findex_subgroups_extended`, `etl_contract` ; recalcul A1 : conforme ; 36 lignes (33 approuvées, 3 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Subgroup survey estimate; its sampling error is larger than the total-population estimate and is not propagated. Detailed historical questionnaire comparability has not been independently reverified.

### Détention d'un compte - niveau secondaire ou plus (`account_ownership_secondary_or_more`)

- **Définition** : Part des adultes de niveau d'études secondaire ou plus qui détiennent un compte dans une banque ou une institution financière similaire, ou un compte de monnaie mobile.
  <br><sub>Source (EN) : Share of adults with secondary education or more who own a bank or similar financial-institution account or a mobile-money account.</sub>
- **Formule** : `100 * value` depuis `fact` (`account_t_d`)
- **Unité** : percent
- **Dénominateur** : Adultes de 15 ans et plus interrogés du sous-groupe « niveau secondaire ou plus » ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : surveyed adults aged 15+ in the subgroup education = secondary edu or more (survey_weighted_population_share)</sub>
- **Code source** : findex `account_t_d` (indicateur officiel `account.t.d`)
- **Années valides** : 2011, 2014, 2017, 2021, 2022, 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary_account`, `findex_subgroups_extended`, `etl_contract` ; recalcul A1 : conforme ; 36 lignes (33 approuvées, 3 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Subgroup survey estimate; its sampling error is larger than the total-population estimate and is not propagated. Detailed historical questionnaire comparability has not been independently reverified.

### Détention d'un compte - hors population active (`account_ownership_out_of_laborforce`)

- **Définition** : Part des adultes hors population active qui détiennent un compte dans une banque ou une institution financière similaire, ou un compte de monnaie mobile.
  <br><sub>Source (EN) : Share of adults out of the labor force who own a bank or similar financial-institution account or a mobile-money account.</sub>
- **Formule** : `100 * value` depuis `fact` (`account_t_d`)
- **Unité** : percent
- **Dénominateur** : Adultes de 15 ans et plus interrogés du sous-groupe « hors population active » ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : surveyed adults aged 15+ in the subgroup laborforce = out of laborforce (survey_weighted_population_share)</sub>
- **Code source** : findex `account_t_d` (indicateur officiel `account.t.d`)
- **Années valides** : 2011, 2014, 2017, 2021, 2022, 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary_account`, `findex_subgroups_extended`, `etl_contract` ; recalcul A1 : conforme ; 36 lignes (33 approuvées, 3 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Subgroup survey estimate; its sampling error is larger than the total-population estimate and is not propagated. Detailed historical questionnaire comparability has not been independently reverified.

### Détention d'un compte - population active (`account_ownership_in_laborforce`)

- **Définition** : Part des adultes de la population active qui détiennent un compte dans une banque ou une institution financière similaire, ou un compte de monnaie mobile.
  <br><sub>Source (EN) : Share of adults in the labor force who own a bank or similar financial-institution account or a mobile-money account.</sub>
- **Formule** : `100 * value` depuis `fact` (`account_t_d`)
- **Unité** : percent
- **Dénominateur** : Adultes de 15 ans et plus interrogés du sous-groupe « population active » ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : surveyed adults aged 15+ in the subgroup laborforce = in laborforce (survey_weighted_population_share)</sub>
- **Code source** : findex `account_t_d` (indicateur officiel `account.t.d`)
- **Années valides** : 2011, 2014, 2017, 2021, 2022, 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary_account`, `findex_subgroups_extended`, `etl_contract` ; recalcul A1 : conforme ; 36 lignes (33 approuvées, 3 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Subgroup survey estimate; its sampling error is larger than the total-population estimate and is not propagated. Detailed historical questionnaire comparability has not been independently reverified.

### Détention d'un compte - milieu rural (`account_ownership_rural`)

- **Définition** : Part des adultes vivant en milieu rural qui détiennent un compte dans une banque ou une institution financière similaire, ou un compte de monnaie mobile.
  <br><sub>Source (EN) : Share of adults living in rural areas who own a bank or similar financial-institution account or a mobile-money account.</sub>
- **Formule** : `100 * value` depuis `fact` (`account_t_d`)
- **Unité** : percent
- **Dénominateur** : Adultes de 15 ans et plus interrogés du sous-groupe « milieu rural » ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : surveyed adults aged 15+ in the subgroup urbanicity = rural (survey_weighted_population_share)</sub>
- **Code source** : findex `account_t_d` (indicateur officiel `account.t.d`)
- **Années valides** : 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary_account`, `findex_subgroups_extended`, `etl_contract` ; recalcul A1 : conforme ; 6 lignes (6 approuvées, 0 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Subgroup survey estimate; its sampling error is larger than the total-population estimate and is not propagated. Detailed historical questionnaire comparability has not been independently reverified.

### Détention d'un compte - milieu urbain (`account_ownership_urban`)

- **Définition** : Part des adultes vivant en milieu urbain qui détiennent un compte dans une banque ou une institution financière similaire, ou un compte de monnaie mobile.
  <br><sub>Source (EN) : Share of adults living in urban areas who own a bank or similar financial-institution account or a mobile-money account.</sub>
- **Formule** : `100 * value` depuis `fact` (`account_t_d`)
- **Unité** : percent
- **Dénominateur** : Adultes de 15 ans et plus interrogés du sous-groupe « milieu urbain » ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : surveyed adults aged 15+ in the subgroup urbanicity = urban (survey_weighted_population_share)</sub>
- **Code source** : findex `account_t_d` (indicateur officiel `account.t.d`)
- **Années valides** : 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary_account`, `findex_subgroups_extended`, `etl_contract` ; recalcul A1 : conforme ; 6 lignes (6 approuvées, 0 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Subgroup survey estimate; its sampling error is larger than the total-population estimate and is not propagated. Detailed historical questionnaire comparability has not been independently reverified.

### Pas de compte : institutions financières trop éloignées (`barrier_too_far`)

- **Définition** : Part de l'ensemble des adultes (15 ans et plus) qui déclarent ne pas avoir de compte dans une banque ou une institution financière similaire parce que les institutions financières sont trop éloignées. Le dénominateur est l'ensemble des adultes, pas seulement les adultes sans compte ; les comptes de monnaie mobile n'entrent pas dans la question.
  <br><sub>Source (EN) : Share of all adults (aged 15+) who report not having a bank or similar financial-institution account because financial institutions are too far away. The denominator is all adults, not only adults without an account; mobile-money accounts are outside the question.</sub>
- **Formule** : `100 * value` depuis `fact` (`fin11a`)
- **Unité** : percent
- **Dénominateur** : Ensemble des adultes de 15 ans et plus interrogés ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : all surveyed adults aged 15+ (survey_weighted_population_share)</sub>
- **Code source** : findex `fin11a` (indicateur officiel `fin11a`)
- **Années valides** : 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary_fin11a`, `etl_contract` ; recalcul A1 : conforme ; 6 lignes (5 approuvées, 1 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Several reasons can be cited by the same person: barrier shares do not add up to 100% and must never be summed. The reason refers to a bank or similar financial-institution account only; mobile money is excluded. Observed for the 2024 wave only in the local Findex file.

### Pas de compte : services financiers trop chers (`barrier_too_expensive`)

- **Définition** : Part de l'ensemble des adultes (15 ans et plus) qui déclarent ne pas avoir de compte dans une banque ou une institution financière similaire parce que les services financiers sont trop chers. Le dénominateur est l'ensemble des adultes, pas seulement les adultes sans compte ; les comptes de monnaie mobile n'entrent pas dans la question.
  <br><sub>Source (EN) : Share of all adults (aged 15+) who report not having a bank or similar financial-institution account because financial services are too expensive. The denominator is all adults, not only adults without an account; mobile-money accounts are outside the question.</sub>
- **Formule** : `100 * value` depuis `fact` (`fin11b`)
- **Unité** : percent
- **Dénominateur** : Ensemble des adultes de 15 ans et plus interrogés ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : all surveyed adults aged 15+ (survey_weighted_population_share)</sub>
- **Code source** : findex `fin11b` (indicateur officiel `fin11b`)
- **Années valides** : 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary_fin11b`, `etl_contract` ; recalcul A1 : conforme ; 6 lignes (5 approuvées, 1 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Several reasons can be cited by the same person: barrier shares do not add up to 100% and must never be summed. The reason refers to a bank or similar financial-institution account only; mobile money is excluded. Observed for the 2024 wave only in the local Findex file.

### Pas de compte : documents requis manquants (`barrier_no_documents`)

- **Définition** : Part de l'ensemble des adultes (15 ans et plus) qui déclarent ne pas avoir de compte dans une banque ou une institution financière similaire faute des documents nécessaires pour en ouvrir un. Le dénominateur est l'ensemble des adultes, pas seulement les adultes sans compte ; les comptes de monnaie mobile n'entrent pas dans la question.
  <br><sub>Source (EN) : Share of all adults (aged 15+) who report not having a bank or similar financial-institution account because they lack the documentation needed to open one. The denominator is all adults, not only adults without an account; mobile-money accounts are outside the question.</sub>
- **Formule** : `100 * value` depuis `fact` (`fin11c`)
- **Unité** : percent
- **Dénominateur** : Ensemble des adultes de 15 ans et plus interrogés ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : all surveyed adults aged 15+ (survey_weighted_population_share)</sub>
- **Code source** : findex `fin11c` (indicateur officiel `fin11c`)
- **Années valides** : 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary_fin11c`, `etl_contract` ; recalcul A1 : conforme ; 6 lignes (5 approuvées, 1 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Several reasons can be cited by the same person: barrier shares do not add up to 100% and must never be summed. The reason refers to a bank or similar financial-institution account only; mobile money is excluded. Observed for the 2024 wave only in the local Findex file.

### Pas de compte : pas assez d'argent (`barrier_insufficient_funds`)

- **Définition** : Part de l'ensemble des adultes (15 ans et plus) qui déclarent ne pas avoir de compte dans une banque ou une institution financière similaire parce qu'ils n'ont pas assez d'argent pour en utiliser un. Le dénominateur est l'ensemble des adultes, pas seulement les adultes sans compte ; les comptes de monnaie mobile n'entrent pas dans la question.
  <br><sub>Source (EN) : Share of all adults (aged 15+) who report not having a bank or similar financial-institution account because they do not have enough money to use one. The denominator is all adults, not only adults without an account; mobile-money accounts are outside the question.</sub>
- **Formule** : `100 * value` depuis `fact` (`fin11d`)
- **Unité** : percent
- **Dénominateur** : Ensemble des adultes de 15 ans et plus interrogés ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : all surveyed adults aged 15+ (survey_weighted_population_share)</sub>
- **Code source** : findex `fin11d` (indicateur officiel `fin11d`)
- **Années valides** : 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary_fin11d`, `etl_contract` ; recalcul A1 : conforme ; 6 lignes (5 approuvées, 1 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Several reasons can be cited by the same person: barrier shares do not add up to 100% and must never be summed. The reason refers to a bank or similar financial-institution account only; mobile money is excluded. Observed for the 2024 wave only in the local Findex file.

### Pas de compte : un membre de la famille en a déjà un (`barrier_family_has_account`)

- **Définition** : Part de l'ensemble des adultes (15 ans et plus) qui déclarent ne pas avoir de compte dans une banque ou une institution financière similaire parce qu'un autre membre de leur famille en a déjà un. Le dénominateur est l'ensemble des adultes, pas seulement les adultes sans compte ; les comptes de monnaie mobile n'entrent pas dans la question.
  <br><sub>Source (EN) : Share of all adults (aged 15+) who report not having a bank or similar financial-institution account because someone else in their family already has one. The denominator is all adults, not only adults without an account; mobile-money accounts are outside the question.</sub>
- **Formule** : `100 * value` depuis `fact` (`fin11e`)
- **Unité** : percent
- **Dénominateur** : Ensemble des adultes de 15 ans et plus interrogés ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : all surveyed adults aged 15+ (survey_weighted_population_share)</sub>
- **Code source** : findex `fin11e` (indicateur officiel `fin11e`)
- **Années valides** : 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary_fin11e`, `etl_contract` ; recalcul A1 : conforme ; 6 lignes (5 approuvées, 1 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Several reasons can be cited by the same person: barrier shares do not add up to 100% and must never be summed. The reason refers to a bank or similar financial-institution account only; mobile money is excluded. Observed for the 2024 wave only in the local Findex file.

### Pas de compte : manque de confiance dans les institutions financières (`barrier_no_trust`)

- **Définition** : Part de l'ensemble des adultes (15 ans et plus) qui déclarent ne pas avoir de compte dans une banque ou une institution financière similaire parce qu'ils n'ont pas confiance dans les institutions financières. Le dénominateur est l'ensemble des adultes, pas seulement les adultes sans compte ; les comptes de monnaie mobile n'entrent pas dans la question.
  <br><sub>Source (EN) : Share of all adults (aged 15+) who report not having a bank or similar financial-institution account because they do not trust financial institutions. The denominator is all adults, not only adults without an account; mobile-money accounts are outside the question.</sub>
- **Formule** : `100 * value` depuis `fact` (`fin11f`)
- **Unité** : percent
- **Dénominateur** : Ensemble des adultes de 15 ans et plus interrogés ; part pondérée selon le plan de sondage.
  <br><sub>Source (EN) : all surveyed adults aged 15+ (survey_weighted_population_share)</sub>
- **Code source** : findex `fin11f` (indicateur officiel `fin11f`)
- **Années valides** : 2024
- **Vérification** : statut `verified` ; preuves : `findex_2025_glossary_fin11f`, `etl_contract` ; recalcul A1 : conforme ; 6 lignes (5 approuvées, 1 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Several reasons can be cited by the same person: barrier shares do not add up to 100% and must never be summed. The reason refers to a bank or similar financial-institution account only; mobile money is excluded. Observed for the 2024 wave only in the local Findex file.

### Écart d'éducation de détention d'un compte (`education_gap`)

- **Définition** : Détention d'un compte des adultes de niveau d'études secondaire ou plus moins celle des adultes de niveau primaire ou moins, même pays et même année d'enquête, en points de pourcentage.
  <br><sub>Source (EN) : Account ownership of adults with secondary education or more minus adults with primary education or less, same country and survey year, in percentage points.</sub>
- **Formule** : `100 * (value[secondary edu or more] - value[prim edu or less])` depuis `fact` (`account_t_d`)
- **Unité** : percentage_points
- **Dénominateur** : Adultes de 15 ans et plus de chacun des sous-groupes comparés ; différence entre les parts pondérées des sous-groupes.
  <br><sub>Source (EN) : adults aged 15+ in each compared subgroup (difference_of_survey_weighted_subgroup_shares)</sub>
- **Code source** : findex `account_t_d` (indicateur officiel `account.t.d`)
- **Années valides** : 2011, 2014, 2017, 2021, 2022, 2024
- **Vérification** : statut `derived_verified` ; preuves : `findex_2025_glossary_account`, `findex_subgroups_extended`, `etl_contract` ; recalcul A1 : conforme ; 36 lignes (33 approuvées, 3 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Difference of two survey estimates; sampling error of each subgroup is not propagated. Detailed historical questionnaire comparability has not been independently reverified.

### Écart d'activité de détention d'un compte (`laborforce_gap`)

- **Définition** : Détention d'un compte des adultes de la population active moins celle des adultes hors population active, même pays et même année d'enquête, en points de pourcentage.
  <br><sub>Source (EN) : Account ownership of adults in the labor force minus adults out of the labor force, same country and survey year, in percentage points.</sub>
- **Formule** : `100 * (value[in laborforce] - value[out of laborforce])` depuis `fact` (`account_t_d`)
- **Unité** : percentage_points
- **Dénominateur** : Adultes de 15 ans et plus de chacun des sous-groupes comparés ; différence entre les parts pondérées des sous-groupes.
  <br><sub>Source (EN) : adults aged 15+ in each compared subgroup (difference_of_survey_weighted_subgroup_shares)</sub>
- **Code source** : findex `account_t_d` (indicateur officiel `account.t.d`)
- **Années valides** : 2011, 2014, 2017, 2021, 2022, 2024
- **Vérification** : statut `derived_verified` ; preuves : `findex_2025_glossary_account`, `findex_subgroups_extended`, `etl_contract` ; recalcul A1 : conforme ; 36 lignes (33 approuvées, 3 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Difference of two survey estimates; sampling error of each subgroup is not propagated. Detailed historical questionnaire comparability has not been independently reverified.

### Écart urbain-rural de détention d'un compte (`urban_gap`)

- **Définition** : Détention d'un compte des adultes urbains moins celle des adultes ruraux, même pays et même année d'enquête, en points de pourcentage.
  <br><sub>Source (EN) : Account ownership of urban adults minus rural adults, same country and survey year, in percentage points.</sub>
- **Formule** : `100 * (value[urban] - value[rural])` depuis `fact` (`account_t_d`)
- **Unité** : percentage_points
- **Dénominateur** : Adultes de 15 ans et plus de chacun des sous-groupes comparés ; différence entre les parts pondérées des sous-groupes.
  <br><sub>Source (EN) : adults aged 15+ in each compared subgroup (difference_of_survey_weighted_subgroup_shares)</sub>
- **Code source** : findex `account_t_d` (indicateur officiel `account.t.d`)
- **Années valides** : 2024
- **Vérification** : statut `derived_verified` ; preuves : `findex_2025_glossary_account`, `findex_subgroups_extended`, `etl_contract` ; recalcul A1 : conforme ; 6 lignes (6 approuvées, 0 avec réserve, 0 bloquées)
- **Incertitudes déclarées** : Difference of two survey estimates; sampling error of each subgroup is not propagated. Detailed historical questionnaire comparability has not been independently reverified.

## Références des preuves

| Preuve | Localisation | Contenu |
|---|---|---|
| `findex_2025_book` | Glossary, printed page 160, Account | account ownership definition; does not certify every historical questionnaire |
| `findex_2025_glossary` | Glossary!A118:C118, g20.any | made or received a digital payment in the past year, age 15+ |
| `findex_2025_glossary_save_any` | Glossary!A121:C121, save.any.t.d (file retrieved 2026-10-29, sha256 8eb99754e6e18d6831c133cc743d8207cc657baedc3447588a574fd3d935f923) | Saved any money (%, age 15+): personally saving or setting aside any money for any reason and using any mode of saving in the past year |
| `findex_2025_glossary_borrow_any` | Glossary!A3:C3, borrow.any.t.d (file retrieved 2026-10-29, sha256 8eb99754e6e18d6831c133cc743d8207cc657baedc3447588a574fd3d935f923) | Borrowed any money (%, age 15+): borrowing any money (alone or with someone else) for any reason and from any source in the past year |
| `findex_2025_glossary_fin17a` | Glossary!A24:C24, fin17a (file retrieved 2026-10-29, sha256 8eb99754e6e18d6831c133cc743d8207cc657baedc3447588a574fd3d935f923) | Saved at a bank or similar financial institution (%, age 15+): saving or setting aside any money at a bank or similar financial institution in the past year |
| `findex_2025_glossary_fin22a` | Glossary!A31:C31, fin22a (file retrieved 2026-10-29, sha256 8eb99754e6e18d6831c133cc743d8207cc657baedc3447588a574fd3d935f923) | Borrowed from a formal bank or similar financial institution (%, age 15+): borrowing any money from a bank or similar financial institution or using a credit card in the past year |
| `fas_raw_metadata` | SERIES_CODE ending in FA26N.PHTADLT_NUM.A; INDICATOR, TYPE_OF_TRANSFORMATION, FREQUENCY, SCALE | commercial-bank branches, per 100000 adults, annual, units |
| `findex_subgroups` | group/group2 values: gender = men / women; income = richest 60% / poorest 40%; age_cat = age 25+ / ages 15-24 | official Findex subgroup breakdowns of account.t.d, observed for every survey year 2011-2024 |
| `local_dictionary` | FINDEX_LABELS and UNITS | implemented labels and units; not authoritative verification of survey questions |
| `etl_contract` | findex_long, fas_long and PIVOT_SQL | implemented fact and country_year mappings |
| `observed_availability` | total-population rows inspected during the offline real-data audit | observed nonmissing survey years, not a guarantee of coverage for each economy |
| `findex_2025_glossary_account` | Glossary!A2:C2, account.t.d (file retrieved 2026-10-29, sha256 8eb99754e6e18d6831c133cc743d8207cc657baedc3447588a574fd3d935f923) | Account (%, age 15+): The percentage of respondents who report having an account (by themselves or together with someone else) at a bank or similar financial institution or report personally using a mobile money service in the past year |
| `findex_2025_glossary_fin24aP` | Glossary!A44:C44, fin24aP (file retrieved 2026-10-29, sha256 8eb99754e6e18d6831c133cc743d8207cc657baedc3447588a574fd3d935f923) | Coming up with emergency funds in 30 days: possible (%, age 15+): The percentage of respondents who say it is possible--whether difficult, somewhat difficult, or not very difficult--for them to come up with the emergency funds in 30 days |
| `findex_2025_glossary_fin24sav` | Glossary!A34:C34, fin24sav (file retrieved 2026-10-29, sha256 8eb99754e6e18d6831c133cc743d8207cc657baedc3447588a574fd3d935f923) | Main source of emergency funds in 30 days: savings (%, age 15+): The percentage of respondents who say it is possible for them to come up with emergency funds in 30 days and list savings as their main source of emergency funds |
| `findex_2025_glossary_fin24bor` | Glossary!A37:C37, fin24bor (file retrieved 2026-10-29, sha256 8eb99754e6e18d6831c133cc743d8207cc657baedc3447588a574fd3d935f923) | Main source of emergency funds in 30 days: loan from a bank, employer, or private lender (%, age 15+): The percentage of respondents who say it is possible for them to come up with emergency funds in 30 days and list borrowing from a bank, employer, or private lender as their main source of emergency funds |
| `findex_2025_glossary_inactive` | Glossary!A109:C109, inactive.t.d (file retrieved 2026-10-29, sha256 8eb99754e6e18d6831c133cc743d8207cc657baedc3447588a574fd3d935f923) | Has an inactive account (%, age 15+): The percentage of respondents who report neither a deposit into nor a withdrawal from their account in the past year. This also includes making or receiving any kind of digital payment |
| `findex_2025_glossary_mobileaccount` | Glossary!A120:C120, mobileaccount.t.d (file retrieved 2026-10-29, sha256 8eb99754e6e18d6831c133cc743d8207cc657baedc3447588a574fd3d935f923) | Mobile money account (%, age 15+): The percentage of respondents who report personally using a mobile money service in the past year |
| `fas_raw_metadata_atm_density` | SERIES_CODE ending in FA18N.PHTADLT_NUM.A; INDICATOR, TYPE_OF_TRANSFORMATION, FREQUENCY, SCALE | Number of automated teller machines (ATMs), Per 100,000 adults, annual, scale Units |
| `fas_raw_metadata_depositors_per_1k` | SERIES_CODE ending in FA29N_COMBANK.PTADLT_NUM.A; INDICATOR, TYPE_OF_TRANSFORMATION, FREQUENCY, SCALE | Number of depositors, Commercial banks, Per 1,000 adults, annual, scale Units |
| `fas_raw_metadata_borrowers_per_1k` | SERIES_CODE ending in FA21N_COMBANK.PTADLT_NUM.A; INDICATOR, TYPE_OF_TRANSFORMATION, FREQUENCY, SCALE | Number of borrowers, Commercial banks, Per 1,000 adults, annual, scale Units |
| `fas_raw_metadata_deposit_accounts_per_1k` | SERIES_CODE ending in FA30N_COMBANK.PTADLT_NUM.A; INDICATOR, TYPE_OF_TRANSFORMATION, FREQUENCY, SCALE | Number of deposit accounts, Commercial banks, Per 1,000 adults, annual, scale Units |
| `fas_raw_metadata_loan_accounts_per_1k` | SERIES_CODE ending in LOANACCN_COMBANK.PTADLT_NUM.A; INDICATOR, TYPE_OF_TRANSFORMATION, FREQUENCY, SCALE | Number of loan accounts, Commercial banks, Per 1,000 adults, annual, scale Units |
| `fas_raw_metadata_deposits_pct_gdp` | SERIES_CODE ending in OUTD_COMBANK.POGDP.A; INDICATOR, TYPE_OF_TRANSFORMATION, FREQUENCY, SCALE | Outstanding deposits, Commercial banks, Percent of GDP, annual, scale Units |
| `fas_raw_metadata_loans_pct_gdp` | SERIES_CODE ending in OUTL_COMBANK.POGDP.A; INDICATOR, TYPE_OF_TRANSFORMATION, FREQUENCY, SCALE | Outstanding loans, Commercial banks, Percent of GDP, annual, scale Units |
| `findex_subgroups_extended` | group/group2 values: education = prim edu or less / secondary edu or more; laborforce = in laborforce / out of laborforce; urbanicity = rural / urban | official Findex subgroup breakdowns of account.t.d; education and laborforce observed for every survey year 2011-2024, urbanicity for 2024 only |
| `findex_2025_glossary_fin11a` | Glossary!A6:C6, fin11a (file retrieved 2026-10-29, sha256 8eb99754e6e18d6831c133cc743d8207cc657baedc3447588a574fd3d935f923) | No account because bank or similar financial institutions are too far away (%, age 15+): The percentage of respondents who report that they don't have a bank or similar financial institution account because bank or similar financial institutions are too far away |
| `findex_2025_glossary_fin11b` | Glossary!A7:C7, fin11b (file retrieved 2026-10-29, sha256 8eb99754e6e18d6831c133cc743d8207cc657baedc3447588a574fd3d935f923) | No account because financial services are too expensive (%, age 15+): The percentage of respondents who report not having a bank or similar financial institution account because financial services are too expensive |
| `findex_2025_glossary_fin11c` | Glossary!A8:C8, fin11c (file retrieved 2026-10-29, sha256 8eb99754e6e18d6831c133cc743d8207cc657baedc3447588a574fd3d935f923) | No account because of a lack of necessary documentation (%, age 15+): The percentage of respondents who report not having a bank or similar financial institution account because they lack the documentation needed to open one, such as an identity card, a wage slip, or the like |
| `findex_2025_glossary_fin11d` | Glossary!A10:C10, fin11d (file retrieved 2026-10-29, sha256 8eb99754e6e18d6831c133cc743d8207cc657baedc3447588a574fd3d935f923) | No account because of insufficient funds (%, age 15+): The percentage of respondents who report not having a bank or similar financial institution account because they do not have enough money to use one |
| `findex_2025_glossary_fin11e` | Glossary!A11:C11, fin11e (file retrieved 2026-10-29, sha256 8eb99754e6e18d6831c133cc743d8207cc657baedc3447588a574fd3d935f923) | No account because someone in the family has one (%, age 15+): The percentage of respondents who report not having a bank or similar financial institution account because someone else in their family already has one |
| `findex_2025_glossary_fin11f` | Glossary!A9:C9, fin11f (file retrieved 2026-10-29, sha256 8eb99754e6e18d6831c133cc743d8207cc657baedc3447588a574fd3d935f923) | No account because of a lack of trust in bank or similar financial institutions (%, age 15+): The percentage of respondents who report not having a bank or similar financial institution account because they do not trust bank or similar financial institutions |
