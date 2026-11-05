import type {
  AgentsTimeline, AskResult, ComparableKpi, ComparisonsResult, DetectResult, DryRunResult, RecommendationsResult, RunSummary, SourceData, SourceJob,
  SourceMappingInput,
  SourcesList, Spec,
} from "./types";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
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
      /* keep the HTTP message */
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export async function fetchSpec(
  iso3: string,
  year: number,
  signal?: AbortSignal,
): Promise<{ spec: Spec; source: string }> {
  const url = `/api/spec?iso3=${encodeURIComponent(iso3)}&year=${year}`;
  const response = await fetch(url, { signal });
  if (!response.ok) {
    let detail = `Erreur HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* keep the HTTP message */
    }
    throw new ApiError(response.status, detail);
  }
  const spec = (await response.json()) as Spec;
  const source = response.headers.get("X-Finova-Source") || "file";
  return { spec, source };
}

export interface ChatTurn {
  role: "user" | "assistant";
  text: string;
}

export function askFinova(
  question: string,
  iso3: string,
  year: number,
  context: { page?: string; session_id?: string; history?: ChatTurn[] } = {},
): Promise<AskResult> {
  return request<AskResult>("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, iso3, year, ...context }),
  });
}

// ------------------------------------------------------------ Mes données
export async function detectSource(file: File): Promise<DetectResult> {
  const form = new FormData();
  form.append("file", file, file.name);
  return request<DetectResult>("/api/sources/detect", { method: "POST", body: form });
}

function sourceBody(upload_id: string, name: string, mapping: SourceMappingInput): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ upload_id, name, mapping }),
  };
}

export function dryRunSource(uploadId: string, name: string, mapping: SourceMappingInput): Promise<DryRunResult> {
  return request<DryRunResult>("/api/sources/dry-run", sourceBody(uploadId, name, mapping));
}

export function confirmSource(
  uploadId: string,
  name: string,
  mapping: SourceMappingInput,
): Promise<{ job_id: string; name: string; replaced: boolean }> {
  return request("/api/sources/confirm", sourceBody(uploadId, name, mapping));
}

export function fetchSourceJob(jobId: string): Promise<SourceJob> {
  return request<SourceJob>(`/api/sources/jobs/${encodeURIComponent(jobId)}`);
}

export function fetchSources(): Promise<SourcesList> {
  return request<SourcesList>("/api/sources");
}

export function deleteSource(name: string): Promise<{ job_id: string; name: string }> {
  return request(`/api/sources/${encodeURIComponent(name)}`, { method: "DELETE" });
}

export function fetchSourceData(name: string): Promise<SourceData> {
  return request<SourceData>(`/api/sources/${encodeURIComponent(name)}/data`);
}

export function fetchRuns(): Promise<{ runs: RunSummary[]; count: number }> {
  return request<{ runs: RunSummary[]; count: number }>("/api/runs");
}

export function fetchComparableKpis(): Promise<{ kpis: ComparableKpi[] }> {
  return request<{ kpis: ComparableKpi[] }>("/api/sources/comparable-kpis");
}

export function fetchComparisons(iso3: string, year: number, signal?: AbortSignal): Promise<ComparisonsResult> {
  return request<ComparisonsResult>(
    `/api/sources/comparisons?iso3=${encodeURIComponent(iso3)}&year=${year}`, { signal });
}

export function fetchRecommendations(iso3: string, year: number, signal?: AbortSignal): Promise<RecommendationsResult> {
  return request<RecommendationsResult>(
    `/api/recommendations?iso3=${encodeURIComponent(iso3)}&year=${year}`, { signal });
}

export function fetchAgents(runId?: string): Promise<AgentsTimeline> {
  const query = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
  return request<AgentsTimeline>(`/api/pipeline/agents${query}`);
}

export function startDemo(): Promise<{ job_id: string; status: string }> {
  return request("/api/pipeline/demo", { method: "POST" });
}
