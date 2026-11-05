# Rapport de qualité des données

- **Généré le** : 2026-11-06T00:05:28
- **Run audité (Route 1)** : `20261105T234338`
- **Snapshot** : `v9`
- **Version du catalogue KPI** : 1.8.0
- **Run Route 2 (spec publiée)** : `route2_20261105T234415620050`
- **Sources lues** : `data/quality/quality_report.json`, `outputs/reports/<run>/quality.json`
- Document généré par `scripts/build_deliverables.py` : ne pas modifier à la main.

## Synthèse

| Mesure | Valeur |
|---|---|
| Run qualité | `20261105T234338` (2026-11-05T23:43:43) |
| Score global | 0,936 |
| Seuil du gate (`quality.score_threshold`) | 0,70 |
| Gate | réussi |
| Anomalies critiques | 0 |
| Anomalies élevées | 0 |
| Anomalies moyennes | 2 |
| Anomalies faibles | 0 |
| Diagnostics (sans effet sur le score) | 25 |
| Durée de l'agent Quality | 2,19 s |

## Score et gate par source

| Source | Lignes | Colonnes | Doublons | Cellules vides | Score | Gate | Anomalies |
|---|---|---|---|---|---|---|---|
| findex | 8 577 | 36 | 0 | 49,01 % | 1,000 | réussi | 0 |
| fas | 32 209 | 57 | 0 | 38,52 % | 0,880 | réussi | 2 |
| gdp | 19 575 | 6 | 0 | 0,53 % | 1,000 | réussi | 0 |

## Anomalies par source

| Source | Code | Sévérité | Message | Nombre |
|---|---|---|---|---|
| fas | `empty_columns` | medium | [fas] 1 colonnes 100 % vides | 1 |
| fas | `negative_values` | medium | [fas] 1 valeurs négatives dans les colonnes années | 1 |

## Diagnostics

Signalements de plausibilité : ils n'entrent ni dans le score ni dans le gate et ne modifient aucune valeur.

| Source | Code | Pays | Année | Indicateur | Valeur | Seuil | Motif |
|---|---|---|---|---|---|---|---|
| fas | `fas_pct_gdp_plausibility` | VEN | 2005 | deposits_pct_gdp | 2 123 506 066 229,76 | 1000.0 | Value exceeds diagnostic threshold of 1000% GDP; review source value, scale and GDP denominator before KPI use. |
| fas | `fas_pct_gdp_plausibility` | VEN | 2006 | deposits_pct_gdp | 2 811 427 372 408,73 | 1000.0 | Value exceeds diagnostic threshold of 1000% GDP; review source value, scale and GDP denominator before KPI use. |
| fas | `fas_pct_gdp_plausibility` | VEN | 2007 | deposits_pct_gdp | 2 855 176 473 357,79 | 1000.0 | Value exceeds diagnostic threshold of 1000% GDP; review source value, scale and GDP denominator before KPI use. |
| fas | `fas_pct_gdp_plausibility` | VEN | 2008 | deposits_pct_gdp | 2 600 205 092 678,51 | 1000.0 | Value exceeds diagnostic threshold of 1000% GDP; review source value, scale and GDP denominator before KPI use. |
| fas | `fas_pct_gdp_plausibility` | VEN | 2009 | deposits_pct_gdp | 2 686 141 816 305,41 | 1000.0 | Value exceeds diagnostic threshold of 1000% GDP; review source value, scale and GDP denominator before KPI use. |
| fas | `fas_pct_gdp_plausibility` | VEN | 2010 | deposits_pct_gdp | 2 558 885 492 356,18 | 1000.0 | Value exceeds diagnostic threshold of 1000% GDP; review source value, scale and GDP denominator before KPI use. |
| fas | `fas_pct_gdp_plausibility` | VEN | 2011 | deposits_pct_gdp | 2 978 174 729 587,81 | 1000.0 | Value exceeds diagnostic threshold of 1000% GDP; review source value, scale and GDP denominator before KPI use. |
| fas | `fas_pct_gdp_plausibility` | VEN | 2012 | deposits_pct_gdp | 3 783 782 846 704,12 | 1000.0 | Value exceeds diagnostic threshold of 1000% GDP; review source value, scale and GDP denominator before KPI use. |
| fas | `fas_pct_gdp_plausibility` | VEN | 2013 | deposits_pct_gdp | 5 107 645 317 147,16 | 1000.0 | Value exceeds diagnostic threshold of 1000% GDP; review source value, scale and GDP denominator before KPI use. |
| fas | `fas_pct_gdp_plausibility` | VEN | 2014 | deposits_pct_gdp | 4 320 208 084 329,59 | 1000.0 | Value exceeds diagnostic threshold of 1000% GDP; review source value, scale and GDP denominator before KPI use. |
| fas | `fas_pct_gdp_plausibility` | VEN | 2015 | deposits_pct_gdp | 3 775 626 464 786,70 | 1000.0 | Value exceeds diagnostic threshold of 1000% GDP; review source value, scale and GDP denominator before KPI use. |
| fas | `fas_pct_gdp_plausibility` | VEN | 2005 | loans_pct_gdp | 1 221 995 466 114,91 | 1000.0 | Value exceeds diagnostic threshold of 1000% GDP; review source value, scale and GDP denominator before KPI use. |
| fas | `fas_pct_gdp_plausibility` | VEN | 2006 | loans_pct_gdp | 1 534 823 139 146,65 | 1000.0 | Value exceeds diagnostic threshold of 1000% GDP; review source value, scale and GDP denominator before KPI use. |
| fas | `fas_pct_gdp_plausibility` | VEN | 2007 | loans_pct_gdp | 2 063 780 132 174,93 | 1000.0 | Value exceeds diagnostic threshold of 1000% GDP; review source value, scale and GDP denominator before KPI use. |
| fas | `fas_pct_gdp_plausibility` | VEN | 2008 | loans_pct_gdp | 1 895 373 096 810,92 | 1000.0 | Value exceeds diagnostic threshold of 1000% GDP; review source value, scale and GDP denominator before KPI use. |
| fas | `fas_pct_gdp_plausibility` | VEN | 2009 | loans_pct_gdp | 1 961 956 424 411,04 | 1000.0 | Value exceeds diagnostic threshold of 1000% GDP; review source value, scale and GDP denominator before KPI use. |
| fas | `fas_pct_gdp_plausibility` | VEN | 2010 | loans_pct_gdp | 1 742 900 562 220,22 | 1000.0 | Value exceeds diagnostic threshold of 1000% GDP; review source value, scale and GDP denominator before KPI use. |
| fas | `fas_pct_gdp_plausibility` | VEN | 2011 | loans_pct_gdp | 1 937 666 098 956,60 | 1000.0 | Value exceeds diagnostic threshold of 1000% GDP; review source value, scale and GDP denominator before KPI use. |
| fas | `fas_pct_gdp_plausibility` | VEN | 2012 | loans_pct_gdp | 2 274 087 909 760,23 | 1000.0 | Value exceeds diagnostic threshold of 1000% GDP; review source value, scale and GDP denominator before KPI use. |
| fas | `fas_pct_gdp_plausibility` | VEN | 2013 | loans_pct_gdp | 2 619 297 008 161,34 | 1000.0 | Value exceeds diagnostic threshold of 1000% GDP; review source value, scale and GDP denominator before KPI use. |
| fas | `fas_pct_gdp_plausibility` | VEN | 2014 | loans_pct_gdp | 2 389 523 830 416,89 | 1000.0 | Value exceeds diagnostic threshold of 1000% GDP; review source value, scale and GDP denominator before KPI use. |
| fas | `fas_pct_gdp_plausibility` | VEN | 2015 | loans_pct_gdp | 2 295 911 493 352,05 | 1000.0 | Value exceeds diagnostic threshold of 1000% GDP; review source value, scale and GDP denominator before KPI use. |
| fas | `fas_pct_gdp_plausibility` | NAM | 2023 | loans_pct_gdp | 2 818,67 | 1000.0 | Value exceeds diagnostic threshold of 1000% GDP; review source value, scale and GDP denominator before KPI use. |
| fas | `fas_pct_gdp_plausibility` | NAM | 2024 | loans_pct_gdp | 3 752,32 | 1000.0 | Value exceeds diagnostic threshold of 1000% GDP; review source value, scale and GDP denominator before KPI use. |
| fas | `fas_pct_gdp_plausibility` | PNG | 2023 | loans_pct_gdp | 20 054,40 | 1000.0 | Value exceeds diagnostic threshold of 1000% GDP; review source value, scale and GDP denominator before KPI use. |

## Sources utilisateur

Aucune source utilisateur contrôlée dans ce run.

### Exclusions

Aucune source utilisateur exclue : les sources officielles ne sont jamais exclues par ce mécanisme.

## Plan de remédiation

Origine : règles déterministes, aucun appel LLM dans ce run.

1. Corriger en priorité les anomalies critiques (clés dupliquées, source vide).
2. Documenter les colonnes structurellement vides au lieu de les supprimer.
3. Verifier les codes pays inconnus et les valeurs hors plage avant l'ETL.
