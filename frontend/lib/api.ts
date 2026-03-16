import {
  AdminOverview,
  AdminUser,
  Contributor,
  FeedResponse,
  FederationPolicy,
  IngestionRun,
  IngestionSource,
  IntelItem,
  SimilarIntel,
  SourceReliabilityRow
} from "@/lib/types";

const API_BASE =
  typeof window === "undefined"
    ? process.env.API_BASE_URL_INTERNAL || "http://backend:8000"
    : process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const DEFAULT_KEY = process.env.NEXT_PUBLIC_DEFAULT_API_KEY || "orga_admin_key";
const BACKUP_KEYS = ["alice_admin_key", "ana_analyst_key", "carl_contrib_key"];

const TOKEN_KEY = "ps13_access_token";

function getBrowserToken(): string {
  if (typeof window === "undefined") return "";
  const ls = window.localStorage.getItem(TOKEN_KEY);
  if (ls) return ls;
  const match = document.cookie.match(/(?:^|; )ps13_token=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

export function setSessionToken(token: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
  document.cookie = `ps13_token=${encodeURIComponent(token)}; path=/; max-age=${60 * 60 * 24 * 14}`;
}

export function clearSessionToken() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
  document.cookie = "ps13_token=; path=/; max-age=0";
}

export class ApiFetchError extends Error {
  status: number;
  body: string;

  constructor(status: number, body: string, message?: string) {
    super(message || body || `Request failed ${status}`);
    this.status = status;
    this.body = body;
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const baseHeaders = new Headers(init?.headers || undefined);

  if (!(init?.body instanceof FormData)) {
    baseHeaders.set("Content-Type", "application/json");
  }

  const token = getBrowserToken();
  let res: Response;
  const candidates = Array.from(new Set([DEFAULT_KEY, ...BACKUP_KEYS].filter(Boolean)));

  const requestWithKeys = async (): Promise<Response> => {
    let chosen: Response | null = null;
    for (const key of candidates) {
      const headers = new Headers(baseHeaders);
      headers.set("X-API-Key", key);
      const attempt = await fetch(`${API_BASE}${path}`, {
        ...init,
        cache: "no-store",
        headers
      });
      chosen = attempt;
      if (attempt.status !== 401 && attempt.status !== 403) break;
    }
    return chosen as Response;
  };

  if (token) {
    const headers = new Headers(baseHeaders);
    headers.set("Authorization", `Bearer ${token}`);
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      cache: "no-store",
      headers
    });
    if (res.status === 401 || res.status === 403) {
      clearSessionToken();
      res = await requestWithKeys();
    }
  } else {
    res = await requestWithKeys();
  }

  if (!res.ok) {
    const body = await res.text();
    throw new ApiFetchError(res.status, body, body || `Request failed ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function loginWithApiKey(apiKey: string) {
  return apiFetch<{
    access_token: string;
    token_type: string;
    expires_in: number;
    user: { user_id: number; org_id: number; role: string; name: string; auth_type: string };
  }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ api_key: apiKey })
  });
}

export async function whoAmI() {
  return apiFetch<{ user_id: number; org_id: number; role: string; name: string; auth_type: string }>("/api/auth/whoami");
}

export async function rotateApiKey(scope: "user" | "org" = "user") {
  return apiFetch<{ scope: string; subject_id: number; new_api_key: string; rotated_at: string }>(
    `/api/auth/rotate-key?scope=${scope}`,
    { method: "POST" }
  );
}

export async function getFeed(query = ""): Promise<FeedResponse> {
  return apiFetch<FeedResponse>(`/api/feed${query ? `?${query}` : ""}`);
}

export async function getIntel(id: string): Promise<IntelItem> {
  return apiFetch<IntelItem>(`/api/intel/${id}`);
}

export async function getIntelProof(id: string) {
  return apiFetch<{
    intel_id: number;
    entries: Array<{ ledger_id: number; prev_hash: string; hash: string; signature?: string; created_at: string }>;
  }>(`/api/intel/${id}/proof`);
}

export async function getIntelSimilar(id: string): Promise<SimilarIntel[]> {
  return apiFetch<SimilarIntel[]>(`/api/intel/${id}/similar`);
}

export async function getContributors(): Promise<Contributor[]> {
  return apiFetch<Contributor[]>("/api/contributors");
}

export async function runIntegrityVerify() {
  return apiFetch<{ status: string; first_broken_index: number | null; checked_entries: number }>(
    "/api/integrity/verify"
  );
}

export async function runIntegrityAnchor() {
  return apiFetch<{ created: boolean; anchor_id?: number; up_to_ledger_id?: number; head_hash?: string }>(
    "/api/integrity/anchor",
    { method: "POST" }
  );
}

export async function getIntegrityAnchors(limit = 10) {
  return apiFetch<Array<{ id: number; up_to_ledger_id: number; head_hash: string; anchor_hash: string; created_at: string }>>(
    `/api/integrity/anchors?limit=${limit}`
  );
}

export async function runFederation() {
  return apiFetch<{ shared_count: number; details: Array<Record<string, unknown>> }>("/api/federation/run", {
    method: "POST"
  });
}

export async function contributorAction(payload: {
  contributor_id: number;
  intel_id: number;
  action: "approve" | "upvote" | "flag";
}) {
  return apiFetch<{ contributor_id: number; new_reputation: number; delta: number }>(
    "/api/contributors/action",
    {
      method: "POST",
      body: JSON.stringify(payload)
    }
  );
}

export async function getAdminOverview(): Promise<AdminOverview> {
  return apiFetch<AdminOverview>("/api/admin/overview");
}

export async function getAdminUsers(): Promise<AdminUser[]> {
  return apiFetch<AdminUser[]>("/api/admin/users");
}

export async function getAdminPolicies(): Promise<FederationPolicy[]> {
  return apiFetch<FederationPolicy[]>("/api/admin/federation-policies");
}

export async function updateAdminPolicy(
  id: number,
  payload: Partial<Pick<FederationPolicy, "min_credibility" | "min_reputation" | "enabled">>
) {
  return apiFetch<FederationPolicy>(`/api/admin/federation-policies/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export async function getAdminIngestionSources(): Promise<IngestionSource[]> {
  return apiFetch<IngestionSource[]>("/api/admin/ingestion-sources");
}

export async function updateAdminIngestionSource(
  id: number,
  payload: Partial<Pick<IngestionSource, "enabled" | "interval_minutes" | "max_rows" | "config">>
) {
  return apiFetch<IngestionSource>(`/api/admin/ingestion-sources/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export async function runAdminSource(id: number) {
  return apiFetch<{ queued: boolean; task_id: string; source_id: number; name: string }>(
    `/api/admin/ingestion-sources/${id}/run`,
    { method: "POST" }
  );
}

export async function runDueAdminSources() {
  return apiFetch<{ queued: boolean; task_id: string; due_count: number; source_ids: number[] }>(
    "/api/admin/ingestion/run-due",
    { method: "POST" }
  );
}

export async function getAdminIngestionRuns(limit = 20): Promise<IngestionRun[]> {
  return apiFetch<IngestionRun[]>(`/api/admin/ingestion-runs?limit=${limit}`);
}

export async function getSourceReliability(): Promise<SourceReliabilityRow[]> {
  return apiFetch<SourceReliabilityRow[]>("/api/source-reliability");
}

export async function updateSourceReliability(id: number, payload: Partial<SourceReliabilityRow>) {
  return apiFetch<SourceReliabilityRow>(`/api/source-reliability/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}
