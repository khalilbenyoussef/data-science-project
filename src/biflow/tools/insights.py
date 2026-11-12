"""Contrat d'audit des insights (futur agent Analyst).

Un insight cite ses chiffres sous forme de claims ; l'Auditor verifie chaque
claim contre kpi_values (valeur au meme arrondi, unite, annee, ligne approuvee)
et chaque nombre du texte : valeur d'un claim, annee d'un claim, ou difference
deterministe entre deux claims du meme KPI (deux annees d'un pays ou deux pays
d'une annee), au meme arrondi. Tout autre nombre fait rejeter l'insight.
"""
from __future__ import annotations

from decimal import Decimal
from itertools import combinations
import re
from typing import Any, Iterable, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, ValidationError

from biflow.tools.audit_text import NUMBER, THOUSANDS
from biflow.utils.countries import normalize_iso3

APPROVED = ("approved", "approved_with_review_note")
# Preuve d'une observation KPI du dataset Route 2 (analysis.evidence_id)
EVIDENCE = re.compile(r"EV-(?P<kpi>[a-z0-9_]+)-(?P<iso3>[A-Z]{3}|PEERS)-(?P<year>\d{4})")


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kpi_id: StrictStr = Field(min_length=1)
    iso3: StrictStr = Field(min_length=3)
    year: StrictInt
    value: float
    unit: StrictStr


class Insight(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    insight_id: StrictStr = Field(min_length=1)
    text: StrictStr = Field(min_length=1)
    claims: list[Claim] = Field(min_length=1)
    recommendation: StrictStr
    confidence: Literal["low", "medium", "high"]


def _decimals(text: str) -> int:
    exponent = Decimal(text).as_tuple().exponent
    return max(0, -int(exponent))


def _numbers(text: str) -> list[tuple[str, float, int]]:
    """(texte, valeur absolue, decimales) pour chaque nombre ; 37,8 et 37.8 identiques."""
    out = []
    for token in NUMBER.findall(text):
        canonical = token.lstrip("+-−").replace(",", ".")
        for sep in THOUSANDS:
            canonical = canonical.replace(sep, "")
        out.append((token, float(canonical), _decimals(canonical)))
    return out


def _same(a: float, b: float, decimals: int) -> bool:
    return f"{a:.{decimals}f}" == f"{b:.{decimals}f}"


def audit_insights(insights: Iterable[Any], rows: Iterable[Mapping[str, Any]],
                   statuses: Mapping[tuple, str] | None = None) -> list[dict[str, Any]]:
    """{insight_id, accepted, reasons, notes} pour chaque insight fourni."""
    table = {(r["kpi_id"], r["iso3"], int(r["year"])): r for r in rows}
    results = []
    for index, raw in enumerate(insights):
        try:
            insight = Insight.model_validate(raw)
        except ValidationError as exc:
            insight_id = raw.get("insight_id") if isinstance(raw, Mapping) else None
            results.append({"insight_id": insight_id or f"#{index}", "accepted": False,
                            "reasons": [f"schema invalide : {e['loc']} {e['msg']}" for e in exc.errors()],
                            "notes": []})
            continue
        reasons, notes, verified = [], [], []
        for claim in insight.claims:
            iso3 = "PEERS" if claim.iso3.strip().upper() == "PEERS" else normalize_iso3(claim.iso3)
            label = f"{claim.kpi_id}/{claim.iso3}/{claim.year}"
            row = table.get((claim.kpi_id, iso3, claim.year))
            if row is None:
                reasons.append(f"claim {label} : aucune ligne kpi_values")
                continue
            status = (statuses or {}).get((claim.kpi_id, iso3, claim.year), row.get("publication_status"))
            decimals = _decimals(repr(claim.value)) if "e" not in repr(claim.value) else 6
            if row["unit"] != claim.unit:
                reasons.append(f"claim {label} : unité {claim.unit} au lieu de {row['unit']}")
            elif row["value"] is None:
                reasons.append(f"claim {label} : valeur indisponible dans kpi_values")
            elif not _same(claim.value, row["value"], decimals):
                reasons.append(f"claim {label} : {claim.value} différent de {row['value']:.{decimals}f} publié")
            elif status not in APPROVED:
                reasons.append(f"claim {label} : ligne {status}, non approuvée")
            else:
                verified.append((claim, iso3, row["value"]))
                if status == "approved_with_review_note":
                    notes.append(f"claim {label} : publié avec note de revue {list(row.get('review_reasons') or [])}")

        years = {c.year for c, _, _ in verified}
        differences = []
        for (a, ia, va), (b, ib, vb) in combinations(verified, 2):
            same_series = a.kpi_id == b.kpi_id and ((ia == ib and a.year != b.year) or (a.year == b.year and ia != ib))
            if same_series:
                differences += [abs(va - vb), abs(a.value - b.value)]
        for token, number, decimals in _numbers(insight.text):
            backed = (
                any(_same(number, abs(c.value), decimals) or _same(number, abs(v), decimals) for c, _, v in verified)
                or (decimals == 0 and int(number) in years)
                or any(_same(number, diff, decimals) for diff in differences)
            )
            if not backed:
                reasons.append(f"nombre '{token}' du texte non justifié par un claim")
        results.append({"insight_id": insight.insight_id, "accepted": not reasons,
                        "reasons": reasons, "notes": notes})
    return results


def insights_from_finova(insights_by_page: Mapping[str, Iterable[Mapping[str, Any]]] | None,
                         facts: Iterable[Mapping[str, Any]], kpi_ids: Iterable[str],
                         ) -> tuple[list[dict[str, Any]], list[str]]:
    """Insights du FinOVA Analyst -> Insight a auditer.

    Seuls les faits fournis par le catalogue KPI (provider semantic, une preuve
    EV-<kpi>-<iso3>-<annee>) deviennent des claims. Un fait derive (variation,
    ecart entre groupes) apporte les claims des faits KPI dont il est issu, lus sur
    les faits semantiques qui portent ses preuves (une variation 2021 -> 2024 cite
    ainsi ses deux annees). Un insight sans fait KPI n'est pas
    auditable (liste renvoyee a part). Aucune valeur n'est calculee ici.
    """
    facts = list(facts)
    by_id = {fact.get("id"): fact for fact in facts}
    kpis = set(kpi_ids)

    def claim(fact: Mapping[str, Any]) -> dict[str, Any] | None:
        evidence = tuple(fact.get("evidence_ids") or ())
        match = EVIDENCE.fullmatch(evidence[0]) if len(evidence) == 1 else None
        if (fact.get("provider") != "semantic" or match is None or match["kpi"] not in kpis
                or fact.get("value") is None or fact.get("year") is None
                or int(match["year"]) != int(fact["year"])):
            return None
        return {"kpi_id": match["kpi"], "iso3": match["iso3"], "year": int(fact["year"]),
                "value": float(fact["value"]), "unit": fact.get("unit")}

    carriers = {}  # preuve -> claim du fait semantique qui la porte seule
    for fact in facts:
        found = claim(fact)
        if found is not None:
            carriers.setdefault(fact["evidence_ids"][0], found)
    converted, not_auditable = [], []
    for page, items in (insights_by_page or {}).items():
        for item in items or []:
            claims = []
            for evidence in item.get("evidence_ids") or ():
                fact = by_id.get(evidence) or {}
                found = [claim(fact)]
                if fact.get("provider") == "derived":  # variation, ecart : faits KPI d'origine
                    found = [carriers.get(ev) for ev in fact.get("evidence_ids") or ()]
                claims.extend(c for c in found if c is not None and c not in claims)
            identifier = f"{page}:{item.get('id')}"
            if not claims:
                not_auditable.append(identifier)
                continue
            converted.append({"insight_id": identifier, "text": item.get("statement", ""), "claims": claims,
                              "recommendation": "", "confidence": "medium"})
    return converted, not_auditable


def insight_details(spec: Mapping[str, Any], audit: Mapping[str, Any],
                    catalog_kpis: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Constats de la spec avec leur resultat d'audit (accepte, rejete ou non
    auditable) et les KPI, pays et annees qu'ils citent. Lecture seule."""
    def name_fr(kpi_id: str) -> str:
        kpi = catalog_kpis.get(kpi_id) or {}
        return kpi.get("name_fr") or kpi.get("name") or kpi_id

    by_page = {page.get("id"): page.get("insights") or [] for page in spec.get("pages") or []}
    statements = {f"{page}:{item.get('id')}": item.get("statement") for page, items in by_page.items()
                  for item in items}
    claims, _ = insights_from_finova(by_page, spec.get("facts") or [], catalog_kpis)
    cited = {claim["insight_id"]: [{"kpi_id": c["kpi_id"], "kpi": name_fr(c["kpi_id"]),
                                    "iso3": c["iso3"], "year": c["year"]} for c in claim["claims"]]
             for claim in claims}
    rows = [{"insight_id": item["insight_id"], "accepted": item["accepted"], "reasons": item.get("reasons") or [],
             "statement": statements.get(item["insight_id"]), "cited": cited.get(item["insight_id"], [])}
            for item in audit.get("results") or []]
    rows += [{"insight_id": insight_id, "accepted": None, "reasons": ["non auditable"],
              "statement": statements.get(insight_id), "cited": []}
             for insight_id in audit.get("not_auditable_ids") or []]
    return rows


__all__ = ["APPROVED", "Claim", "Insight", "audit_insights", "insight_details", "insights_from_finova"]
