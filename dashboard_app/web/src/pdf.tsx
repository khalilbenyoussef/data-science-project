import { useState } from "react";
import { apiFetch } from "./auth";
import { t } from "./i18n";

// Téléchargement authentifié d'un rapport PDF construit à la demande par l'API.
// Le lien direct ne porte pas le jeton (celui-ci reste en mémoire) : on récupère
// le fichier via apiFetch puis on déclenche le téléchargement d'un blob local.
function filenameFrom(href: string, title: string): string {
  const last = (href.split("?")[0].split("/").pop() || "").toLowerCase();
  if (last.endsWith(".pdf")) return last;
  const slug = title
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return `${slug || "rapport-finova"}.pdf`;
}

export function PdfDownload({ href, title }: { href: string; title: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const download = async (event: React.MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const response = await apiFetch(href);
      if (!response.ok) {
        throw new Error(
          response.status === 401
            ? t("Session expirée : reconnectez-vous pour télécharger le rapport.")
            : t("Téléchargement impossible (HTTP {status}).", { status: response.status }),
        );
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filenameFrom(href, title);
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("Téléchargement impossible."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <a
        className="primary-btn pdf-download"
        href={href}
        onClick={download}
        aria-busy={busy}
        title={title}
      >
        <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
          <path d="M12 4v11m0 0-4-4m4 4 4-4M5 19h14" fill="none" stroke="currentColor" strokeWidth="2"
                strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        {busy ? t("Préparation du PDF…") : t("Télécharger le rapport (PDF)")}
      </a>
      {error && <span className="auth-error pdf-error" role="alert">{error}</span>}
    </>
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
      <label className="inline-check small" title={t("Ajoute une annexe séparée avec vos données.")}>
        <input type="checkbox" checked={annex} onChange={(event) => setAnnex(event.target.checked)} />
        {t("Inclure l'annexe : vos données")}
      </label>
    </div>
  );
}
