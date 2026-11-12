// Client d'authentification FinOVA.
// Le jeton d'accès reste en mémoire (jamais dans localStorage) ; le refresh est
// un cookie HttpOnly + un jeton CSRF en double soumission (cookie lisible + en-tête).

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  role: "admin" | "user";
  status: "invited" | "active" | "disabled";
  email_verified: boolean;
  created_at: string;
  updated_at: string;
  last_login_at: string | null;
  password_changed_at: string | null;
}

export interface AdminUser extends AuthUser {
  email_sent?: boolean;
}

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

let accessToken: string | null = null;
let refreshPromise: Promise<boolean> | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function csrfCookie(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)finova_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

function isSafeMethod(method: string): boolean {
  return method === "GET" || method === "HEAD" || method === "OPTIONS";
}

function withSession(url: string, init?: RequestInit): RequestInit {
  const headers = new Headers(init?.headers || {});
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  if (!isSafeMethod((init?.method || "GET").toUpperCase())) {
    const csrf = csrfCookie();
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }
  void url;
  return { ...init, headers, credentials: "same-origin" };
}

export function authFetch(url: string, init?: RequestInit): Promise<Response> {
  return fetch(url, withSession(url, init));
}

async function toApiError(response: Response): Promise<ApiError> {
  let detail = `Erreur HTTP ${response.status}`;
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") detail = body.detail;
    else if (Array.isArray(body?.detail)) {
      detail = body.detail
        .map((item: { loc?: unknown[]; msg?: string }) =>
          `${(item.loc || []).join(".")}: ${item.msg || "invalide"}`)
        .join(" · ");
    }
  } catch {
    /* message HTTP conservé */
  }
  return new ApiError(response.status, detail);
}

function notifyUnauthorized() {
  window.dispatchEvent(new CustomEvent("finova:unauthorized"));
}

/** Tente un refresh silencieux (cookie HttpOnly + CSRF). Un seul appel à la fois. */
export function refreshSession(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const csrf = csrfCookie();
      try {
        const response = await fetch("/api/auth/refresh", {
          method: "POST",
          credentials: "same-origin",
          headers: csrf ? { "X-CSRF-Token": csrf } : {},
        });
        if (!response.ok) {
          accessToken = null;
          return false;
        }
        const body = (await response.json()) as { access_token?: string };
        accessToken = body.access_token || null;
        return Boolean(accessToken);
      } catch {
        accessToken = null;
        return false;
      }
    })().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

/** Requête authentifiée : refresh + rejeu unique sur 401. */
export async function apiFetch(url: string, init?: RequestInit): Promise<Response> {
  let response = await authFetch(url, init);
  if (response.status === 401 && !url.startsWith("/api/auth/")) {
    if (await refreshSession()) response = await authFetch(url, init);
    if (response.status === 401) notifyUnauthorized();
  }
  return response;
}

export async function apiRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await apiFetch(url, init);
  if (!response.ok) throw await toApiError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

async function publicRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers || {});
  if (init?.body) headers.set("Content-Type", "application/json");
  const response = await fetch(url, { ...init, headers, credentials: "same-origin" });
  if (!response.ok) throw await toApiError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// ------------------------------------------------------------- auth public
export async function login(email: string, password: string): Promise<AuthUser> {
  const body = await publicRequest<{ access_token: string; user: AuthUser }>(
    "/api/auth/login",
    { method: "POST", body: JSON.stringify({ email, password }) },
  );
  accessToken = body.access_token;
  return body.user;
}

export async function logout(): Promise<void> {
  try {
    let csrf = csrfCookie();
    if (!csrf) {
      // Cookie CSRF absent (nettoyage navigateur) : le refresh en repose un.
      await refreshSession();
      csrf = csrfCookie();
    }
    await publicRequest<void>("/api/auth/logout", {
      method: "POST",
      headers: csrf ? { "X-CSRF-Token": csrf } : {},
    });
  } finally {
    accessToken = null;
  }
}

export async function getMe(): Promise<AuthUser> {
  // Rechargement de page : le jeton d'accès (en mémoire) est perdu, mais le
  // cookie HttpOnly permet de restaurer la session avant d'interroger /me.
  if (!accessToken) await refreshSession();
  const body = await apiRequest<{ user: AuthUser }>("/api/auth/me");
  return body.user;
}

export function requestPasswordReset(email: string): Promise<{ message: string }> {
  return publicRequest<{ message: string }>("/api/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function resetPassword(token: string, password: string): Promise<{ message: string }> {
  return publicRequest<{ message: string }>("/api/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, password }),
  });
}

export function activateAccount(token: string, password: string): Promise<{ message: string }> {
  return publicRequest<{ message: string }>("/api/auth/activate", {
    method: "POST",
    body: JSON.stringify({ token, password }),
  });
}

// -------------------------------------------------------------- admin only
export async function listUsers(): Promise<AdminUser[]> {
  const body = await apiRequest<{ users: AdminUser[]; count: number }>("/api/auth/admin/users");
  return body.users;
}

export async function inviteUser(input: {
  email: string;
  full_name: string;
  role: "admin" | "user";
}): Promise<AdminUser> {
  const body = await apiRequest<{ user: AdminUser }>("/api/auth/admin/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return body.user;
}

export async function resendInvitation(userId: string): Promise<AdminUser> {
  const body = await apiRequest<{ user: AdminUser }>(
    `/api/auth/admin/users/${encodeURIComponent(userId)}/resend-invitation`,
    { method: "POST" },
  );
  return body.user;
}

export async function updateUser(
  userId: string,
  patch: { role?: "admin" | "user"; status?: "active" | "disabled" },
): Promise<AdminUser> {
  const body = await apiRequest<{ user: AdminUser }>(
    `/api/auth/admin/users/${encodeURIComponent(userId)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    },
  );
  return body.user;
}
