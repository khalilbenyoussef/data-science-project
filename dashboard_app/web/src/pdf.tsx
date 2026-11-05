import { useState } from "react";

// Lien de telechargement d'un rapport PDF construit a la demande par l'API (meme origine,
// compatible avec la CSP : simple navigation, aucun script ni objet embarque).
export function PdfDownload({ href, title }: { href: string; title: string }) {
  return (
    <a className="primary-btn pdf-download" href={href} download title={title}>
      <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
        <path d="M12 4v11m0 0-4-4m4 4 4-4M5 19h14" fill="none" stroke="currentColor" strokeWidth="2"
              strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      Télécharger le rapport (PDF)
    </a>
  );
}

// Rapport des constats (Vue d'ensemble) : case facultative « Annexe : vos données »
// (valeurs de « Mes données », etiquetees, dans une section separee du PDF).
export function InsightsPdf({ iso3, year, title }: { iso3: string; year: number; title: string }) {
  const [annex, setAnnex] = useState(false);
  const href = `/api/reports/insights.pdf?iso3=${encodeURIComponent(iso3)}&year=${year}${annex ? "&annexe=true" : ""}`;
  return (
    <div className="pdf-with-annex">
      <PdfDownload href={href} title={title} />
      <label className="inline-check small" title="Ajoute une annexe séparée avec vos données, étiquetées « non vérifiée par BIFlow »">
        <input type="checkbox" checked={annex} onChange={(event) => setAnnex(event.target.checked)} />
        Inclure l'annexe : vos données
      </label>
    </div>
  );
}
