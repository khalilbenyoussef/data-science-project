import type { Card } from "../types";
import { formatValue, reasonLabel, statusLabel } from "../format";

interface Props {
  card: Card;
  selected: boolean;
  onSelect: () => void;
}

export function KpiCard({ card, selected, onSelect }: Props) {
  const review = card.requires_review || card.availability_status === "requires_review";
  return (
    <button
      type="button"
      className={`kpi-card${selected ? " is-selected" : ""}${review ? " has-review" : ""}`}
      onClick={onSelect}
      aria-pressed={selected}
      title={`${card.kpi_name} — ${card.evidence_id}`}
    >
      <span className="kpi-card__top">
        <span className="kpi-card__name">{card.kpi_name}</span>
        <span className="kpi-card__country">
          {card.iso3} · {card.year ?? "année non déterminée"}
        </span>
      </span>
      <span className={`kpi-card__value${card.value === null ? " is-missing" : ""}`}>
        {formatValue(card.value, card.unit)}
      </span>
      <span className="kpi-card__badges">
        <span className={`badge ${review ? "badge-review" : "badge-ok"}`}>
          {review ? "Revue requise" : statusLabel(card.availability_status)}
        </span>
        <span
          className={`badge ${
            card.definition_status === "provisional" ? "badge-warning" : "badge-neutral"
          }`}
        >
          {statusLabel(card.definition_status)}
        </span>
      </span>
      {card.review_reasons.length > 0 && (
        <span className="kpi-card__reasons">
          {card.review_reasons.slice(0, 2).map((code) => (
            <span className="chip" key={code} title={code}>
              {reasonLabel(code)}
            </span>
          ))}
          {card.review_reasons.length > 2 && (
            <span className="chip chip-more" title={card.review_reasons.slice(2).join(", ")}>
              +{card.review_reasons.length - 2}
            </span>
          )}
        </span>
      )}
      <span className="kpi-card__evidence">{card.evidence_id}</span>
    </button>
  );
}
