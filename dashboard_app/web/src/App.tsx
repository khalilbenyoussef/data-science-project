import { useEffect, useRef, useState } from "react";
import type { AskResult, Notice, Spec } from "./types";
import { ApiError, askFinova, fetchSpec } from "./api";
import { AuthUser, getMe, logout } from "./auth";
import {
  ActivatePage, AdminUsersPage, ForgotPasswordPage, LoginPage, ResetPasswordPage,
  detailOf,
} from "./auth_pages";
import { PageView } from "./pages";
import { AskDock, ChatMessage, NoticeList } from "./ui";
import { MyDataPage } from "./sources";
import { AuditPage } from "./audit";
import { prettyDate } from "./format";
import { WaveNavContext } from "./waveNav";
import { PAGE_COPY, plainText } from "./copy";
import { DisplayControls } from "./controls";
import { t, tr } from "./i18n";
import { usePreferences } from "./preferences";
import { ConsentDialog, useUserDataMode } from "./userDataMode";

// page « Mes données » : hors contrat Finova (sources CSV de l'utilisateur)
const MYDATA = "mydata";
// page « Audit et confiance » : rapport d'audit officiel (hors contrat Finova)
const AUDIT = "audit";
// page « Utilisateurs » : administration des comptes (admin uniquement)
const ADMIN = "admin";
const LOCAL_PAGES = new Set([MYDATA, AUDIT, ADMIN]);

const NAV = [
  { id: "overview", label: "Vue d'ensemble", icon: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z" },
  { id: "inclusion", label: "Inclusion et inégalités", icon: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21c0-3.3 3.6-6 8-6s8 2.7 8 6" },
  { id: "access", label: "Accès et crédit", icon: "M3 21h18M5 21V7l7-4 7 4v14M9 21v-5h6v5" },
  { id: "exclusion", label: "Pourquoi l'exclusion ?", icon: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM9.5 9a2.5 2.5 0 1 1 3.6 2.2c-.8.5-1.1 1-1.1 1.8M12 17h.01" },
  { id: "pipeline", label: "Sources et qualité", icon: "M4 6h16M4 12h16M4 18h16M8 4v4M16 10v4M10 16v4" },
  { id: MYDATA, label: "Mes données", icon: "M12 16V4m0 0-4 4m4-4 4 4M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" },
  { id: AUDIT, label: "Audit et confiance", icon: "M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6l8-3zm-3 9 2 2 4-4" },
];

const ADMIN_NAV = {
  id: ADMIN, label: "Utilisateurs",
  icon: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM19 8v6M22 11h-6",
};

// conversation Ask Finova gardee pour la session du navigateur (sessionStorage)
const CHAT_KEY = "finova.chat";
const SESSION_KEY = "finova.session";
// « Vos données : IA externe » : boîte de consentement proposée une fois par session si la
// configuration la suggère (la session reste locale tant que l'utilisateur n'a pas accepté)
const PROPOSED_KEY = "finova.userDataProposed";

function readStored<T>(key: string, fallback: T): T {
  try {
    const raw = window.sessionStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function writeStored(key: string, value: unknown) {
  try {
    window.sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* stockage indisponible : la conversation reste en memoire */
  }
}

function sessionId(): string {
  const existing = readStored<string | null>(SESSION_KEY, null);
  if (existing) return existing;
  const created = `s-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  writeStored(SESSION_KEY, created);
  return created;
}

// pages Findex : bandeau quand la vue reprend une enquete anterieure
const WAVE_PAGES = new Set(["overview", "inclusion", "exclusion"]);

const COUNTRIES = [
  { iso3: "TUN", name: "Tunisie" },
  { iso3: "DZA", name: "Algérie" },
  { iso3: "EGY", name: "Égypte" },
  { iso3: "JOR", name: "Jordanie" },
  { iso3: "MAR", name: "Maroc" },
];

function Icon({ path }: { path: string }) {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={path} />
    </svg>
  );
}

type AuthState =
  | { status: "loading" }
  | { status: "error"; detail: string }
  | { status: "anonymous" }
  | { status: "authenticated"; user: AuthUser };

function AuthSplash({ detail, onRetry }: { detail?: string; onRetry?: () => void }) {
  return (
    <div className="auth-gate" role={detail ? "alert" : "status"} aria-live="polite">
      <img className="auth-gate-mark" src="/brand/finova-mark.png" alt="" aria-hidden="true" />
      {detail ? (
        <>
          <h1>{t("Connexion indisponible")}</h1>
          <p className="muted">{detail}</p>
          {onRetry && (
            <button className="primary-btn" onClick={onRetry}>{t("Réessayer")}</button>
          )}
        </>
      ) : (
        <>
          <span className="spinner" aria-hidden="true" />
          <p className="muted">{t("Vérification de votre session…")}</p>
        </>
      )}
    </div>
  );
}

export function App() {
  // abonnement aux préférences : changer de langue ou de thème re-rend toute l'interface
  usePreferences();
  const [path] = useState(() => window.location.pathname);
  if (path === "/forgot-password") return <ForgotPasswordPage />;
  if (path === "/reset-password") return <ResetPasswordPage />;
  if (path === "/activate") return <ActivatePage />;
  return <AuthGate initialAdmin={path === "/admin/users"} />;
}

function AuthGate({ initialAdmin }: { initialAdmin: boolean }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let alive = true;
    setState({ status: "loading" });
    getMe()
      .then((user) => {
        if (alive) setState({ status: "authenticated", user });
      })
      .catch((err) => {
        if (!alive) return;
        if (err instanceof ApiError && err.status === 401) {
          setState({ status: "anonymous" });
        } else {
          setState({ status: "error", detail: detailOf(err) });
        }
      });
    return () => {
      alive = false;
    };
  }, [attempt]);

  useEffect(() => {
    const onUnauthorized = () => setState({ status: "anonymous" });
    window.addEventListener("finova:unauthorized", onUnauthorized);
    return () => window.removeEventListener("finova:unauthorized", onUnauthorized);
  }, []);

  if (state.status === "loading") return <AuthSplash />;
  if (state.status === "error") {
    return (
      <AuthSplash detail={state.detail} onRetry={() => setAttempt((value) => value + 1)} />
    );
  }
  if (state.status === "anonymous") {
    return (
      <LoginPage
        onEnter={(user) => setState({ status: "authenticated", user })}
      />
    );
  }
  return (
    <Dashboard
      user={state.user}
      initialPage={initialAdmin && state.user.role === "admin" ? ADMIN : "overview"}
      onLogout={() => {
        try {
          window.sessionStorage.removeItem(PROPOSED_KEY);
        } catch {
          /* stockage indisponible */
        }
        logout()
          .catch(() => undefined)
          .finally(() => window.location.assign("/login"));
      }}
    />
  );
}

function Dashboard({
  user,
  onLogout,
  initialPage,
}: {
  user: AuthUser;
  onLogout: () => void;
  initialPage: string;
}) {
  const { lang } = usePreferences();
  const [pageId, setPageId] = useState(initialPage);
  const [iso3, setIso3] = useState("TUN");
  const [year, setYear] = useState(2024);
  const [years, setYears] = useState<number[]>([]);
  const [spec, setSpec] = useState<Spec | null>(null);
  const [source, setSource] = useState("file");
  const [loading, setLoading] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [askOpen, setAskOpen] = useState(false);
  const userData = useUserDataMode(sessionId());
  useEffect(() => {
    if (!askOpen || !userData.mode?.suggested || userData.mode.enabled) return;
    if (readStored<boolean>(PROPOSED_KEY, false)) return;
    writeStored(PROPOSED_KEY, true);
    userData.requestOn();
  }, [askOpen, userData.mode]); // eslint-disable-line react-hooks/exhaustive-deps
  const [messages, setMessages] = useState<ChatMessage[]>(() => readStored(CHAT_KEY, []));
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  const cache = useRef(new Map<string, { spec: Spec; source: string }>());
  // design : indicateur de navigation, barre de lecture et halo au survol
  const navRef = useRef<HTMLElement | null>(null);
  const navButtons = useRef(new Map<string, HTMLButtonElement>());
  const topbarRef = useRef<HTMLElement | null>(null);
  const progressRef = useRef<HTMLSpanElement | null>(null);
  const [navMarker, setNavMarker] = useState({ top: 0, height: 0 });
  const firstPage = useRef(true);

  const key = `${iso3}-${year}`;
  // vagues du pays selectionne seulement (TUN sans 2011, MAR a partir de 2017)
  const surveyYears = spec?.country.iso3 === iso3 ? spec.survey_years ?? [] : [];
  const wave =
    spec?.findex_wave &&
    spec.findex_wave.year_used !== null &&
    spec.findex_wave.year_used !== spec.findex_wave.year_requested
      ? spec.findex_wave
      : null;

  useEffect(() => {
    if (!loading) {
      setElapsed(0);
      return;
    }
    setElapsed(0);
    const timer = window.setInterval(
      () => setElapsed((value) => value + 1),
      1000,
    );
    return () => window.clearInterval(timer);
  }, [loading]);

  useEffect(() => {
    const cached = cache.current.get(key);
    if (cached) {
      setSpec(cached.spec);
      setSource(cached.source);
      setLoading(false);
      setError(null);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetchSpec(iso3, year, controller.signal)
      .then((result) => {
        cache.current.set(key, result);
        setSpec(result.spec);
        setSource(result.source);
        setYears((current) => {
          const merged = Array.from(new Set([...current, ...result.spec.years])).sort((a, b) => a - b);
          return merged.length ? merged : current;
        });
        setPageId((current) =>
          LOCAL_PAGES.has(current) || result.spec.pages.some((item) => item.id === current) ? current : "overview");
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        const detail = err instanceof ApiError ? err.detail : String(err);
        setError(detail || t("Impossible de charger le contrat Finova."));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
    // pageId intentionally excluded: switching pages must not refetch
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [iso3, year, reload]);

  // pastille de navigation : suit l'élément actif, même en arabe ou en repli icônes
  useEffect(() => {
    const measure = () => {
      const nav = navRef.current;
      const active = navButtons.current.get(pageId);
      if (!nav || !active) return;
      const navBox = nav.getBoundingClientRect();
      const box = active.getBoundingClientRect();
      setNavMarker({ top: box.top - navBox.top, height: box.height });
    };
    measure();
    const nav = navRef.current;
    const observer = nav ? new ResizeObserver(measure) : null;
    if (nav && observer) observer.observe(nav);
    window.addEventListener("resize", measure);
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [pageId, lang, user.role]);

  // retour en haut lors d'un changement de page ou de sélection (expérience mobile)
  useEffect(() => {
    if (firstPage.current) {
      firstPage.current = false;
      return;
    }
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: 0, behavior: reduced ? "auto" : "smooth" });
  }, [pageId, iso3, year]);

  // barre de lecture + ombre de la barre supérieure, sans re-rendu React
  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      const root = document.documentElement;
      const max = root.scrollHeight - window.innerHeight;
      const ratio = max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0;
      if (progressRef.current) progressRef.current.style.transform = `scaleX(${ratio})`;
      topbarRef.current?.classList.toggle("is-scrolled", window.scrollY > 6);
    };
    const onScroll = () => {
      if (frame) return;
      frame = window.requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, []);

  // halo qui suit le curseur sur les cartes (pointeur fin uniquement)
  useEffect(() => {
    if (!window.matchMedia?.("(hover: hover) and (pointer: fine)").matches) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    let frame = 0;
    let target: HTMLElement | null = null;
    let x = 0;
    let y = 0;
    const apply = () => {
      frame = 0;
      if (!target) return;
      const box = target.getBoundingClientRect();
      target.style.setProperty("--mx", `${((x - box.left) / box.width) * 100}%`);
      target.style.setProperty("--my", `${((y - box.top) / box.height) * 100}%`);
    };
    const onMove = (event: PointerEvent) => {
      const element = (event.target as HTMLElement | null)?.closest?.(
        ".metric-card, .chart-card, .info-card, .source-card, .panel",
      ) as HTMLElement | null;
      if (!element) return;
      target = element;
      x = event.clientX;
      y = event.clientY;
      if (!frame) frame = window.requestAnimationFrame(apply);
    };
    document.addEventListener("pointermove", onMove, { passive: true });
    return () => {
      document.removeEventListener("pointermove", onMove);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, []);

  // Ctrl/⌘ K ouvre Ask Finova, Échap le referme
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setAskOpen(true);
      } else if (event.key === "Escape") {
        setAskOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const page = spec?.pages.find((item) => item.id === pageId) ?? spec?.pages[0];
  const askBlock = spec?.pages
    .find((item) => item.id === "exclusion")
    ?.blocks.find((block) => block.kind === "ask");
  const rawSuggestions = (askBlock?.payload as { suggestions?: string[] } | undefined)?.suggestions ?? [
    "Combien d'adultes ont un compte ?",
    "Pourquoi l'écart femmes-hommes est-il élevé ?",
    "Les ATMs ont-ils augmenté depuis 2017 ?",
  ];
  const suggestions = rawSuggestions.map((item) => t(item));
  const rules = (askBlock?.payload as { rules?: string[] } | undefined)?.rules ?? [];

  useEffect(() => {
    writeStored(CHAT_KEY, messages.slice(-40));
  }, [messages]);

  const submitAsk = (question: string) => {
    const text = question.trim();
    if (!text || busy) return;
    setAskOpen(true);
    // historique de la session du navigateur : derniers echanges (hors erreurs)
    const history = messages
      .filter((message) => !message.isError)
      .slice(-10)
      .map((message) => ({ role: message.role, text: message.text.slice(0, 2000) }));
    setMessages((current) => [...current, { role: "user", text }]);
    setBusy(true);
    askFinova(text, iso3, year, { page: page?.id, session_id: sessionId(), history })
      .then((result: AskResult) => {
        setMessages((current) => [
          ...current,
          { role: "assistant", text: result.answer, result },
        ]);
      })
      .catch((err) => {
        const detail = err instanceof ApiError ? err.detail : String(err);
        setMessages((current) => [
          ...current,
          {
            role: "assistant",
            text: t("Réponse indisponible : {detail}", { detail }),
            isError: true,
          },
        ]);
      })
      .finally(() => setBusy(false));
  };

  const globalNotices: Notice[] = spec?.notices ?? [];
  const countryName = tr(
    COUNTRIES.find((item) => item.iso3 === iso3)?.name ?? iso3,
  );
  const navItems = user.role === "admin" ? [...NAV, ADMIN_NAV] : NAV;

  return (
    <div className="shell">
      <div className="app-ambient" aria-hidden="true">
        <span className="ambient-orb orb-a" />
        <span className="ambient-orb orb-b" />
        <span className="ambient-orb orb-c" />
      </div>
      <aside className="sidebar">
        <div className="brand">
          <img className="brand-logo brand-logo-on-light" src="/brand/finova-logo.png" alt="FinOVA" />
          <img
            className="brand-logo brand-logo-on-dark"
            src="/brand/finova-logo-light.png"
            alt=""
            aria-hidden="true"
          />
          <img className="brand-mark" src="/brand/finova-icon.png" alt="" aria-hidden="true" />
          <div>
            <strong>
              Fin<em>OVA</em>
            </strong>
          </div>
        </div>
        <nav ref={navRef}>
          <span
            className="nav-marker"
            aria-hidden="true"
            style={{ transform: `translateY(${navMarker.top}px)`, height: `${navMarker.height}px` }}
          />
          {navItems.map((item) => (
            <button
              key={item.id}
              ref={(node) => {
                if (node) navButtons.current.set(item.id, node);
                else navButtons.current.delete(item.id);
              }}
              className={`nav-item ${pageId === item.id ? "active" : ""}`}
              onClick={() => setPageId(item.id)}
              title={t(item.label)}
              aria-label={t(item.label)}
              aria-current={pageId === item.id ? "page" : undefined}
            >
              <Icon path={item.icon} />
              <span>{t(item.label)}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="sidebar-user" title={user.email}>
            <span className="sidebar-avatar" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="8.2" r="3.6" />
                <path d="M5 19.6a7 7 0 0 1 14 0" />
              </svg>
              <span className="sidebar-avatar-dot" />
            </span>
            <span className="sidebar-user-info">
              <span className="sidebar-user-email">{user.email}</span>
              <span className={`sidebar-user-role${user.role === "admin" ? " is-admin" : ""}`}>
                {user.role === "admin" ? t("Administrateur") : t("Utilisateur")}
              </span>
            </span>
          </div>
          <button
            className="nav-item ghost"
            onClick={onLogout}
            title={t("Déconnexion")}
            aria-label={t("Déconnexion")}
          >
            <Icon path="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
            <span>{t("Déconnexion")}</span>
          </button>
        </div>
      </aside>

      <div className="main">
        <header className="topbar" ref={topbarRef}>
          <span className="read-progress" ref={progressRef} aria-hidden="true" />
          <div className="topbar-crumb">
            <span className="muted small">FinOVA</span>
            <span className="sep">/</span>
            <strong key={pageId}>
              {pageId === MYDATA
                ? t("Mes données")
                : pageId === AUDIT
                ? t("Audit et confiance")
                : pageId === ADMIN
                ? t("Utilisateurs")
                : PAGE_COPY[page?.id ?? ""]?.title ?? (plainText(page?.title) || t("Vue d'ensemble"))}
            </strong>
          </div>
          <div className="topbar-tools">
            <DisplayControls />
            <label className="select">
              <span className="sr-only">{t("Pays")}</span>
              <select
                value={iso3}
                onChange={(event) => setIso3(event.target.value)}
                title={t("Pays")}
              >
                {COUNTRIES.map((country) => (
                  <option key={country.iso3} value={country.iso3}>
                    {tr(country.name)}
                  </option>
                ))}
              </select>
            </label>
            <label className="select">
              <span className="sr-only">{t("Année")}</span>
              <select
                value={year}
                onChange={(event) => setYear(Number(event.target.value))}
                title={t("Année")}
              >
                {(years.length ? years : [2017, 2021, 2024]).map((item) => (
                  <option key={item} value={item}>
                    {surveyYears.includes(item) ? `${item} · ${t("enquête")}` : item}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </header>

        <main className="content">
          {pageId === MYDATA && <MyDataPage userData={userData} />}
          {pageId === AUDIT && <AuditPage />}
          {pageId === ADMIN && user.role === "admin" && (
            <AdminUsersPage currentUser={user} />
          )}
          {!LOCAL_PAGES.has(pageId) && loading && !spec && (
            <LoadingScreen
              country={countryName}
              year={year}
              elapsed={elapsed}
            />
          )}
          {!LOCAL_PAGES.has(pageId) && loading && spec && (
            <div className="loading-banner">
              {t(
                "Préparation des chiffres pour {country} {year}… ({elapsed} s). La vue précédente reste affichée pendant le calcul, puis elle sera remplacée.",
                { country: countryName, year, elapsed },
              )}
            </div>
          )}
          {!LOCAL_PAGES.has(pageId) && error && (
            <div className="error-card">
              <h3>{t("Tableau de bord indisponible")}</h3>
              <p>{t("Les données n'ont pas pu être chargées pour le moment.")}</p>
              <details className="tech-details">
                <summary>{t("Détail technique")}</summary>
                <p className="muted small">{error}</p>
                <p className="muted small">
                  {t("Vérifiez que le service tourne et que la base de données a bien été préparée.")}
                </p>
              </details>
              <button
                className="primary-btn"
                onClick={() => {
                  cache.current.delete(key);
                  setSpec(null);
                  setReload((value) => value + 1);
                }}
              >
                {t("Réessayer")}
              </button>
            </div>
          )}
          {!LOCAL_PAGES.has(pageId) && !loading && !error && spec && page && (
            <>
              {(spec.survey_years?.length ?? 0) > 0 && (
                <p className="survey-hint">
                  {t(
                    "Années d'enquête Findex pour {country} : {years}. Les autres années reprennent la dernière enquête antérieure ; les indicateurs bancaires restent ceux de l'année.",
                    {
                      country: tr(spec.country.name),
                      years: spec.survey_years!.join(", "),
                    },
                  )}
                </p>
              )}
              {wave && WAVE_PAGES.has(page.id) && (
                <div className="generated-banner wave-banner" role="status">
                  {t("Pas d'enquête Findex en {year} : les chiffres viennent de l'enquête {used}.", {
                    year: wave.year_requested,
                    used: wave.year_used ?? "",
                  })}
                </div>
              )}
              {source === "generated" && (
                <div className="generated-banner">
                  {t(
                    "Cette vue a été préparée à la demande pour ce pays et cette année, à partir de la même base de données. Elle peut différer de la vue publiée par défaut.",
                  )}
                </div>
              )}
              <WaveNavContext.Provider value={setYear}>
                <PageView key={`${page.id}-${iso3}-${year}`} page={page} spec={spec} onAsk={submitAsk} />
              </WaveNavContext.Provider>
              {(pageId === "overview" || pageId === "pipeline") && (
                <NoticeList notices={globalNotices} />
              )}
              <footer className="page-foot">
                <span>{tr(spec.country.name)} · {spec.year}</span>
                <span>{t("Mise à jour du {date}", { date: prettyDate(spec.generated_at) })}</span>
                <span>
                  {t("Aucune valeur inventée · {count} données sourcées", {
                    count: spec.facts.length,
                  })}
                </span>
              </footer>
            </>
          )}
        </main>
      </div>

      <AskDock
        open={askOpen}
        onClose={() => setAskOpen(false)}
        messages={messages}
        busy={busy}
        onAsk={submitAsk}
        suggestions={suggestions}
        rules={rules}
        userData={userData}
      />
      <ConsentDialog control={userData} />
      {!askOpen && (
        <button
          className="ask-fab"
          onClick={() => setAskOpen(true)}
          aria-label={`${t("Ouvrir Ask Finova")} · Ctrl K`}
          title={`${t("Ouvrir Ask Finova")} · Ctrl K`}
        >
          <span className="ask-fab-dot" aria-hidden="true" />
          Ask Finova
          <kbd className="ask-fab-key" aria-hidden="true">Ctrl K</kbd>
        </button>
      )}
    </div>
  );
}

function LoadingScreen({
  country,
  year,
  elapsed,
}: {
  country: string;
  year: number;
  elapsed: number;
}) {
  return (
    <div className="loading-screen" role="status" aria-live="polite">
      <div className="loading-orbit" aria-hidden="true">
        <img className="loading-core" src="/brand/finova-icon.png" alt="" />
      </div>
      <h3>{t("Préparation des données…")}</h3>
      <p className="muted">
        {country} · {year} — {t("lecture de la base locale et vérification des sources.")}
      </p>
      <p className="small muted">
        {elapsed < 15
          ? t("La première ouverture de ce pays peut prendre 20 à 40 secondes.")
          : t(
              "Toujours en cours ({elapsed} s) : les séries annuelles sont recalculées depuis la base, sans estimation.",
              { elapsed },
            )}
      </p>
      <div className="loading-skeleton" aria-hidden="true">
        <div className="sk-grid">
          {[0, 1, 2, 3].map((item) => (
            <span key={item} className="sk-card" />
          ))}
        </div>
        <span className="sk-chart" />
      </div>
    </div>
  );
}

