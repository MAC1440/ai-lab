const API_BASE_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL
  ?? process.env.NEXT_PUBLIC_API_BASE_URL
  ?? "http://127.0.0.1:8000";

export type JsonRecord = Record<string, unknown>;

export type ProjectIndexQueryRequest = {
  query: string;
  limit?: number;
  project_root?: string | null;
  refresh?: boolean;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null) as
      | { detail?: unknown }
      | null;
    throw new Error(
      typeof payload?.detail === "string"
        ? payload.detail
        : `Request failed (${response.status})`,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export function getActiveWorkspace(): Promise<JsonRecord> {
  return request("/workspaces/active");
}

export function getKnowledgeSourcesStatus(): Promise<JsonRecord> {
  return request("/knowledge/sources");
}

export function removeKnowledgeSource(
  sourceId: string,
): Promise<JsonRecord> {
  return request(`/knowledge/sources/${encodeURIComponent(sourceId)}`, {
    method: "DELETE",
  });
}

export function getUnityKnowledgeStatus(): Promise<JsonRecord> {
  return request("/knowledge/unity/status");
}

export function getProjectIndexStatus(): Promise<JsonRecord> {
  return request("/project-index/status");
}

export function refreshProjectIndex(
  rebuild = false,
): Promise<JsonRecord> {
  return request("/project-index/refresh", {
    method: "POST",
    body: JSON.stringify({ rebuild }),
  });
}

export function queryProjectIndex(
  body: ProjectIndexQueryRequest,
): Promise<JsonRecord> {
  return request("/project-index/query", {
    method: "POST",
    body: JSON.stringify({
      query: body.query,
      limit: body.limit ?? 8,
      project_root: body.project_root ?? null,
      refresh: body.refresh ?? true,
    }),
  });
}
