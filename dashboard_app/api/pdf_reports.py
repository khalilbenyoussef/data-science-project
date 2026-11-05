"""Rapports PDF de la plateforme, construits a la demande (jamais pendant un run).

Deux documents, a partir de l'etat courant lu en lecture seule :

- evaluation.pdf : verdict d'audit, controles en francais simple, publication,
  injection de fautes, audit des constats, evaluation par agent, approche de
  reference. Les chiffres d'audit sont ceux de ``GET /api/audit/summary``.
- insights.pdf : constats du pays et de l'annee choisis (statut d'audit calcule
  a la demande contre kpi_values) et pistes de recommandation.

Polices standard du PDF (Helvetica, codage WinAnsi) : les rares caracteres hors
de ce jeu (≥, −, espace fine) sont remplaces par un equivalent lisible.
"""
from __future__ import annotations

from io import BytesIO
from typing import Any, Iterable, Mapping, Sequence
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from biflow.tools.audit_text import fr_number
from biflow.tools.deliverables import NA, STALE, STATUS_FR, Context, agent_summaries
from biflow.tools.user_sources.data import USER_CHIP

INK, MUTED, LINE, ACCENT, SOFT = (colors.HexColor(c) for c in ("#14213d", "#5b6577", "#d7dde8", "#1f5fbf", "#eef3fb"))
WARN = colors.HexColor("#b45309")
VERDICTS = {"pass": "conforme", "pass_with_warnings": "conforme avec avertissements", "fail": "non conforme"}
RESULTS = {"pass": "réussi", "warn": "avertissement", "fail": "échec"}
UNITS = {"percent": "%", "percentage_points": "pts", "per_100k_adults": "pour 100 000 adultes",
         "per_1k_adults": "pour 1 000 adultes", "percent_of_gdp": "% du PIB"}
PUBLICATION = {"approved": "approuvée", "approved_with_review_note": "avec réserve", "blocked": "bloquée"}
REPLACE = {"≥": ">=", "≤": "<=", "−": "-", "\u202f": "\u00a0", " ": " ", "→": "->", "✓": "oui", "✗": "non"}


def clean(value: Any) -> str:
    text = "" if value is None else str(value)
    for old, new in REPLACE.items():
        text = text.replace(old, new)
    return text.encode("cp1252", errors="replace").decode("cp1252")


def n(value: Any, decimals: int = 0) -> str:
    """Nombre au format francais (espace des milliers, virgule decimale)."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return NA
    return fr_number(value, decimals, thousands="\u00a0")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=base["BodyText"], fontName="Helvetica", fontSize=9.5, leading=13,
                          textColor=INK, alignment=TA_LEFT, spaceAfter=4)
    return {
        "title": ParagraphStyle("title", parent=body, fontName="Helvetica-Bold", fontSize=22, leading=27,
                                spaceAfter=6),
        "subtitle": ParagraphStyle("subtitle", parent=body, fontSize=12, leading=16, textColor=MUTED, spaceAfter=18),
        "h1": ParagraphStyle("h1", parent=body, fontName="Helvetica-Bold", fontSize=14, leading=18,
                             spaceBefore=10, spaceAfter=6, textColor=ACCENT),
        "h2": ParagraphStyle("h2", parent=body, fontName="Helvetica-Bold", fontSize=11, leading=14,
                             spaceBefore=6, spaceAfter=4),
        "body": body,
        "small": ParagraphStyle("small", parent=body, fontSize=8, leading=10.5, textColor=MUTED),
        "cell": ParagraphStyle("cell", parent=body, fontSize=8, leading=10, spaceAfter=0),
        "cellb": ParagraphStyle("cellb", parent=body, fontName="Helvetica-Bold", fontSize=8, leading=10,
                                spaceAfter=0),
        "warn": ParagraphStyle("warn", parent=body, textColor=WARN, fontName="Helvetica-Bold"),
    }


S = _styles()


def P(text: Any, style: str = "body") -> Paragraph:
    return Paragraph(escape(clean(text)), S[style])


def grid(headers: Sequence[str], rows: Iterable[Sequence[Any]], widths: Sequence[float]) -> Table:
    data = [[P(h, "cellb") for h in headers]] + [[P(c, "cell") for c in row] for row in rows]
    table = Table(data, colWidths=[w * mm for w in widths], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), SOFT), ("LINEBELOW", (0, 0), (-1, 0), 0.6, ACCENT),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def _cover(title: str, subtitle: str, ctx: Context, extra: Sequence[tuple[str, str]] = (),
           notices: Sequence[str] = ()) -> list[Any]:
    rows = [("Date de génération", ctx.generated_at.replace("T", " ")),
            ("Run audité (Route 1)", ctx.run_id), ("Snapshot", ctx.snapshot_id),
            ("Version du catalogue KPI", ctx.catalog_version), ("Run Route 2", ctx.route2_run_id), *extra]
    table = Table([[P(k, "cellb"), P(v, "cell")] for k, v in rows], colWidths=[55 * mm, 115 * mm])
    table.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.3, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    out = [Spacer(1, 30 * mm), P("FinOVA", "subtitle"), P(title, "title"), P(subtitle, "subtitle"), table,
           Spacer(1, 8 * mm)]
    out += [P(text, "warn") for text in notices]
    out += [Spacer(1, 6 * mm), P("Document construit à la demande depuis les données courantes de la plateforme "
                                 "(lecture seule). Aucun chiffre n'est saisi à la main.", "small"), PageBreak()]
    return out


def _footer(label: str):
    def draw(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 10 * mm, clean(label))
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"page {doc.page}")
        canvas.restoreState()
    return draw


def _build(story: list[Any], title: str, footer: str) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm, title=clean(title), author="FinOVA", creator="FinOVA",
                            subject=clean(title))
    doc.build(story, onFirstPage=_footer(footer), onLaterPages=_footer(footer))
    return buffer.getvalue()


# ------------------------------------------------------------------ evaluation.pdf
def evaluation_pdf(ctx: Context, summary: Mapping[str, Any], checks: Sequence[Mapping[str, Any]],
                   freshness: Mapping[str, Any]) -> bytes:
    """Evaluation et explicabilite ; ``summary`` est la reponse de /api/audit/summary."""
    counts = summary.get("counts") or {}
    publication = summary.get("publication") or {}
    evaluation = summary.get("evaluation") or {}
    insight = summary.get("insight_audit") or {}
    notices = []
    fi, ag = freshness.get("fault_injection") or {}, freshness.get("agents") or {}
    if fi.get("stale"):
        notices.append(f"Injection de fautes : {STALE} ({fi.get('created_at')}).")
    if ag.get("stale"):
        notices.append(f"Évaluation des agents : {STALE} ({ag.get('created_at')}).")
    story = _cover("Rapport d'évaluation et d'explicabilité",
                   "Audit des indicateurs, contrôles, injection de fautes, évaluation des agents", ctx,
                   [("Dernier audit", str(summary.get("created_at") or NA).replace("T", " ")),
                    ("Injection de fautes (mesure enregistrée)", str(fi.get("created_at") or NA).replace("T", " ")),
                    ("Évaluation des agents (mesure enregistrée)", str(ag.get("created_at") or NA).replace("T", " "))],
                   notices)
    verdict = summary.get("verdict")
    story += [
        P("Synthèse", "h1"),
        grid(["Mesure", "Valeur"], [
            ["Verdict d'audit", VERDICTS.get(verdict, verdict or NA)],
            ["Contrôles réussis", n(counts.get("pass"))], ["Avertissements", n(counts.get("warn"))],
            ["Échecs", n(counts.get("fail"))],
            ["Valeurs approuvées", n(publication.get("approved"))],
            ["Valeurs approuvées avec réserve", n(publication.get("approved_with_review_note"))],
            ["Valeurs bloquées", n(publication.get("blocked"))],
            ["Fautes injectées détectées", f"{n(evaluation.get('detected'))} / {n(evaluation.get('total'))}"],
            ["Constats audités", n(insight.get("audited"))], ["Constats acceptés", n(insight.get("accepted"))],
            ["Constats rejetés", n(insight.get("rejected"))],
            ["Constats non auditables", n(insight.get("not_auditable"))],
        ], [90, 50]),
        P("1. Verdict d'audit", "h1"),
        P(f"Verdict : {VERDICTS.get(verdict, verdict or NA)} ({verdict or NA}). {n(counts.get('pass'))} contrôles "
          f"réussis, {n(counts.get('warn'))} avertissements, {n(counts.get('fail'))} échecs. Snapshot "
          f"{summary.get('snapshot_id') or NA}, run {summary.get('run_id') or NA}, catalogue "
          f"{summary.get('catalog_version') or NA}."),
        P("Publication des valeurs", "h2"),
        grid(["Statut", "Lignes"], [["approuvées", n(publication.get("approved"))],
                                    ["approuvées avec réserve", n(publication.get("approved_with_review_note"))],
                                    ["bloquées", n(publication.get("blocked"))]], [90, 40]),
    ]
    reasons = summary.get("review_reasons") or []
    if reasons:
        story += [Spacer(1, 3 * mm), P("Motifs des réserves", "h2"),
                  grid(["Motif", "Lignes"], [[r.get("label"), n(r.get("rows"))] for r in reasons], [90, 40])]
    story += [P("2. Contrôles, en clair", "h1"),
              grid(["Contrôle", "Résultat", "Ce qui est vérifié", "Lignes signalées"],
                   [[c.get("check_id"), RESULTS.get(c.get("result"), c.get("result")), c.get("description"),
                     n(c.get("affected_count"))] for c in checks], [38, 22, 90, 24])]
    story += [P(f"3. Injection de fautes : {n(evaluation.get('detected'))}/{n(evaluation.get('total'))} "
                "fautes détectées", "h1"),
              P("Chaque faute est injectée dans une copie des données ; l'Auditor doit la détecter avec le contrôle "
                f"attendu. Mesure du {evaluation.get('created_at') or NA}."
                + (f" Attention : {STALE}." if evaluation.get("stale") else ""), "body"),
              grid(["Faute injectée", "Contrôle attendu", "Détectée", "Verdict obtenu"],
                   [[f.get("label"), f.get("expected_check"), "oui" if f.get("detected") else "non",
                     VERDICTS.get(f.get("verdict"), f.get("verdict"))] for f in evaluation.get("faults") or []],
                   [62, 52, 20, 40])]
    rows = insight.get("insights") or []
    story += [P("4. Audit des constats", "h1"),
              P(f"Run {insight.get('run_id') or NA} : {n(insight.get('audited'))} constats audités, "
                f"{n(insight.get('accepted'))} acceptés, {n(insight.get('rejected'))} rejetés, "
                f"{n(insight.get('not_auditable'))} non auditables."),
              grid(["Constat", "Statut", "Indicateurs cités"],
                   [[r.get("statement"), "accepté" if r.get("accepted") is True else
                     "rejeté" if r.get("accepted") is False else "non auditable",
                     "; ".join(f"{c['kpi']} {c['iso3']} {c['year']}" for c in r.get("cited") or []) or "-"]
                    for r in rows], [95, 22, 57])]
    story += [PageBreak(), P("5. Évaluation par agent", "h1"),
              grid(["Agent", "Mode", "Statut", "Durée", "Sortie clé", "LLM"],
                   [[a["label"], a["llm_mode"].split(" (")[0], STATUS_FR.get(a["status"], a["status"] or NA),
                     f"{n(a['duration_s'], 2)} s" if a["duration_s"] is not None else NA, a["key_output"],
                     a["llm_measured"]] for a in agent_summaries(ctx)], [30, 34, 16, 16, 58, 20])]
    unit = ctx.agents_eval.get("ask_unit_tests") or {}
    live = ctx.ask_live
    story += [P("Ask Finova", "h2"),
              P(f"Tests unitaires (LLM simulé) : {n(unit.get('passed'))}/{n(unit.get('total'))} réussis"
                if unit.get("total") else "Tests unitaires (LLM simulé) : non mesuré."),
              P(f"Contrôle en direct : {n(live.get('grounded'))}/{n(live.get('questions'))} réponses dont tous les "
                f"nombres sont fondés, modèle {live.get('model')}, le {live.get('run_at')}."
                if live.get("status") == "mesuré" else "Contrôle en direct : non mesuré (aucune clé LLM ou "
                                                        "contrôle non exécuté).")]
    base = ctx.baseline
    story += [P("6. Approche de référence", "h1")]
    if base:
        timing = base.get("timing_s") or {}
        manual = (ctx.manual.get("minutes_per_kpi") or {}) if isinstance(ctx.manual, dict) else {}
        story += [
            P(f"Recalcul naïf de 4 indicateurs depuis les CSV bruts (pandas), comparé à kpi_values : "
              f"{n(base.get('matched'))}/{n(base.get('compared'))} valeurs identiques (tolérance "
              f"{base.get('tolerance')}). Recalcul naïf {n(timing.get('naive_pandas'), 2)} s ; lecture de "
              f"kpi_values {n(timing.get('kpi_values_read'), 3)} s. Mesure du {base.get('created_at')}."),
            grid(["Indicateur", "Valeurs comparées", "Identiques", "Temps Excel (manuel)"],
                 [[k, n(v.get("compared")), n(v.get("matched")),
                   f"{n(manual.get(k), 1)} min" if isinstance(manual.get(k), (int, float)) else "non mesuré"]
                  for k, v in (base.get("by_kpi") or {}).items()], [60, 35, 30, 45])]
    else:
        story += [P("Approche de référence : non disponible (scripts/baseline_reference.py non exécuté).")]
    return _build(story, "FinOVA - Rapport d'évaluation", f"FinOVA - évaluation - run {ctx.run_id} - "
                                                           f"snapshot {ctx.snapshot_id}")


# ------------------------------------------------------------------ insights.pdf
def insights_pdf(ctx: Context, scope: Mapping[str, Any], insights: Sequence[Mapping[str, Any]],
                 recommendations: Mapping[str, Any], annex: Mapping[str, Any] | None = None) -> bytes:
    """Constats et pistes du perimetre choisi ; annexe facultative « vos données »."""
    label = f"{scope.get('country') or scope.get('iso3')} ({scope.get('iso3')}), {scope.get('year')}"
    extra = [("Périmètre", label), ("Spec", f"générée le {scope.get('generated_at') or NA}")]
    if annex is not None:
        extra.append(("Annexe", f"vos données ({USER_CHIP})"))
    story = _cover("Constats et pistes de recommandation", label, ctx, extra)
    accepted = sum(1 for i in insights if i.get("accepted") is True)
    story += [P("1. Constats", "h1"),
              P(f"{n(len(insights))} constats ; {n(accepted)} acceptés par l'audit des nombres (chaque nombre est une "
                "valeur publiée de kpi_values, une année ou une différence entre deux valeurs citées), "
                f"{n(sum(1 for i in insights if i.get('accepted') is False))} rejetés, "
                f"{n(sum(1 for i in insights if i.get('accepted') is None))} non auditables. Statut calculé à la "
                "génération du document.")]
    pages: dict[str, list[Mapping[str, Any]]] = {}
    for item in insights:
        pages.setdefault(item["page"], []).append(item)
    for page, items in pages.items():
        story += [P(page, "h2"),
                  grid(["Constat", "Statut", "Indicateurs cités"],
                       [[i.get("statement"), "accepté" if i.get("accepted") is True else "rejeté"
                         if i.get("accepted") is False else "non auditable",
                         "; ".join(f"{c['kpi']} {c['iso3']} {c['year']}" for c in i.get("cited") or []) or "-"]
                        for i in items], [95, 22, 57])]
    recs = recommendations.get("recommendations") or []
    story += [P("2. Pistes de recommandation", "h1"),
              P(f"Règles déterministes (config/recommendations.yaml, version {recommendations.get('rules_version')}) "
                f"appliquées aux valeurs auditées : {n(recommendations.get('rules_checked'))} comparaisons, "
                f"{n(len(recs))} pistes retenues, {n(len(recommendations.get('rejected') or []))} écartées par l'audit "
                "des nombres. Une piste décrit une association, pas une causalité.")]
    if not recs:
        story += [P("Aucune règle déclenchée pour ce périmètre.")]
    for index, rec in enumerate(recs, 1):
        story += [KeepTogether([
            P(f"{index}. {rec['text']}", "body"),
            P(f"Groupe cible : {rec['target_group']} - règle : {rec['rule']}", "small"),
            grid(["Source", "Pays", "Année", "Valeur", "Statut"],
                 [[e["kpi"], "moyenne des pairs" if e["iso3"] == "PEERS" else e["iso3"], e["year"],
                   f"{n(e['value'], 1)} {UNITS.get(e['unit'], e['unit'])}",
                   PUBLICATION.get(e["publication_status"], e["publication_status"])] for e in rec["evidence"]],
                 [70, 30, 14, 32, 28]), Spacer(1, 3 * mm)])]
    if annex is not None:
        story += _annex(annex, scope)
    return _build(story, f"FinOVA - Constats {label}", f"FinOVA - constats {label} - run {ctx.run_id}")


def _user_value(value: Mapping[str, Any] | None) -> str:
    if not value:
        return "-"
    return f"{value['display']} ({value['year']})"


def _annex(annex: Mapping[str, Any], scope: Mapping[str, Any]) -> list[Any]:
    """Annexe : vos données. Section separee, chaque valeur etiquetee ; aucune n'entre
    dans les constats ni dans les pistes officiels."""
    year = scope.get("year")
    story: list[Any] = [PageBreak(), P("Annexe : vos données", "h1"),
                        P(f"{USER_CHIP}. Valeurs importées sur la page « Mes données » : BIFlow ne les vérifie pas "
                          "et elles ne font partie ni des constats ni des pistes officiels ci-dessus. Pour chaque "
                          f"indicateur : valeur de {year}, sinon de la dernière année antérieure (année indiquée).")]
    values = annex.get("values") or []
    if not values:
        story.append(P("Aucune donnée utilisateur intégrée."))
    else:
        story += [P("Vos indicateurs", "h2"),
                  grid(["Indicateur (vos données)", "Valeur (année)", "Étiquette"],
                       [[v["label"], _user_value(v.get("row")), USER_CHIP] for v in values], [80, 40, 54])]
    comp = annex.get("comparisons") or {}
    rows = comp.get("rows") or []
    if rows:
        story += [P("Vos indicateurs face aux données officielles", "h2"), P(comp.get("note") or "", "small")]
        story.append(grid(["Votre indicateur (non vérifié)", "Valeur", "Indicateur officiel", "Valeur", "Note"],
                          [[r["label"], _user_value(r.get("user")), r["kpi"], _user_value(r.get("official")),
                            "; ".join(r.get("notes") or []) or "-"] for r in rows], [44, 26, 44, 26, 34]))
        for r in rows:
            if r.get("definition"):
                story.append(P(f"{r['kpi']} - définition officielle : {r['definition']}"
                               + (f" Dénominateur : {r['denominator']}." if r.get("denominator") else ""), "small"))
    recs = annex.get("recommendations") or []
    if recs:
        story += [P("Pistes à partir de vos données", "h2")]
        story += [P(f"{index}. {rec['text']}", "body") for index, rec in enumerate(recs, 1)]
    return story


__all__ = ["evaluation_pdf", "insights_pdf"]
