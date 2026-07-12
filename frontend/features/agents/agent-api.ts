export type AgentProfile = {
    id: string;
    name: string;
    description: string;
    model: string;
    system_prompt: string;
    use_rag: boolean;
    tools: string[];
};

type AgentsResponse = {
    agents: AgentProfile[];
};

export type AgentChatHistoryMessage = {
    role: "user" | "assistant";
    content: string;
};

export type AgentToolExecution = {
    name: string;
    arguments: Record<string, unknown>;
    status: "success" | "error";
    error?: string;
};

export type AgentRagSource = {
    source?: string;
    chunk_index?: string | number;
    [key: string]: unknown;
};

export type AgentRagTrace = {
    enabled: boolean;
    context_found: boolean;
    retrieved_count: number;
    included_count: number;
    sources: AgentRagSource[];
    distances: Array<number | null>;
    distance_threshold: number | null;
};

export type AgentChatRequest = {
    agent_id: string;
    prompt: string;
    history?: AgentChatHistoryMessage[] | null;
    rag_top_k?: number;
    rag_distance_threshold?: number | null;
};

export type AgentChatResponse = {
    answer: string;
    agent_id: string;
    model: string;
    steps: number;
    tools_used: AgentToolExecution[];
    rag: AgentRagTrace;
};

const API_BASE_URL =
    process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

async function getErrorMessage(response: Response): Promise<string> {
    const body = (await response.json().catch(() => null)) as
        | {
            detail?: unknown;
            error?: unknown;
        }
        | null;

    if (typeof body?.detail === "string") {
        return body.detail;
    }

    // FastAPI validation errors normally arrive as an array of objects.
    if (Array.isArray(body?.detail)) {
        const messages = body.detail
            .map((item) => {
                if (
                    item &&
                    typeof item === "object" &&
                    "msg" in item &&
                    typeof item.msg === "string"
                ) {
                    return item.msg;
                }

                return null;
            })
            .filter((message): message is string => Boolean(message));

        if (messages.length > 0) {
            return messages.join(", ");
        }
    }

    if (typeof body?.error === "string") {
        return body.error;
    }

    return `Request failed with status ${response.status}`;
}

async function parseResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
        throw new Error(await getErrorMessage(response));
    }

    return response.json() as Promise<T>;
}

export async function getAgents(): Promise<AgentProfile[]> {
    const response = await fetch(`${API_BASE_URL}/agent/list`, {
        cache: "no-store",
    });

    const data = await parseResponse<AgentsResponse>(response);
    return data.agents;
}

export async function sendAgentChat(
    request: AgentChatRequest,
): Promise<AgentChatResponse> {
    const response = await fetch(`${API_BASE_URL}/agent/chat`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
    });

    return parseResponse<AgentChatResponse>(response);
}