"""Scoped analysis options used by the dashboard API (no unnecessary work)."""
from types import SimpleNamespace

import duckdb
import pytest
from pydantic import ValidationError

from biflow.tools.analysis import AnalysisRequest, AnalysisService

COUNTRIES = ("TUN", "MAR", "DZA")
KPIS = ("account_ownership", "branch_density")


def _result(kpi_id: str, iso3: str, year: int, value: float | None):
    available = value is not None
    return SimpleNamespace(
        kpi_id=kpi_id,
        iso3=iso3,
        observation_year=year,
        value=value,
        unit="percent",
        availability_status="available" if available else "unavailable",
        reason=None if available else "no_observation",
        verification_status="verified",
        requires_review=False,
        review_reasons=[],
        source="findex",
        source_indicator="account_t_d",
        indicator_code="account_t_d",
        input_value=None,
        input_unit=None,
        definition_version="v1",
        formula=None,
        subgroup="all",
        dependencies=[],
        publication_status="not_evaluated",
        provenance=None,
        quality_warnings=[],
        source_warnings=[],
    )


class _FakeTools:
    def list_kpis(self, request):
        return SimpleNamespace(
            kpis=[
                SimpleNamespace(
                    kpi_id=kpi, name=kpi, unit="percent", subgroup="all",
                    verification_status="verified", valid_years=(2023, 2024),
                    dependencies=(),
                )
                for kpi in KPIS
            ],
            catalog_version="1.0",
            catalog_sha256="0" * 64,
        )

    def calculate_kpi(self, request):
        value = 40.0 + request.year % 10 if request.year in (2023, 2024) else None
        return SimpleNamespace(
            result=_result(request.kpi_id, request.iso3, request.year, value)
        )

    def compare_countries(self, request):
        left = 40.0 + request.year % 10
        right = 30.0 + request.year % 10
        return SimpleNamespace(
            right=SimpleNamespace(value=right),
            left=SimpleNamespace(value=left),
            difference=right - left,
            difference_unit="percentage_points",
            comparison_status="complete",
            reason=None,
            requires_review=False,
            review_reasons=[],
        )


@pytest.fixture(scope="module")
def warehouse(tmp_path_factory):
    path = tmp_path_factory.mktemp("analysis_scope") / "warehouse.duckdb"
    with duckdb.connect(str(path)) as con:
        con.execute(
            "CREATE TABLE country_dim (iso3 VARCHAR, country VARCHAR, region VARCHAR, "
            "income_group VARCHAR)"
        )
        con.executemany(
            "INSERT INTO country_dim VALUES (?, ?, ?, ?)",
            [(code, code, "MENA", "LMIC") for code in COUNTRIES],
        )
    return path


def _build(warehouse, **options):
    request = AnalysisRequest(
        iso3=COUNTRIES, kpi_ids=KPIS, mode="year", year=2024, **options,
    )
    return AnalysisService(
        warehouse, tools=_FakeTools(),
        lineage_path=warehouse.parent / "lineage.json",
        quality_report_path=warehouse.parent / "quality_report.json",
    ).build(request)


def test_default_scope_keeps_every_section(warehouse):
    data = _build(warehouse)
    assert len(data["series"]) == len(COUNTRIES) * len(KPIS)
    assert data["trends"] and data["rankings"] and data["comparisons"]


def test_dashboard_scope_skips_unused_sections(warehouse):
    data = _build(
        warehouse, series_iso3=("TUN",), include_trends=False,
        include_rankings=False, include_comparisons=False,
    )
    assert {row["iso3"] for row in data["series"]} == {"TUN"}
    assert len(data["observations"]) == len(COUNTRIES) * len(KPIS)
    assert data["trends"] == []
    assert data["rankings"] == []
    assert data["comparisons"] == []


def test_series_scope_is_normalized(warehouse):
    request = AnalysisRequest(
        iso3=("TUN", "MAR"), series_iso3=("tun",), mode="year", year=2024,
    )
    assert request.series_iso3 == ("TUN",)


def test_series_scope_must_belong_to_scope():
    with pytest.raises(ValidationError):
        AnalysisRequest(
            iso3=("TUN",), series_iso3=("MAR",), mode="year", year=2024,
        )
