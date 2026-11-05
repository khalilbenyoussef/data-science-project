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
