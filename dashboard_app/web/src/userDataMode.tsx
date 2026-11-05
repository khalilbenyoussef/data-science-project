import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, fetchUserDataMode, setUserDataMode } from "./api";
import type { UserDataMode } from "./types";

// « Vos données : IA externe » : choix par session (onglet), consentement toujours requis.
// Désactivé par défaut ; activer ouvre une boîte de consentement, désactiver est immédiat.
// L'état est partagé entre le panneau Ask Finova et la page « Mes données ».

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
    <span className={`user-mode-badge ${on ? "on" : "off"}`} role="status">
      {on ? `Vos données : envoyées à ${mode?.provider}` : "Vos données : traitement local"}
    </span>
  );
}

export function UserDataSwitch({ control }: { control: UserDataControl }) {
  const { mode } = control;
  if (!mode) return <UserDataBadge mode={null} />;
  const available = mode.switch_available && mode.llm_available;
  return (
    <div className="user-mode">
      {mode.switch_available && (
        <label className={`user-mode-switch ${available ? "" : "disabled"}`}
          title={available ? undefined : mode.reason ?? undefined}>
          <input
            type="checkbox"
            role="switch"
            aria-checked={mode.enabled}
            checked={mode.enabled}
            disabled={!available || control.busy}
            onChange={(event) => (event.target.checked ? control.requestOn() : control.turnOff())}
          />
          <span className="track" aria-hidden="true"><span className="thumb" /></span>
          <span>Vos données : IA externe</span>
          {mode.suggested && !mode.enabled && <span className="chip chip-suggested">suggéré</span>}
        </label>
      )}
      <UserDataBadge mode={mode} />
      {!available && mode.reason && <span className="muted small user-mode-reason">{mode.reason}</span>}
    </div>
  );
}

export function ConsentDialog({ control }: { control: UserDataControl }) {
  const [accepted, setAccepted] = useState(false);
  const first = useRef<HTMLInputElement | null>(null);
  const provider = control.mode?.provider ?? "le service d'IA";

  useEffect(() => {
    if (!control.dialogOpen) return;
    setAccepted(false);
    first.current?.focus();
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") control.cancel(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [control.dialogOpen]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!control.dialogOpen) return null;
  return (
    <div className="modal-backdrop" onClick={control.cancel}>
      <div className="modal consent-modal" role="dialog" aria-modal="true" aria-labelledby="consent-title"
        onClick={(event) => event.stopPropagation()}>
        <h3 id="consent-title">Envoyer vos données à {provider} ?</h3>
        <dl className="consent-list">
          <dt>Ce qui est envoyé</dt>
          <dd>La question et les valeurs de vos indicateurs utilisées pour répondre.</dd>
          <dt>À qui</dt>
          <dd>{provider}, un service d'IA externe à BIFlow.</dd>
          <dt>Ce qui n'est pas envoyé</dt>
          <dd>Vos fichiers complets et les données des autres sources.</dd>
          <dt>Durée</dt>
          <dd>Pour cette session seulement (cet onglet) : l'option revient à « traitement local » à la
            fermeture de l'onglet ou au redémarrage du serveur. Vous pouvez la désactiver à tout moment.</dd>
        </dl>
        <label className="inline-check consent-check">
          <input ref={first} type="checkbox" checked={accepted} onChange={(event) => setAccepted(event.target.checked)} />
          J'accepte que mes données soient envoyées à {provider} pour cette session
        </label>
        {control.error && <p className="warning-text small">{control.error}</p>}
        <div className="modal-actions">
          <button className="why-pill" onClick={control.cancel} disabled={control.busy}>Annuler</button>
          <button className="primary-btn" onClick={() => void control.confirm()} disabled={!accepted || control.busy}>
            Activer
          </button>
        </div>
      </div>
    </div>
  );
}
