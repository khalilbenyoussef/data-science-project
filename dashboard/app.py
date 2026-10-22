"""Dashboard Streamlit BIFlow."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.data import (  # noqa: E402
    DashboardDataError,
    KPI_METRIC_COLUMNS,
    available_years,
    country_snapshot,
    coverage_warnings,
    dimension_values,
    kpi_series,
    latest_kpis,
    load_all,
    quality_table,
    top_bottom,
)

st.set_page_config(
    page_title="BIFlow — Inclusion financière",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def get_data() -> dict[str, Any]:
    return load_all()


def _format_value(value: Any, decimals: Any) -> str:
    if pd.isna(value):
        return "—"
    try:
        places = int(decimals)
    except (TypeError, ValueError):
        places = 1
    return f"{float(value):,.{places}f}"


def _format_delta(value: Any) -> float | None:
    if pd.isna(value):
        return None
    return float(value)


def _filter_snapshot(
    snapshot: pd.DataFrame,
    regions: list[str],
    income_groups: list[str],
) -> pd.DataFrame:
    out = snapshot
    if regions and "region" in out.columns:
        out = out[out["region"].isin(regions)]
    if income_groups and "income_group" in out.columns:
        out = out[out["income_group"].isin(income_groups)]
    return out.reset_index(drop=True)


def _quality_badge(quality: dict[str, Any]) -> None:
    score = quality.get("overall_score")
    passed = quality.get("passed")
    critical = quality.get("critical_issues")
    score_text = f"{float(score):.2%}" if score is not None else "—"
    label = "PASS" if passed else "FAIL"
    message = f"Qualité {score_text} — {label} — {critical or 0} anomalie(s) critique(s)"
    if passed:
        st.success(message)
    else:
        st.error(message)


def _kpi_cards(latest: pd.DataFrame, selected_ids: list[str]) -> None:
    rows = latest[latest["id"].isin(selected_ids)].head(5)
    if rows.empty:
        st.info("Aucun KPI à afficher.")
        return
    columns = st.columns(len(rows))
    for column, (_, row) in zip(columns, rows.iterrows()):
        value = _format_value(row["latest_value"], row["decimals"])
        delta = _format_delta(row["change"])
        unit = row["unit"] if pd.notna(row["unit"]) else ""
        column.metric(
            label=str(row["label"]),
            value=f"{value} {unit}".strip(),
            delta=delta,
        )


def _overview(
    data: dict[str, Any],
    latest: pd.DataFrame,
    selected_ids: list[str],
    year: int,
    regions: list[str],
    income_groups: list[str],
) -> None:
    st.subheader("Vue d'ensemble")

    summary = data["kpi_summary"]
    insights = data["insights"]
    quality = data["quality"]
    narrative = insights.get("narrative") or {}

    _kpi_cards(latest, selected_ids)
    _quality_badge(quality)

    st.caption(
        f"Run : {summary.get('run_id', insights.get('run_id', 'inconnu'))} — "
        f"année de référence : {year}"
    )

    executive = narrative.get("executive_summary")
    if executive:
        st.markdown("### Résumé exécutif")
        st.write(executive)

    snapshot = country_snapshot(data["country_year"], year, "inclusion_rate")
    snapshot = _filter_snapshot(snapshot, regions, income_groups)
    if not snapshot.empty:
        top, bottom = top_bottom(snapshot, n=5)
        left, right = st.columns(2)
        with left:
            st.markdown("### Pays les plus inclus")
            st.dataframe(
                top[["country", "value", "region"]],
                hide_index=True,
                use_container_width=True,
            )
        with right:
            st.markdown("### Pays les moins inclus")
            st.dataframe(
                bottom[["country", "value", "region"]],
                hide_index=True,
                use_container_width=True,
            )

    warnings = coverage_warnings(summary)
    if warnings:
        with st.expander("Points d'attention sur la couverture"):
            for warning in warnings:
                st.write(f"- {warning}")

    st.caption(
        "Les KPI sont des moyennes simples de pays, non pondérées par la population. "
        "Les agrégats régionaux sont exclus des comparaisons pays."
    )


def _trends(data: dict[str, Any], selected_ids: list[str]) -> None:
    st.subheader("Tendances")
    if not selected_ids:
        st.info("Sélectionne au moins un KPI dans la barre latérale.")
        return

    dimension_label = st.radio(
        "Niveau d'agrégation",
        ["Global", "Région", "Groupe de revenu"],
        horizontal=True,
    )
    if dimension_label == "Région":
        dimension = "region"
        values = dimension_values(data["kpi_values"], dimension)
        dimension_value = st.selectbox("Région", values) if values else None
    elif dimension_label == "Groupe de revenu":
        dimension = "income_group"
        values = dimension_values(data["kpi_values"], dimension)
        dimension_value = st.selectbox("Groupe de revenu", values) if values else None
    else:
        dimension = "global"
        dimension_value = "all"

    series = kpi_series(
        data["kpi_values"],
        selected_ids,
        dimension=dimension,
        dimension_value=dimension_value,
    )
    if series.empty:
        st.warning("Aucune série disponible pour cette sélection.")
        return

    fig = px.line(
        series,
        x="year",
        y="value",
        color="label",
        markers=True,
        labels={"year": "Année", "value": "Valeur", "label": "KPI"},
    )
    fig.update_layout(
        legend_title_text="",
        hovermode="x unified",
        margin=dict(l=10, r=10, t=20, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.warning(
        "2022 est une vague Findex partielle. "
        "Le paiement numérique n'est disponible que pour 2024."
    )
    st.dataframe(
        series[["label", "year", "value", "n_obs"]],
        hide_index=True,
        use_container_width=True,
    )


def _countries(
    data: dict[str, Any],
    latest: pd.DataFrame,
    year: int,
    regions: list[str],
    income_groups: list[str],
    selected_countries: list[str],
) -> None:
    st.subheader("Pays")
    if latest.empty:
        st.info("Aucun KPI pays disponible.")
        return

    options = {
        str(row["id"]): f"{row['label']} ({row['unit']})"
        for _, row in latest.iterrows()
    }
    kpi_id = st.selectbox(
        "KPI à cartographier",
        options=list(options),
        format_func=lambda value: options[value],
    )

    snapshot = country_snapshot(data["country_year"], year, kpi_id)
    snapshot = _filter_snapshot(snapshot, regions, income_groups)

    if snapshot.empty:
        st.warning("Aucune valeur pour cette sélection.")
        return

    if selected_countries:
        snapshot_focus = snapshot[snapshot["iso3"].isin(selected_countries)]
        title = "Comparaison des pays sélectionnés"
    else:
        snapshot_focus = snapshot
        title = "Classement des pays"

    st.markdown(f"### {title}")
    if snapshot_focus.empty:
        st.warning("Aucun pays sélectionné n'a de valeur pour cette année.")
        return

    ranking = snapshot_focus.sort_values("value", ascending=False)
    st.dataframe(
        ranking[["country", "value", "region", "income_group"]],
        hide_index=True,
        use_container_width=True,
    )

    fig_map = px.choropleth(
        snapshot,
        locations="iso3",
        locationmode="ISO-3",
        color="value",
        hover_name="country",
        hover_data={"region": True, "income_group": True, "iso3": False},
        color_continuous_scale="Viridis",
        labels={"value": options[kpi_id]},
    )
    fig_map.update_layout(
        margin=dict(l=0, r=0, t=20, b=0),
        coloraxis_colorbar_title="Valeur",
    )
    st.plotly_chart(fig_map, use_container_width=True)

    codes = selected_countries or ranking.head(5)["iso3"].tolist()
    metric = KPI_METRIC_COLUMNS.get(kpi_id)
    if metric and metric in data["country_year"].columns:
        trend = data["country_year"][
            data["country_year"]["iso3"].isin(codes)
        ][["country", "year", metric]].rename(columns={metric: "value"})
        trend = trend.dropna(subset=["value"])
        if not trend.empty:
            fig_trend = px.line(
                trend,
                x="year",
                y="value",
                color="country",
                markers=True,
                labels={"year": "Année", "value": options[kpi_id], "country": "Pays"},
            )
            fig_trend.update_layout(
                legend_title_text="",
                hovermode="x unified",
                margin=dict(l=10, r=10, t=20, b=10),
            )
            st.markdown("### Évolution des pays")
            st.plotly_chart(fig_trend, use_container_width=True)


def _quality_and_insights(data: dict[str, Any]) -> None:
    st.subheader("Qualité et insights")
    quality = data["quality"]
    summary = data["kpi_summary"]
    insights = data["insights"]
    narrative = insights.get("narrative") or {}

    _quality_badge(quality)
    table = quality_table(quality)
    if not table.empty:
        st.dataframe(table, hide_index=True, use_container_width=True)

    issues = pd.DataFrame(quality.get("issues") or [])
    if not issues.empty:
        st.markdown("### Anomalies détectées")
        st.dataframe(issues, hide_index=True, use_container_width=True)

    plan = quality.get("llm_plan") or []
    if plan:
        st.markdown("### Plan de remédiation proposé")
        for step in plan:
            st.write(f"- {step}")

    warnings = coverage_warnings(summary)
    if warnings:
        st.markdown("### Points d'attention KPI")
        for warning in warnings:
            st.write(f"- {warning}")

    st.markdown("### Synthèse de l'analyste")
    executive = narrative.get("executive_summary")
    if executive:
        st.write(executive)

    findings = narrative.get("key_findings") or []
    if findings:
        st.markdown("#### Constats")
        for finding in findings:
            st.write(f"- {finding}")

    recommendations = narrative.get("recommendations") or []
    if recommendations:
        st.markdown("#### Recommandations")
        for recommendation in recommendations:
            st.write(f"- {recommendation}")


def main() -> None:
    st.title("BIFlow — Inclusion financière")
    st.caption(
        "Dashboard en lecture seule : il lit les artefacts produits par le pipeline, "
        "sans recalculer les KPI et sans appeler les agents."
    )

    try:
        data = get_data()
    except DashboardDataError as exc:
        st.error(str(exc))
        st.stop()
        return

    latest = latest_kpis(data["kpi_summary"])
    if latest.empty:
        st.error("Aucun KPI dans kpi_summary.json.")
        st.stop()
        return

    labels = {
        str(row["id"]): f"{row['label']} ({row['unit']})"
        for _, row in latest.iterrows()
    }
    default_ids = [
        kpi_id
        for kpi_id in (
            "inclusion_rate",
            "gender_gap",
            "mobile_account_rate",
            "savings_rate",
            "borrowing_rate",
        )
        if kpi_id in labels
    ]
    if not default_ids:
        default_ids = list(labels)[:5]

    st.sidebar.header("Filtres")
    selected_ids = st.sidebar.multiselect(
        "KPI",
        options=list(labels),
        default=default_ids,
        format_func=lambda value: labels[value],
    )

    years = available_years(data["country_year"])
    if not years:
        st.error("Aucune année disponible dans country_year.parquet.")
        st.stop()
        return
    year = st.sidebar.selectbox("Année", years, index=len(years) - 1)

    country_frame = (
        data["country_year"]
        .loc[data["country_year"]["is_country"], ["iso3", "country"]]
        .dropna()
        .drop_duplicates()
        .sort_values("country")
    )
    country_options = {
        str(row["iso3"]): str(row["country"])
        for _, row in country_frame.iterrows()
    }
    selected_countries = st.sidebar.multiselect(
        "Pays",
        options=list(country_options),
        format_func=lambda value: country_options[value],
    )

    regions = sorted(
        data["country_year"]
        .loc[data["country_year"]["is_country"], "region"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )
    selected_regions = st.sidebar.multiselect("Région", regions)

    income_groups = sorted(
        data["country_year"]
        .loc[data["country_year"]["is_country"], "income_group"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )
    selected_income = st.sidebar.multiselect("Groupe de revenu", income_groups)

    if st.sidebar.button("Recharger les données"):
        st.cache_data.clear()
        st.rerun()

    st.sidebar.caption(
        "Sources : Findex, FAS, WDI. Les données et rapports ne sont pas versionnés."
    )

    tab_overview, tab_trends, tab_countries, tab_quality = st.tabs(
        ["Vue d'ensemble", "Tendances", "Pays", "Qualité et insights"]
    )

    with tab_overview:
        _overview(
            data,
            latest,
            selected_ids,
            year,
            selected_regions,
            selected_income,
        )

    with tab_trends:
        _trends(data, selected_ids)

    with tab_countries:
        _countries(
            data,
            latest,
            year,
            selected_regions,
            selected_income,
            selected_countries,
        )

    with tab_quality:
        _quality_and_insights(data)

    st.divider()
    st.caption(
        "BIFlow — P4 Dashboard. Calculs déterministes en amont ; "
        "les LLM ne produisent que des notes et des recommandations."
    )


if __name__ == "__main__":
    main()
