const API_BASE_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL
  ?? process.env.NEXT_PUBLIC_API_BASE_URL
  ?? "http://127.0.0.1:8000";

export type JsonRecord = Record<string, unknown>;

async function get(path: string): Promise<JsonRecord> {
  const response = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: unknown } | null;
    throw new Error(typeof body?.detail === "string" ? body.detail : `Request failed (${response.status})`);
  }
  return response.json() as Promise<JsonRecord>;
}

export const getBackendHealth = () => get("/health");
export const getActiveWorkspace = () => get("/workspaces/active");
export const getProjectIndexStatus = () => get("/project-index/status");
export const getKnowledgeStatus = () => get("/knowledge/sources");
export const getUnityKnowledgeStatus = () => get("/knowledge/unity/status");
