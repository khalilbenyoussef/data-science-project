import { useEffect, useRef, useState } from "react";
import type { AskResult, Notice, Spec } from "./types";
import { ApiError, askFinova, fetchSpec } from "./api";
import { PageView } from "./pages";
import { AskDock, ChatMessage, NoticeList } from "./ui";
import { prettyDate } from "./format";
import { PAGE_COPY, PUBLICATION_LABELS, plainText } from "./copy";

const NAV = [
  { id: "overview", label: "Vue d'ensemble", icon: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z" },
  { id: "inclusion", label: "Inclusion et inégalités", icon: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21c0-3.3 3.6-6 8-6s8 2.7 8 6" },
  { id: "access", label: "Accès et crédit", icon: "M3 21h18M5 21V7l7-4 7 4v14M9 21v-5h6v5" },
  { id: "exclusion", label: "Pourquoi l'exclusion ?", icon: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM9.5 9a2.5 2.5 0 1 1 3.6 2.2c-.8.5-1.1 1-1.1 1.8M12 17h.01" },
  { id: "poverty", label: "Pauvreté et SMIG", icon: "M4 19V5m0 14h16M8 15l3-4 3 2 5-7" },
  { id: "pipeline", label: "Sources et qualité", icon: "M4 6h16M4 12h16M4 18h16M8 4v4M16 10v4M10 16v4" },
];

// conversation Ask Finova gardee pour la session du navigateur (sessionStorage)
const CHAT_KEY = "finova.chat";
const SESSION_KEY = "finova.session";

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

export function App() {
  const [screen, setScreen] = useState<"login" | "app">(() =>
    new URLSearchParams(window.location.search).get("demo") === "1" ? "app" : "login",
  );
  const [pageId, setPageId] = useState("overview");
  const [iso3, setIso3] = useState("TUN");
  const [year, setYear] = useState(2024);
  const [years, setYears] = useState<number[]>([]);
  const [spec, setSpec] = useState<Spec | null>(null);
  const [source, setSource] = useState("file");
  const [loading, setLoading] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [askOpen, setAskOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>(() => readStored(CHAT_KEY, []));
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const [reload, setReload] = useState(0);
  const cache = useRef(new Map<string, { spec: Spec; source: string }>());

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
    if (screen !== "app") return;
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
        if (!result.spec.pages.some((page) => page.id === pageId)) setPageId("overview");
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        const detail = err instanceof ApiError ? err.detail : String(err);
        setError(detail || "Impossible de charger le contrat Finova.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
    // pageId intentionally excluded: switching pages must not refetch
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [screen, iso3, year, reload]);

  const page = spec?.pages.find((item) => item.id === pageId) ?? spec?.pages[0];
  const askBlock = spec?.pages
    .find((item) => item.id === "exclusion")
    ?.blocks.find((block) => block.kind === "ask");
  const suggestions = (askBlock?.payload as { suggestions?: string[] } | undefined)?.suggestions ?? [
    "Combien d'adultes ont un compte ?",
    "Pourquoi l'écart femmes-hommes est-il élevé ?",
    "Les ATMs ont-ils augmenté depuis 2017 ?",
  ];
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
            text: `Réponse indisponible : ${detail}`,
            isError: true,
          },
        ]);
      })
      .finally(() => setBusy(false));
  };

  const onSearch = (event: React.FormEvent) => {
    event.preventDefault();
    if (!query.trim()) {
      setAskOpen(true);
      return;
    }
    submitAsk(query);
    setQuery("");
  };

  const globalNotices: Notice[] = spec?.notices ?? [];
  const countryName =
    COUNTRIES.find((item) => item.iso3 === iso3)?.name ?? iso3;

  if (screen === "login") {
    return <Login onEnter={() => setScreen("app")} />;
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <img className="brand-logo" src="/brand/finova-logo.png" alt="FinOVA" />
          <img className="brand-mark" src="/brand/finova-icon.png" alt="" aria-hidden="true" />
          <div>
            <strong>
              Fin<em>OVA</em>
            </strong>
            <span>Inclusion financière</span>
          </div>
        </div>
        <nav>
          {NAV.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${pageId === item.id ? "active" : ""}`}
              onClick={() => setPageId(item.id)}
            >
              <Icon path={item.icon} />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <span className="eyebrow">Version {spec?.schema_version ?? "2.0"}</span>
          <span
            className={`status ${spec?.publication_status === "not_evaluated" ? "status-warning" : "status-available"}`}
            title={`Publication : ${PUBLICATION_LABELS[spec?.publication_status ?? "not_evaluated"] ?? PUBLICATION_LABELS.not_evaluated}`}
          >
            Démonstration
          </span>
          <button className="nav-item ghost" onClick={() => setScreen("login")}>
            <Icon path="M19 12H5m7-7-7 7 7 7" />
            <span>Retour à l'accueil</span>
          </button>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="topbar-crumb">
            <span className="muted small">FinOVA</span>
            <span className="sep">/</span>
            <strong>
              {PAGE_COPY[page?.id ?? ""]?.title ?? (plainText(page?.title) || "Vue d'ensemble")}
            </strong>
          </div>
          <div className="topbar-tools">
            <label className="select">
              <span className="sr-only">Pays</span>
              <select
                value={iso3}
                onChange={(event) => setIso3(event.target.value)}
                title="Pays"
              >
                {COUNTRIES.map((country) => (
                  <option key={country.iso3} value={country.iso3}>
                    {country.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="select">
              <span className="sr-only">Année</span>
              <select
                value={year}
                onChange={(event) => setYear(Number(event.target.value))}
                title="Année"
              >
                {(years.length ? years : [2017, 2021, 2024]).map((item) => (
                  <option key={item} value={item}>
                    {surveyYears.includes(item) ? `${item} · enquête` : item}
                  </option>
                ))}
              </select>
            </label>
            <span className="real-badge">
              <i />
              Données réelles et sourcées
            </span>
            <form className="search" onSubmit={onSearch}>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Posez une question…"
                aria-label="Poser une question"
              />
              <button type="submit" aria-label="Poser la question">
                <Icon path="M21 21l-4.3-4.3M11 19a8 8 0 1 1 0-16 8 8 0 0 1 0 16z" />
              </button>
            </form>
          </div>
        </header>

        <main className="content">
          {loading && !spec && (
            <LoadingScreen
              country={countryName}
              year={year}
              elapsed={elapsed}
            />
          )}
          {loading && spec && (
            <div className="loading-banner">
              Préparation des chiffres pour {countryName} {year}… ({elapsed} s).
              La vue précédente reste affichée pendant le calcul, puis elle sera
              remplacée.
            </div>
          )}
          {error && (
            <div className="error-card">
              <h3>Tableau de bord indisponible</h3>
              <p>Les données n'ont pas pu être chargées pour le moment.</p>
              <details className="tech-details">
                <summary>Détail technique</summary>
                <p className="muted small">{error}</p>
                <p className="muted small">
                  Vérifiez que le service tourne et que la base de données a bien été
                  préparée.
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
                Réessayer
              </button>
            </div>
          )}
          {!loading && !error && spec && page && (
            <>
              {(spec.survey_years?.length ?? 0) > 0 && (
                <p className="survey-hint">
                  Années d'enquête Findex pour {spec.country.name} :{" "}
                  {spec.survey_years!.join(", ")}. Les autres années reprennent la dernière
                  enquête antérieure ; les indicateurs bancaires restent ceux de l'année.
                </p>
              )}
              {wave && WAVE_PAGES.has(page.id) && (
                <div className="generated-banner wave-banner" role="status">
                  Pas d'enquête Findex en {wave.year_requested} : les chiffres viennent de
                  l'enquête {wave.year_used}.
                </div>
              )}
              {source === "generated" && (
                <div className="generated-banner">
                  Cette vue a été préparée à la demande pour ce pays et cette année, à
                  partir de la même base de données. Elle peut différer de la vue publiée
                  par défaut.
                </div>
              )}
              <PageView page={page} spec={spec} onAsk={submitAsk} />
              {(pageId === "overview" || pageId === "pipeline") && (
                <NoticeList notices={globalNotices} />
              )}
              <footer className="page-foot">
                <span>{spec.country.name} · {spec.year}</span>
                <span>Mise à jour du {prettyDate(spec.generated_at)}</span>
                <span>Aucune valeur inventée · {spec.facts.length} données sourcées</span>
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
      />
      {!askOpen && (
        <button className="ask-fab" onClick={() => setAskOpen(true)} aria-label="Ouvrir Ask Finova">
          Ask Finova
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
      <span className="spinner" aria-hidden="true" />
      <h3>Préparation des données…</h3>
      <p className="muted">
        {country} · {year} — lecture de la base locale et vérification des sources.
      </p>
      <p className="small muted">
        {elapsed < 15
          ? "La première ouverture de ce pays peut prendre 20 à 40 secondes."
          : `Toujours en cours (${elapsed} s) : les séries annuelles sont recalculées depuis la base, sans estimation.`}
      </p>
    </div>
  );
}

const LOGIN_VIDEOS = [
  "/media/login/login-01.mp4",
  "/media/login/login-02.mp4",
  "/media/login/login-03.mp4",
  "/media/login/login-04.mp4",
];

function LoginBackdrop() {
  const [index, setIndex] = useState(0);
  // Videos non versionnees (*.mp4 ignore) : une video introuvable est sautee ; si
  // aucune ne se charge, seul le fond statique de .login / .login-media reste.
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
    <div className="login-media" aria-hidden="true">
      {playable && (
        <video
          key={LOGIN_VIDEOS[index]}
          src={LOGIN_VIDEOS[index]}
          autoPlay
          muted
          playsInline
          preload="auto"
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

function Login({ onEnter }: { onEnter: () => void }) {
  return (
    <div className="login">
      <LoginBackdrop />
      <div className="login-logo" role="img" aria-label="FinOVA">
        <img className="login-mark" src="/brand/finova-mark.png" alt="" aria-hidden="true" />
        <span className="login-word" aria-hidden="true" />
      </div>
      <section className="login-brand">
        <h1>Les chiffres d'abord.<br />Les sources toujours.</h1>
        <p>
          FinOVA rassemble des chiffres publics sur les services financiers — compte
          bancaire, épargne, crédit — les vérifie, puis vous les explique simplement.
          Pas besoin d'être spécialiste : chaque page dit ce que le chiffre signifie,
          d'où il vient et ce qu'il ne permet pas de conclure.
        </p>
      </section>
      <section className="login-card">
        <h2>Connexion</h2>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            onEnter();
          }}
        >
          <label>
            Identifiant
            <span className="login-field">
              <Icon path="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21c0-3.3 3.6-6 8-6s8 2.7 8 6" />
              <input defaultValue="demo@finova.tn" autoComplete="username" />
            </span>
          </label>
          <label>
            Mot de passe
            <span className="login-field">
              <Icon path="M7 11V8a5 5 0 0 1 10 0v3M5 11h14v10H5zM12 15v3" />
              <input type="password" defaultValue="finova" autoComplete="current-password" />
            </span>
          </label>
          <button className="primary-btn wide" type="submit">
            S'authentifier
          </button>
        </form>
      </section>
    </div>
  );
}
