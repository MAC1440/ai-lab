import type {
  CreateTerminalSessionResponse,
  LaunchClaudeResponse,
  ListTerminalSessionsResponse,
  TerminalDiagnostics,
  TerminalSession,
} from "./types";

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000"
).replace(/\/$/, "");

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      body?.detail ?? body?.error ?? `Request failed with status ${response.status}`,
    );
  }
  return response.json() as Promise<T>;
}

export async function getTerminalDiagnostics(): Promise<TerminalDiagnostics> {
  return parseResponse<TerminalDiagnostics>(
    await fetch(`${API_BASE_URL}/terminals/diagnostics`, { cache: "no-store" }),
  );
}

export async function listTerminalSessions(): Promise<ListTerminalSessionsResponse> {
  return parseResponse<ListTerminalSessionsResponse>(
    await fetch(`${API_BASE_URL}/terminals/sessions`, { cache: "no-store" }),
  );
}

export async function createTerminalSession(input: {
  shell?: "auto" | "pwsh" | "powershell";
  columns: number;
  rows: number;
}): Promise<CreateTerminalSessionResponse> {
  return parseResponse<CreateTerminalSessionResponse>(
    await fetch(`${API_BASE_URL}/terminals/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ shell: input.shell ?? "auto", ...input }),
    }),
  );
}

export async function launchClaude(
  sessionId: string,
  input: { mode: "new" | "continue" | "resume"; resume_id?: string },
): Promise<LaunchClaudeResponse> {
  return parseResponse<LaunchClaudeResponse>(
    await fetch(`${API_BASE_URL}/terminals/sessions/${sessionId}/claude`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export async function interruptTerminal(sessionId: string): Promise<TerminalSession> {
  return parseResponse<TerminalSession>(
    await fetch(`${API_BASE_URL}/terminals/sessions/${sessionId}/interrupt`, {
      method: "POST",
    }),
  );
}

export async function closeTerminal(sessionId: string): Promise<TerminalSession> {
  return parseResponse<TerminalSession>(
    await fetch(`${API_BASE_URL}/terminals/sessions/${sessionId}`, {
      method: "DELETE",
    }),
  );
}

export function terminalWebSocketUrl(sessionId: string): string {
  const url = new URL(API_BASE_URL);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = `${url.pathname.replace(/\/$/, "")}/terminals/sessions/${sessionId}/ws`;
  url.search = "";
  url.hash = "";
  return url.toString();
}
