import type { AskResult, RunSummary, Spec } from "./types";

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

export function askFinova(question: string, iso3: string, year: number): Promise<AskResult> {
  return request<AskResult>("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, iso3, year }),
  });
}

export function fetchRuns(): Promise<{ runs: RunSummary[]; count: number }> {
  return request<{ runs: RunSummary[]; count: number }>("/api/runs");
}
