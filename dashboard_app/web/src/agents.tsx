import { useCallback, useEffect, useRef, useState } from "react";
import type { AgentRow, AgentsTimeline as Timeline, SourceJob } from "./types";
import { ApiError, fetchAgents, fetchSourceJob, startDemo } from "./api";
import { fmtNumber, prettyDate } from "./format";
import { t } from "./i18n";
import { plainText } from "./copy";
import { getLang } from "./preferences";

const AGENT_LABEL_AR: Record<string, string> = {
  collector: "الجمع",
  snapshot: "اللقطة",
  profiler: "التحليل",
  quality: "الجودة",
  etl: "التحويل (ETL)",
  semantic_kpi: "الدلالة والمؤشرات",
  auditor: "المدقّق (BI Auditor / XAI)",
  analyst: "المحلّل (FinOVA)",
  dashboard_spec: "مواصفات لوحة المعلومات",
  ask: "اسأل Finova",
};

const ACTIVE = ["queued", "running"];
// etapes du recalcul (jobs.STEPS) ; « route2 » couvre l'Analyst et le Dashboard spec
const STEP_OF: Record<string, string> = {
  collector: "collector", snapshot: "snapshot", profiler: "profiler", quality: "quality", etl: "etl",
  semantic_kpi: "semantic_kpi", auditor: "auditor", analyst: "route2", dashboard_spec: "route2",
};

type Live = "done" | "running" | "pending" | "skipped" | "error";

function liveState(agent: AgentRow, job: SourceJob | null): Live | null {
  if (!job) return null;
  const step = STEP_OF[agent.id];
  if (!step) return null;
  if ((job.skipped ?? []).includes(step)) return "skipped";
  if (job.steps_done.includes(step)) return "done";
  if (job.step === step) return ACTIVE.includes(job.status) ? "running" : "error";
  return ACTIVE.includes(job.status) ? "pending" : "skipped";
}

const LIVE_LABEL: Record<Live, string> = {
  done: "terminé", running: "en cours…", pending: "en attente", skipped: "ignoré", error: "erreur",
};

function statusLabel(agent: AgentRow): string {
  if (agent.status === "success") return "réussi";
  if (agent.status === "skipped") return "ignoré";
  if (agent.status === "on_demand") return "à la demande";
  if (!agent.status) return "non exécuté";
  return agent.status;
}

function AgentItem({ agent, index, live }: { agent: AgentRow; index: number; live: Live | null }) {
  const state = live ?? (agent.status === "success" ? "done" : agent.status === "skipped" ? "skipped" : null);
  return (
    <li className={`agent-item ${state ? `agent-${state}` : ""}`}>
      <span className="agent-index" aria-hidden="true">{index}</span>
      <div className="agent-body">
        <div className="agent-head">
          <strong>{getLang() === "ar" ? (AGENT_LABEL_AR[agent.id] ?? agent.label) : agent.label}</strong>
          <span className={`agent-mode ${agent.llm ? "mode-llm" : "mode-det"}`}>
            {agent.llm ? t("LLM optionnel") : t("déterministe")}
          </span>
          <span className="agent-status">{live ? t(LIVE_LABEL[live]) : t(statusLabel(agent))}</span>
        </div>
        <p className="muted small">{plainText(agent.role)}</p>
        <div className="agent-facts">
          {agent.duration_s !== null && <span>{fmtNumber(agent.duration_s, 2)} s</span>}
          {agent.key_output && <span>{plainText(agent.key_output)}</span>}
          {agent.llm && agent.status === "success" && (
            <span>{t("appels LLM : {count}", { count: plainText(agent.llm_measured) })}</span>
          )}
          {agent.note && <span className="muted">{plainText(agent.note)}</span>}
        </div>
      </div>
    </li>
  );
}

export function AgentsTimeline() {
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [job, setJob] = useState<SourceJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | null>(null);

  const load = useCallback((runId?: string | null) => {
    fetchAgents(runId ?? undefined)
      .then((data) => {
        setTimeline(data);
        setError(null);
        if (data.active_job && !runId) setJob(data.active_job);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Frise indisponible"));
  }, []);

  useEffect(() => load(), [load]);

  // suivi en direct du recalcul (statut relu toutes les 1,5 s)
  useEffect(() => {
    if (!job || !ACTIVE.includes(job.status)) return undefined;
    timer.current = window.setTimeout(() => {
      fetchSourceJob(job.job_id)
        .then((next) => {
          setJob(next);
          if (!ACTIVE.includes(next.status)) load(next.run_id);
        })
        .catch((err: unknown) => setError(err instanceof Error ? err.message : "Suivi interrompu"));
    }, 1500);
    return () => {
      if (timer.current !== null) window.clearTimeout(timer.current);
    };
  }, [job, load]);

  const start = () => {
    setError(null);
    startDemo()
      .then(({ job_id }) => fetchSourceJob(job_id))
      .then(setJob)
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 409) setError(err.detail);
        else setError(err instanceof Error ? err.message : "Recalcul impossible");
      });
  };

  const running = job !== null && ACTIVE.includes(job.status);
  const route1 = timeline?.agents.filter((a) => a.route === "Route 1") ?? [];
  const route2 = timeline?.agents.filter((a) => a.route === "Route 2") ?? [];
  const ask = timeline?.agents.filter((a) => a.route === "Interface") ?? [];

  return (
    <section className="panel agents-timeline" aria-labelledby="agents-title">
      <div className="panel-head">
        <div>
          <h3 id="agents-title">{t("Agents")}</h3>
          <p className="muted small">
            {timeline
              ? `${t("Run {id}", { id: timeline.route1_run_id })} · ${t("snapshot {id}", { id: timeline.snapshot_id })} · ${
                  timeline.route2_run_id
                    ? t("Route 2 {id}", { id: timeline.route2_run_id })
                    : t("Route 2 non exécutée")}`
              : t("Chargement du dernier run…")}
          </p>
        </div>
        <button type="button" className="primary-btn" onClick={start} disabled={running}>
          {running ? t("Recalcul en cours…") : t("Recalculer les données")}
        </button>
      </div>
      {job && (
        <div className={`agents-banner ${job.no_change ? "banner-info" : running ? "banner-run" : `banner-${job.status}`}`}
             role="status">
          {running
            ? t("Recalcul hors ligne en cours (sources officielles reprises du snapshot publié) — étape : {step}", {
                step: job.step ?? t("démarrage"),
              })
            : job.no_change
              ? t("Aucune donnée nouvelle : le contenu est identique à la version publiée. Les agents suivants sont ignorés.")
              : plainText(job.message) || t(job.status)}
          {!running && job.finished_at && (
            <span className="muted small">
              {" "}· {t("terminé {date} ({seconds} s)", {
                date: prettyDate(job.finished_at),
                seconds: fmtNumber(job.seconds, 1),
              })}
            </span>
          )}
        </div>
      )}
      {error && <p className="muted small">{t(error)}</p>}
      {timeline && (
        <div className="agents-routes">
          <div>
            <span className="eyebrow">{t("Route 1 — fiabiliser les données")}</span>
            <ol className="agent-list">
              {route1.map((agent, i) => (
                <AgentItem key={agent.id} agent={agent} index={i + 1} live={liveState(agent, job)} />
              ))}
            </ol>
          </div>
          <div>
            <span className="eyebrow">{t("Route 2 — analyser et publier")}</span>
            <ol className="agent-list">
              {route2.map((agent, i) => (
                <AgentItem key={agent.id} agent={agent} index={route1.length + i + 1} live={liveState(agent, job)} />
              ))}
            </ol>
            <span className="eyebrow">{t("Interface")}</span>
            <ol className="agent-list">
              {ask.map((agent) => (
                <AgentItem key={agent.id} agent={agent} index={route1.length + route2.length + 1} live={null} />
              ))}
            </ol>
          </div>
        </div>
      )}
    </section>
  );
}
