import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ApiError, fetchUserDataMode, setUserDataMode } from "./api";
import type { UserDataMode } from "./types";
import { t } from "./i18n";

// « Vos données : IA externe » : choix par compte et par session (onglet), consentement
// toujours requis. Désactivé par défaut ; activer ouvre une boîte de consentement,
// désactiver est immédiat. La déconnexion remet l'option à « traitement local ».
// L'état est partagé entre le panneau Ask Finova et la page « Mes données ».
// Rendu : composants existants du design (sélecteur segmenté, pastilles d'état, panneau).

export interface UserDataControl {
  mode: UserDataMode | null;
  dialogOpen: boolean;
  error: string | null;
  busy: boolean;
  requestOn: () => void;
  turnOff: () => void;
  confirm: () => Promise<void>;
  cancel: () => void;
}

export function useUserDataMode(sessionId: string): UserDataControl {
  const [mode, setMode] = useState<UserDataMode | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetchUserDataMode(sessionId).then(setMode).catch(() => setMode(null));
  }, [sessionId]);

  const update = useCallback(async (enabled: boolean, consent: boolean) => {
    setBusy(true);
    setError(null);
    try {
      setMode(await setUserDataMode(sessionId, enabled, consent));
      return true;
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
      return false;
    } finally {
      setBusy(false);
    }
  }, [sessionId]);

  return {
    mode, dialogOpen, error, busy,
    requestOn: () => { setError(null); setDialogOpen(true); },
    turnOff: () => { void update(false, false); },
    confirm: async () => { if (await update(true, true)) setDialogOpen(false); },
    cancel: () => { setError(null); setDialogOpen(false); },
  };
}

export function UserDataBadge({ mode }: { mode: UserDataMode | null }) {
  const on = Boolean(mode?.enabled);
  return (
    <span className={`status ${on ? "status-warning" : "status-available"}`} role="status">
      {on
        ? t("Vos données : envoyées à {provider}", { provider: mode?.provider ?? "" })
        : t("Vos données : traitement local")}
    </span>
  );
}

export function UserDataSwitch({ control }: { control: UserDataControl }) {
  const { mode } = control;
  if (!mode) return <UserDataBadge mode={null} />;
  const available = mode.switch_available && mode.llm_available;
  const on = mode.enabled;
  return (
    <div className="ask-badges user-data-mode">
      {mode.switch_available && (
        <div className="display-controls" role="group" aria-label={t("Vos données : IA externe")}
          title={available ? undefined : mode.reason ?? undefined}>
          <div className="lang-switch">
            <button type="button" className={on ? "" : "active"} aria-pressed={!on}
              disabled={control.busy || !on} onClick={control.turnOff}>
              {t("Local")}
            </button>
            <button type="button" className={on ? "active" : ""} aria-pressed={on}
              disabled={control.busy || on || !available} onClick={control.requestOn}>
              {t("IA externe")}
            </button>
          </div>
        </div>
      )}
      <UserDataBadge mode={mode} />
      {mode.suggested && !on && <span className="chip chip-semantic">{t("suggéré")}</span>}
      {!available && mode.reason && <span className="muted small">{t(mode.reason)}</span>}
    </div>
  );
}

export function ConsentDialog({ control }: { control: UserDataControl }) {
  const [accepted, setAccepted] = useState(false);
  const first = useRef<HTMLInputElement | null>(null);
  const provider = control.mode?.provider ?? t("le service d'IA");

  useEffect(() => {
    if (!control.dialogOpen) return;
    setAccepted(false);
    first.current?.focus();
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") control.cancel(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [control.dialogOpen]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!control.dialogOpen) return null;
  const sections: [string, string][] = [
    [t("Ce qui est envoyé"), t("La question et les valeurs de vos indicateurs utilisées pour répondre.")],
    [t("À qui"), t("{provider}, un service d'IA externe à BIFlow.", { provider })],
    [t("Ce qui n'est pas envoyé"), t("Vos fichiers complets et les données des autres sources.")],
    [t("Durée"), t("Pour cette session seulement (ce compte, cet onglet) : l'option revient à « traitement local » à la déconnexion, à la fermeture de l'onglet ou au redémarrage du serveur. Vous pouvez la désactiver à tout moment.")],
  ];
  return createPortal(
    <div className="sheet-overlay" onClick={control.cancel}>
      <div className="sheet" role="dialog" aria-modal="true" aria-labelledby="consent-title"
        onClick={(event) => event.stopPropagation()}>
        <div className="sheet-head">
          <div>
            <span className="eyebrow">{t("Vos données : IA externe")}</span>
            <h3 id="consent-title">{t("Envoyer vos données à {provider} ?", { provider })}</h3>
          </div>
          <button className="icon-btn" onClick={control.cancel} aria-label={t("Fermer")}>×</button>
        </div>
        <div className="explain-body">
          {sections.map(([heading, body]) => (
            <section key={heading} className="explain-block">
              <h4>{heading}</h4>
              <p>{body}</p>
            </section>
          ))}
        </div>
        <label className="inline-check">
          <input ref={first} type="checkbox" checked={accepted} onChange={(event) => setAccepted(event.target.checked)} />
          {t("J'accepte que mes données soient envoyées à {provider} pour cette session", { provider })}
        </label>
        {control.error && <p className="auth-error" role="alert">{t(control.error)}</p>}
        <div className="explain-actions">
          <button className="why-pill" onClick={control.cancel} disabled={control.busy}>{t("Annuler")}</button>
          <button className="primary-btn" onClick={() => void control.confirm()} disabled={!accepted || control.busy}>
            {t("Activer")}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
