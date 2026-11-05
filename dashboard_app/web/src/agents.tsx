import { useCallback, useEffect, useRef, useState } from "react";
import type { AgentRow, AgentsTimeline as Timeline, SourceJob } from "./types";
import { ApiError, fetchAgents, fetchSourceJob, startDemo } from "./api";
import { fmtNumber, prettyDate } from "./format";

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
          <strong>{agent.label}</strong>
          <span className={`agent-mode ${agent.llm ? "mode-llm" : "mode-det"}`}>
            {agent.llm ? "LLM optionnel" : "déterministe"}
          </span>
          <span className="agent-status">{live ? LIVE_LABEL[live] : statusLabel(agent)}</span>
        </div>
        <p className="muted small">{agent.role}</p>
        <div className="agent-facts">
          {agent.duration_s !== null && <span>{fmtNumber(agent.duration_s, 2)} s</span>}
          {agent.key_output && <span>{agent.key_output}</span>}
          {agent.llm && agent.status === "success" && <span>appels LLM : {agent.llm_measured}</span>}
          {agent.note && <span className="muted">{agent.note}</span>}
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
        else setError(err instanceof Error ? err.message : "Démonstration impossible");
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
          <h3 id="agents-title">Agents</h3>
          <p className="muted small">
            {timeline
              ? `Run ${timeline.route1_run_id} · snapshot ${timeline.snapshot_id} · ${
                  timeline.route2_run_id ? `Route 2 ${timeline.route2_run_id}` : "Route 2 non exécutée"}`
              : "Chargement du dernier run…"}
          </p>
        </div>
        <button type="button" className="primary-btn" onClick={start} disabled={running}>
          {running ? "Démonstration en cours…" : "Relancer la démonstration"}
        </button>
      </div>
      {job && (
        <div className={`agents-banner ${job.no_change ? "banner-info" : running ? "banner-run" : `banner-${job.status}`}`}
             role="status">
          {running
            ? `Recalcul hors ligne en cours (sources officielles reprises du snapshot publié) — étape : ${job.step ?? "démarrage"}`
            : job.no_change
              ? "Aucune donnée nouvelle : le contenu est identique à la version publiée. Les agents suivants sont ignorés."
              : job.message ?? job.status}
          {!running && job.finished_at && (
            <span className="muted small"> · terminé {prettyDate(job.finished_at)} ({fmtNumber(job.seconds, 1)} s)</span>
          )}
        </div>
      )}
      {error && <p className="muted small">{error}</p>}
      {timeline && (
        <div className="agents-routes">
          <div>
            <span className="eyebrow">Route 1 — fiabiliser les données</span>
            <ol className="agent-list">
              {route1.map((agent, i) => (
                <AgentItem key={agent.id} agent={agent} index={i + 1} live={liveState(agent, job)} />
              ))}
            </ol>
          </div>
          <div>
            <span className="eyebrow">Route 2 — analyser et publier</span>
            <ol className="agent-list">
              {route2.map((agent, i) => (
                <AgentItem key={agent.id} agent={agent} index={route1.length + i + 1} live={liveState(agent, job)} />
              ))}
            </ol>
            <span className="eyebrow">Interface</span>
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
