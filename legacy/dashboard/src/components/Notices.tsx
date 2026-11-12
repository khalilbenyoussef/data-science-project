import { useState } from "react";
import type { Notice } from "../types";
import { severityLabel } from "../format";

interface Props {
  notices: Notice[];
}

export function Notices({ notices }: Props) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? notices : notices.slice(0, 8);

  return (
    <section className="panel">
      <header className="panel__head">
        <h2>Avertissements</h2>
        <span className="panel__count">{notices.length}</span>
      </header>
      <ul className="notice-list">
        {visible.map((notice) => (
          <li key={`${notice.code}-${notice.message}`} className={`notice notice--${notice.severity}`}>
            <span className={`badge badge-${notice.severity}`}>
              {severityLabel(notice.severity)}
            </span>
            <div className="notice__body">
              <code>{notice.code}</code>
              <p>{notice.message}</p>
              {typeof notice.reference === "string" && (
                <span className="notice__ref">{notice.reference}</span>
              )}
            </div>
          </li>
        ))}
      </ul>
      {notices.length > 8 && (
        <button className="link-button" type="button" onClick={() => setExpanded((value) => !value)}>
          {expanded ? "Réduire" : `Afficher les ${notices.length - 8} autres avertissements`}
        </button>
      )}
    </section>
  );
}
