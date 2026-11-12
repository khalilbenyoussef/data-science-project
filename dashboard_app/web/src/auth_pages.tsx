// Pages d'authentification FinOVA : connexion, mot de passe oublié,
// réinitialisation, activation et gestion des utilisateurs (admin).
import { FormEvent, ReactNode, useEffect, useState } from "react";
import {
  AdminUser, ApiError, AuthUser, activateAccount, inviteUser, listUsers,
  login, requestPasswordReset, resendInvitation, resetPassword, updateUser,
} from "./auth";
import { DisplayControls } from "./controls";
import { t } from "./i18n";
import { prettyDate } from "./format";

const ICON_USER = "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21c0-3.3 3.6-6 8-6s8 2.7 8 6";
const ICON_LOCK = "M7 11V8a5 5 0 0 1 10 0v3M5 11h14v10H5zM12 15v3";
const ICON_MAIL = "M3 6h18v12H3zM3 7l9 6 9-6";

function FieldIcon({ path }: { path: string }) {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={path} />
    </svg>
  );
}

export function detailOf(error: unknown): string {
  if (error instanceof ApiError) return error.detail;
  return t("Service indisponible. Vérifiez votre connexion puis réessayez.");
}

const LOGIN_VIDEOS = [
  "/media/login/login-01.mp4",
  "/media/login/login-02.mp4",
  "/media/login/login-03.mp4",
  "/media/login/login-04.mp4",
];

// Une image fixe par vidéo : elle remplit l'arrière-plan (floutée) quand la
// vidéo verticale est affichée en entier, sans bandes noires.
const LOGIN_POSTERS = [
  "/media/login/login-01.jpg",
  "/media/login/login-02.jpg",
  "/media/login/login-03.jpg",
  "/media/login/login-04.jpg",
];

function LoginBackdrop() {
  const [index, setIndex] = useState(0);
  // Vidéo verticale : on la montre en entier (object-fit: contain) au lieu de
  // la recadrer, sinon les visages sont coupés en haut.
  const [portrait, setPortrait] = useState(false);
  // Vidéos non versionnées (*.mp4 ignoré) : une vidéo introuvable est sautée ;
  // si aucune ne se charge, seul le fond statique de .login / .login-media reste.
  const [failed, setFailed] = useState<ReadonlySet<number>>(() => new Set());
  const next = (from: number, skip: ReadonlySet<number>) => {
    for (let step = 1; step <= LOGIN_VIDEOS.length; step += 1) {
      const candidate = (from + step) % LOGIN_VIDEOS.length;
      if (!skip.has(candidate)) return candidate;
    }
    return null;
  };
  const playable = failed.size < LOGIN_VIDEOS.length && !failed.has(index);
  return (
    <div className={`login-media${portrait ? " is-portrait" : ""}`} aria-hidden="true">
      <div
        className="login-media-fill"
        style={{ backgroundImage: `url(${LOGIN_POSTERS[index]})` }}
      />
      {playable && (
        <video
          key={LOGIN_VIDEOS[index]}
          src={LOGIN_VIDEOS[index]}
          autoPlay
          muted
          playsInline
          preload="auto"
          onLoadedMetadata={(event) => {
            const video = event.currentTarget;
            setPortrait(video.videoHeight > video.videoWidth);
          }}
          onEnded={() => setIndex((current) => next(current, failed) ?? current)}
          onError={() => {
            const skip = new Set(failed).add(index);
            setFailed(skip);
            const candidate = next(index, skip);
            if (candidate !== null) setIndex(candidate);
          }}
        />
      )}
    </div>
  );
}

function BrandMark() {
  return (
    <div className="login-logo" role="img" aria-label="FinOVA">
      <img className="login-mark" src="/brand/finova-mark.png" alt="" aria-hidden="true" />
      <span className="login-word" aria-hidden="true" />
    </div>
  );
}

function AuthScreen({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <div className="login auth-screen">
      <LoginBackdrop />
      <DisplayControls floating />
      <BrandMark />
      <section className="login-brand">
        <h1>{t("Les chiffres d'abord.")}<br />{t("Les sources toujours.")}</h1>
        <p>
          {t(
            "FinOVA rassemble des chiffres publics sur les services financiers — compte bancaire, épargne, crédit — les vérifie, puis vous les explique simplement.",
          )}
        </p>
      </section>
      <section className="login-card">
        <h2>{title}</h2>
        {subtitle && <p className="auth-subtitle">{subtitle}</p>}
        {children}
      </section>
    </div>
  );
}

function AuthLink({ href, children }: { href: string; children: ReactNode }) {
  return <a className="auth-link" href={href}>{children}</a>;
}

export function LoginPage({ onEnter }: { onEnter: (user: AuthUser) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    login(email.trim(), password)
      .then((user) => {
        if (window.location.pathname !== "/") {
          window.history.replaceState({}, "", "/");
        }
        onEnter(user);
      })
      .catch((err) => setError(detailOf(err)))
      .finally(() => setBusy(false));
  };

  return (
    <div className="login">
      <LoginBackdrop />
      <DisplayControls floating />
      <BrandMark />
      <section className="login-brand">
        <h1>{t("Les chiffres d'abord.")}<br />{t("Les sources toujours.")}</h1>
        <p>
          {t(
            "FinOVA rassemble des chiffres publics sur les services financiers — compte bancaire, épargne, crédit — les vérifie, puis vous les explique simplement.",
          )}{" "}
          {t(
            "Pas besoin d'être spécialiste : chaque page dit ce que le chiffre signifie, d'où il vient et ce qu'il ne permet pas de conclure.",
          )}
        </p>
      </section>
      <section className="login-card">
        <h2>{t("Connexion")}</h2>
        <p className="auth-subtitle">{t("Accès réservé aux comptes autorisés.")}</p>
        <form onSubmit={submit}>
          <label>
            {t("Adresse email")}
            <span className="login-field">
              <FieldIcon path={ICON_MAIL} />
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="username"
                autoFocus
                required
                placeholder="prenom.nom@organisation.tn"
              />
            </span>
          </label>
          <label>
            {t("Mot de passe")}
            <span className="login-field">
              <FieldIcon path={ICON_LOCK} />
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                required
              />
            </span>
          </label>
          {error && <p className="auth-error" role="alert">{error}</p>}
          <button className={`primary-btn wide ${busy ? "is-busy" : ""}`} type="submit" disabled={busy}>
            {busy ? t("Connexion…") : t("S'authentifier")}
          </button>
          <div className="auth-links">
            <AuthLink href="/forgot-password">{t("Mot de passe oublié ?")}</AuthLink>
          </div>
        </form>
      </section>
    </div>
  );
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    requestPasswordReset(email.trim())
      .then(() => setSent(true))
      .catch((err) => setError(detailOf(err)))
      .finally(() => setBusy(false));
  };

  return (
    <AuthScreen
      title={t("Mot de passe oublié")}
      subtitle={t(
        "Indiquez l'adresse associée à votre compte. Pour des raisons de sécurité, la réponse est toujours la même.",
      )}
    >
      {sent ? (
        <div className="auth-success" role="status">
          <p>
            {t(
              "Si un compte correspond à cette adresse, un lien de réinitialisation vient d'être envoyé. Il est valable 15 minutes et ne peut être utilisé qu'une seule fois.",
            )}
          </p>
          <p className="muted small">
            {t(
              "Pensez à vérifier les indésirables. Sans SMTP configuré, le lien est écrit par le serveur dans data/auth/outbox/.",
            )}
          </p>
          <AuthLink href="/login">{t("Retour à la connexion")}</AuthLink>
        </div>
      ) : (
        <form onSubmit={submit}>
          <label>
            {t("Adresse email")}
            <span className="login-field">
              <FieldIcon path={ICON_MAIL} />
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="username"
                autoFocus
                required
              />
            </span>
          </label>
          {error && <p className="auth-error" role="alert">{error}</p>}
          <button className={`primary-btn wide ${busy ? "is-busy" : ""}`} type="submit" disabled={busy}>
            {busy ? t("Envoi…") : t("Envoyer le lien")}
          </button>
          <div className="auth-links">
            <AuthLink href="/login">{t("Retour à la connexion")}</AuthLink>
          </div>
        </form>
      )}
    </AuthScreen>
  );
}

function tokenFromUrl(): string {
  return new URLSearchParams(window.location.search).get("token") || "";
}

function PasswordFields({
  password, confirm, onPassword, onConfirm,
}: {
  password: string;
  confirm: string;
  onPassword: (value: string) => void;
  onConfirm: (value: string) => void;
}) {
  return (
    <>
      <label>
        {t("Nouveau mot de passe")}
        <span className="login-field">
          <FieldIcon path={ICON_LOCK} />
          <input
            type="password"
            value={password}
            onChange={(event) => onPassword(event.target.value)}
            autoComplete="new-password"
            minLength={10}
            required
            autoFocus
          />
        </span>
      </label>
      <label>
        {t("Confirmer le mot de passe")}
        <span className="login-field">
          <FieldIcon path={ICON_LOCK} />
          <input
            type="password"
            value={confirm}
            onChange={(event) => onConfirm(event.target.value)}
            autoComplete="new-password"
            minLength={10}
            required
          />
        </span>
      </label>
      <p className="auth-hint">
        {t("10 caractères minimum, avec au moins une lettre et un chiffre.")}
      </p>
    </>
  );
}

export function ResetPasswordPage() {
  const [token] = useState(tokenFromUrl);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    if (password !== confirm) {
      setError(t("Les deux mots de passe ne correspondent pas."));
      return;
    }
    setBusy(true);
    setError(null);
    resetPassword(token, password)
      .then(() => setDone(true))
      .catch((err) => setError(detailOf(err)))
      .finally(() => setBusy(false));
  };

  if (!token) {
    return (
      <AuthScreen title={t("Lien invalide")} subtitle={t("Ce lien de réinitialisation est incomplet.")}>
        <p className="auth-error" role="alert">
          {t("Ouvrez le lien reçu par email, ou demandez-en un nouveau.")}
        </p>
        <AuthLink href="/forgot-password">{t("Demander un nouveau lien")}</AuthLink>
      </AuthScreen>
    );
  }

  return (
    <AuthScreen
      title={t("Nouveau mot de passe")}
      subtitle={t(
        "Choisissez un mot de passe robuste. Toutes vos sessions seront déconnectées après validation.",
      )}
    >
      {done ? (
        <div className="auth-success" role="status">
          <p>{t("Votre mot de passe a été réinitialisé. Vous pouvez vous connecter.")}</p>
          <AuthLink href="/login">{t("Se connecter")}</AuthLink>
        </div>
      ) : (
        <form onSubmit={submit}>
          <PasswordFields
            password={password}
            confirm={confirm}
            onPassword={setPassword}
            onConfirm={setConfirm}
          />
          {error && <p className="auth-error" role="alert">{error}</p>}
          <button className={`primary-btn wide ${busy ? "is-busy" : ""}`} type="submit" disabled={busy}>
            {busy ? t("Validation…") : t("Réinitialiser le mot de passe")}
          </button>
          <div className="auth-links">
            <AuthLink href="/login">{t("Retour à la connexion")}</AuthLink>
          </div>
        </form>
      )}
    </AuthScreen>
  );
}

export function ActivatePage() {
  const [token] = useState(tokenFromUrl);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    if (password !== confirm) {
      setError(t("Les deux mots de passe ne correspondent pas."));
      return;
    }
    setBusy(true);
    setError(null);
    activateAccount(token, password)
      .then(() => setDone(true))
      .catch((err) => setError(detailOf(err)))
      .finally(() => setBusy(false));
  };

  if (!token) {
    return (
      <AuthScreen title={t("Invitation invalide")} subtitle={t("Ce lien d'activation est incomplet.")}>
        <p className="auth-error" role="alert">
          {t(
            "Ouvrez le lien reçu par email. S'il a expiré, demandez à un administrateur de renvoyer l'invitation.",
          )}
        </p>
        <AuthLink href="/login">{t("Retour à la connexion")}</AuthLink>
      </AuthScreen>
    );
  }

  return (
    <AuthScreen
      title={t("Activer votre compte")}
      subtitle={t(
        "Choisissez votre mot de passe pour finaliser la création de votre compte FinOVA.",
      )}
    >
      {done ? (
        <div className="auth-success" role="status">
          <p>{t("Votre compte est activé. Vous pouvez vous connecter.")}</p>
          <AuthLink href="/login">{t("Se connecter")}</AuthLink>
        </div>
      ) : (
        <form onSubmit={submit}>
          <PasswordFields
            password={password}
            confirm={confirm}
            onPassword={setPassword}
            onConfirm={setConfirm}
          />
          {error && <p className="auth-error" role="alert">{error}</p>}
          <button className={`primary-btn wide ${busy ? "is-busy" : ""}`} type="submit" disabled={busy}>
            {busy ? t("Activation…") : t("Activer mon compte")}
          </button>
          <div className="auth-links">
            <AuthLink href="/login">{t("Retour à la connexion")}</AuthLink>
          </div>
        </form>
      )}
    </AuthScreen>
  );
}

const STATUS_LABELS: Record<AdminUser["status"], string> = {
  invited: "Invitation en attente",
  active: "Actif",
  disabled: "Désactivé",
};

export function AdminUsersPage({ currentUser }: { currentUser: AuthUser }) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<"admin" | "user">("user");
  const [creating, setCreating] = useState(false);

  const reload = () => {
    setLoading(true);
    listUsers()
      .then((items) => {
        setUsers(items);
        setError(null);
      })
      .catch((err) => setError(detailOf(err)))
      .finally(() => setLoading(false));
  };

  useEffect(reload, []);

  const create = (event: FormEvent) => {
    event.preventDefault();
    if (creating) return;
    setCreating(true);
    setError(null);
    setNotice(null);
    inviteUser({ email: email.trim(), full_name: fullName.trim(), role })
      .then((user) => {
        setEmail("");
        setFullName("");
        setRole("user");
        setNotice(
          user.email_sent
            ? t("Invitation envoyée à {email}.", { email: user.email })
            : t(
                "Compte créé pour {email}, mais l'email n'a pas pu être envoyé. Vérifiez la configuration SMTP puis utilisez « Renvoyer ».",
                { email: user.email },
              ),
        );
        reload();
      })
      .catch((err) => setError(detailOf(err)))
      .finally(() => setCreating(false));
  };

  const mutate = (userId: string, action: () => Promise<unknown>, message: string) => {
    setBusyId(userId);
    setError(null);
    setNotice(null);
    action()
      .then(() => {
        setNotice(message);
        reload();
      })
      .catch((err) => setError(detailOf(err)))
      .finally(() => setBusyId(null));
  };

  return (
    <section className="admin-page">
      <div className="admin-head">
        <div>
          <span className="eyebrow">{t("Administration")}</span>
          <h2>{t("Utilisateurs")}</h2>
          <p className="muted">
            {t(
              "Les comptes sont créés uniquement sur invitation. Aucune inscription publique n'est possible.",
            )}
          </p>
        </div>
        <span className="admin-count">{t("{count} compte(s)", { count: users.length })}</span>
      </div>

      <form className="admin-create" onSubmit={create}>
        <label>
          {t("Email")}
          <span className="login-field">
            <FieldIcon path={ICON_MAIL} />
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="analyste@organisation.tn"
              required
            />
          </span>
        </label>
        <label>
          {t("Nom complet")}
          <span className="login-field">
            <FieldIcon path={ICON_USER} />
            <input
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              placeholder="Prénom Nom"
              maxLength={120}
            />
          </span>
        </label>
        <label>
          {t("Rôle")}
          <select value={role} onChange={(event) => setRole(event.target.value as "admin" | "user")}>
            <option value="user">{t("Utilisateur")}</option>
            <option value="admin">{t("Administrateur")}</option>
          </select>
        </label>
        <button className={`primary-btn ${creating ? "is-busy" : ""}`} type="submit" disabled={creating}>
          {creating ? t("Envoi…") : t("Inviter")}
        </button>
      </form>

      {error && <p className="auth-error" role="alert">{error}</p>}
      {notice && <p className="auth-note" role="status">{notice}</p>}

      {loading && users.length === 0 ? (
        <p className="muted">{t("Chargement des comptes…")}</p>
      ) : (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>{t("Utilisateur")}</th>
                <th>{t("Rôle")}</th>
                <th>{t("Statut")}</th>
                <th>{t("Dernière connexion")}</th>
                <th>{t("Actions")}</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => {
                const self = user.id === currentUser.id;
                const busy = busyId === user.id;
                return (
                  <tr key={user.id}>
                    <td>
                      <strong>{user.email}</strong>
                      <span className="muted small admin-name">
                        {user.full_name || "—"}{self ? t(" · vous") : ""}
                      </span>
                    </td>
                    <td>
                      <select
                        value={user.role}
                        disabled={busy || self}
                        onChange={(event) => {
                          const nextRole = event.target.value as "admin" | "user";
                          mutate(
                            user.id,
                            () => updateUser(user.id, { role: nextRole }),
                            t("Rôle de {email} mis à jour.", { email: user.email }),
                          );
                        }}
                      >
                        <option value="user">{t("Utilisateur")}</option>
                        <option value="admin">{t("Administrateur")}</option>
                      </select>
                    </td>
                    <td>
                      <span className={`admin-status ${user.status}`}>
                        {t(STATUS_LABELS[user.status])}
                      </span>
                    </td>
                    <td className="muted small">{prettyDate(user.last_login_at)}</td>
                    <td>
                      <div className="admin-actions">
                        {user.status === "invited" && (
                          <button
                            className="ghost-btn"
                            disabled={busy}
                            onClick={() => mutate(
                              user.id,
                              () => resendInvitation(user.id),
                              t("Invitation renvoyée à {email}.", { email: user.email }),
                            )}
                          >
                            {t("Renvoyer")}
                          </button>
                        )}
                        {user.status !== "invited" && !self && (
                          <button
                            className="ghost-btn"
                            disabled={busy}
                            onClick={() => mutate(
                              user.id,
                              () => updateUser(user.id, {
                                status: user.status === "active" ? "disabled" : "active",
                              }),
                              user.status === "active"
                                ? t("{email} désactivé, sessions révoquées.", { email: user.email })
                                : t("{email} réactivé.", { email: user.email }),
                            )}
                          >
                            {user.status === "active" ? t("Désactiver") : t("Réactiver")}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
              {users.length === 0 && !loading && (
                <tr>
                  <td colSpan={5} className="muted">
                    {t("Aucun compte pour le moment. Invitez le premier utilisateur.")}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
