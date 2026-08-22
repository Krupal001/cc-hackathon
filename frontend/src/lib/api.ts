const API_URL = "/api/backend";

export interface Finding {
  file: string;
  line: number;
  severity: string;
  confidence: number;
  title: string;
  description: string;
  suggestion: string;
  category: string;
  verification: string | null;
}

export interface Review {
  id: number;
  installation_id: number;
  repo_full_name: string;
  pr_number: number;
  commit_sha: string;
  status: string;
  findings: Finding[];
  summary: string;
  diagram: string;
  merge_score: number | null;
  merge_score_reason: string;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
  enabled_agent_count: number;
  review_mode: string;
  error_message: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ReviewListResponse {
  reviews: Review[];
  total: number;
  limit: number;
  offset: number;
}

export interface Installation {
  installation_id: number;
  repo_full_name: string;
  model_id: string | null;
  config: Record<string, unknown>;
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_URL}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
      cache: "no-store",
    });
  } catch (e) {
    throw new Error(`Network error (proxy → ${url}): ${e}`);
  }
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText} (proxy → ${url})`);
  }
  return res.json();
}

export const api = {
  health: () => apiFetch<{ status: string; version: string }>("/health"),

  listReviews: (params?: { repo?: string; status?: string; limit?: number; offset?: number }) => {
    const search = new URLSearchParams();
    if (params?.repo) search.set("repo", params.repo);
    if (params?.status) search.set("status", params.status);
    if (params?.limit) search.set("limit", String(params.limit));
    if (params?.offset) search.set("offset", String(params.offset));
    const qs = search.toString();
    return apiFetch<ReviewListResponse>(`/api/reviews${qs ? `?${qs}` : ""}`);
  },

  getReview: (id: number) => apiFetch<Review>(`/api/reviews/${id}`),

  getReviewByKey: (repo: string, pr: number, sha: string) =>
    apiFetch<Review>(`/api/reviews/by-key/${encodeURIComponent(repo)}/${pr}/${sha}`),

  listInstallations: () =>
    apiFetch<{ installations: Installation[] }>("/api/installations"),

  listRepos: (installationId: number) =>
    apiFetch<{ repos: Installation[] }>(`/api/installations/${installationId}/repos`),

  getSettings: (installationId: number) =>
    apiFetch<{ installation_id: number; settings: Record<string, unknown> | null }>(
      `/api/installations/${installationId}/settings`
    ),

  updateSettings: (installationId: number, body: Record<string, unknown>) =>
    apiFetch<{ status: string }>(`/api/installations/${installationId}/settings`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  getInsights: (installationId: number) =>
    apiFetch<{ insights: Record<string, unknown>[] }>(
      `/api/analytics/${installationId}/insights`
    ),

  getDispositions: (installationId: number, repo?: string) => {
    const search = new URLSearchParams();
    if (repo) search.set("repo", repo);
    const qs = search.toString();
    return apiFetch<{ dispositions: Record<string, unknown>[] }>(
      `/api/analytics/${installationId}/dispositions${qs ? `?${qs}` : ""}`
    );
  },
};
