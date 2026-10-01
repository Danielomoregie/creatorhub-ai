import type { Alert, DigestPreview, Idea, IdeaStatus, Performance, Profile, Summary, Trend } from "./types";

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

async function call<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const { json, ...rest } = init ?? {};
  const res = await fetch(`/api${path}`, {
    ...rest,
    headers: json !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(data?.error ?? `Request failed (${res.status})`, res.status);
  return data as T;
}

export const api = {
  summary: () => call<Summary>("/summary"),
  trends: (params: { niche?: string; hours?: number } = {}) => {
    const q = new URLSearchParams();
    if (params.niche) q.set("niche", params.niche);
    if (params.hours) q.set("hours", String(params.hours));
    return call<Trend[]>(`/trends?${q}`);
  },
  alerts: (all = false) => call<Alert[]>(`/alerts${all ? "?all=1" : ""}`),
  markAlertsRead: (ids?: number[]) => call<{ marked: number }>("/alerts/read", { method: "POST", json: ids ? { ids } : {} }),
  ideas: () => call<Idea[]>("/ideas"),
  generateIdeas: (b: { count: number; niche?: string; platform?: string; direction?: string }) =>
    call<Idea[]>("/ideas/generate", { method: "POST", json: b }),
  setIdeaStatus: (id: number, status: IdeaStatus) => call(`/ideas/${id}`, { method: "PATCH", json: { status } }),
  toNotion: (id: number) => call<{ page_id: string }>(`/ideas/${id}/notion`, { method: "POST" }),
  profile: () => call<Profile>("/profile"),
  addNiche: (name: string, keywords: string[]) => call("/niches", { method: "POST", json: { name, keywords } }),
  performance: () => call<Performance | null>("/performance"),
  refreshPerformance: () => call<Performance>("/performance/refresh", { method: "POST" }),
  digest: () => call<DigestPreview>("/digest"),
  sendDigest: () => call("/digest/send", { method: "POST" }),
  scan: () => call<{ fetched: number; new: number; judged: number; alerts: Alert[] }>("/scan", { method: "POST" }),
};
