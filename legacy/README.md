# legacy/

`legacy/dashboard/` : ancien front React + Vite + ECharts de la Route 2.

**Remplacé par FinOVA (`dashboard_app`)** et retiré du service : il n'est plus
construit, plus servi par l'API, et la Route 1 n'écrit plus dans son dossier
(`dashboard.data_output` = `outputs/dashboard/dashboard.json`). Le code reste dans
le dépôt pour mémoire ; ses tests de sécurité (S4/S5) restent exécutables via
`tests/test_legacy_dashboard_escape.py` (tests Node ignorés sans Node >= 22.6).

Constat d'audit N1 (ECharts < 6.1.0, avis GHSA-fgmj-fm8m-jvvx) : « retiré du
service » — voir `AUDIT_REPORT.md`.
