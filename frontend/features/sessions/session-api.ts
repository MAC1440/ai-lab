import type { AgentChatResponse } from "@/features/agents/agent-api";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

export type ConversationMessage = {
  message_id: string;
  session_id: string;
  sequence: number;
  role: "user" | "assistant";
  content: string;
  agent_result: AgentChatResponse | null;
  created_at: string;
};

export type ConversationSummary = {
  session_id: string;
  workspace: string;
  agent_id: string;
  title: string;
  status: "active" | "archived";
  rag_top_k: number;
  rag_distance_threshold: number | null;
  created_at: string;
  updated_at: string;
  message_count: number;
};

export type Conversation = ConversationSummary & {
  messages: ConversationMessage[];
};

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as
      | { detail?: unknown }
      | null;
    throw new Error(
      typeof body?.detail === "string"
        ? body.detail
        : `Conversation request failed with status ${response.status}`,
    );
  }
  return response.json() as Promise<T>;
}

export async function listConversations(includeArchived = false) {
  const result = await parseJson<{ sessions: ConversationSummary[] }>(
    await fetch(
      `${API_BASE_URL}/conversations?include_archived=${includeArchived}`,
      { cache: "no-store" },
    ),
  );
  return result.sessions;
}

export async function createConversation(input: {
  agentId: string;
  ragTopK: number;
  ragDistanceThreshold: number | null;
}) {
  return parseJson<Conversation>(
    await fetch(`${API_BASE_URL}/conversations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        agent_id: input.agentId,
        rag_top_k: input.ragTopK,
        rag_distance_threshold: input.ragDistanceThreshold,
      }),
    }),
  );
}

export async function getConversation(sessionId: string) {
  return parseJson<Conversation>(
    await fetch(`${API_BASE_URL}/conversations/${sessionId}`, {
      cache: "no-store",
    }),
  );
}

export async function updateConversation(
  sessionId: string,
  update: { title?: string; status?: "active" | "archived" },
) {
  return parseJson<Conversation>(
    await fetch(`${API_BASE_URL}/conversations/${sessionId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(update),
    }),
  );
}

export async function deleteConversation(sessionId: string) {
  const response = await fetch(`${API_BASE_URL}/conversations/${sessionId}`, {
    method: "DELETE",
  });
  if (!response.ok) await parseJson<never>(response);
}
