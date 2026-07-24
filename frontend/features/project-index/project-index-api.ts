const API_BASE_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

export type ProjectIndexStatus = {
  status: "not_indexed" | "ready" | "attention";
  workspace: string;
  indexed_at: string | null;
  duration_ms: number | null;
  file_count: number;
  symbol_count: number;
  reference_count: number;
  scan_truncated: boolean;
  last_error: string | null;
  schema_version: number;
  refresh?: {
    rebuild: boolean;
    changed_files: number;
    unchanged_files: number;
    removed_files: number;
    unreadable_files: number;
  };
};

export type ProjectIndexResult = {
  path: string;
  language: string;
  score: number;
  reasons: string[];
  matching_symbols: string[];
};

export type ProjectIndexQuery = {
  query: string;
  tokens: string[];
  workspace: string;
  project_root: string;
  results: ProjectIndexResult[];
  result_count: number;
  index: ProjectIndexStatus;
};

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as
      | { detail?: unknown }
      | null;
    throw new Error(
      typeof body?.detail === "string"
        ? body.detail
        : `Project index request failed with status ${response.status}`,
    );
  }
  return response.json() as Promise<T>;
}

export async function getProjectIndexStatus(): Promise<ProjectIndexStatus> {
  return parseJson<ProjectIndexStatus>(
    await fetch(`${API_BASE_URL}/project-index/status`, {
      cache: "no-store",
    }),
  );
}

export async function refreshProjectIndex(
  rebuild = false,
): Promise<ProjectIndexStatus> {
  return parseJson<ProjectIndexStatus>(
    await fetch(`${API_BASE_URL}/project-index/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rebuild }),
    }),
  );
}

export async function queryProjectIndex(
  query: string,
): Promise<ProjectIndexQuery> {
  return parseJson<ProjectIndexQuery>(
    await fetch(`${API_BASE_URL}/project-index/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, limit: 12, refresh: true }),
    }),
  );
}
