export type AgentProfile = {
    id: string;
    name: string;
    description: string;
    model: string;
    system_prompt: string;
    use_rag: boolean;
    tools: string[];
    project_types: string[];
};

export type AgentRecommendation = {
    agent_id: string;
    agent: AgentProfile;
    project_types: string[];
    reason: string;
    projects: Array<{ type: string; name: string; root: string }>;
};

type AgentsResponse = {
    agents: AgentProfile[];
};

export type AgentChatHistoryMessage = {
    role: "user" | "assistant";
    content: string;
};

export type AgentToolPolicy = "auto" | "inspect" | "propose";

export type AgentToolExecution = {
    id?: string;
    name: string;
    arguments: Record<string, unknown>;
    status: "running" | "success" | "error";
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

export type AgentProjectContextTrace = {
    enabled: boolean;
    workspace: string | null;
    project_types: string[];
    selected_project_root: string | null;
    files_included: string[];
    file_count: number;
    prompt_paths_found: string[];
    tree_entries: number;
    tree_truncated: boolean;
    characters: number;
    max_characters: number;
    skipped_paths: Array<{ path: string; reason: string }>;
};

export type AgentChatRequest = {
    agent_id: string;
    prompt: string;
    history?: AgentChatHistoryMessage[] | null;
    rag_top_k?: number;
    rag_distance_threshold?: number | null;
    tool_policy?: AgentToolPolicy;
    repair_task_id?: string | null;
    session_id?: string | null;
};

export type AgentChatResponse = {
    answer: string;
    agent_id: string;
    model: string;
    steps: number;
    tools_used: AgentToolExecution[];
    rag: AgentRagTrace;
    // Optional for backward compatibility with legacy/cached backend results.
    context?: AgentProjectContextTrace;
    change_set_id?: string | null;
    repair_task_id?: string | null;
    session_id?: string | null;
};

export type AgentStatusEvent = {
    type: "status";
    stage: "preparing" | "retrieving" | "model" | string;
    message: string;
    step?: number;
};

export type AgentRagEvent = {
    type: "rag";
    rag: AgentRagTrace;
};

export type AgentContextEvent = {
    type: "context";
    context: AgentProjectContextTrace;
};

export type AgentAnswerDeltaEvent = {
    type: "answer_delta";
    content: string;
    step: number;
};

export type AgentAnswerResetEvent = {
    type: "answer_reset";
    step: number;
};

export type AgentToolStartEvent = {
    type: "tool_start";
    call_id: string;
    name: string;
    arguments: Record<string, unknown>;
    step: number;
};

export type AgentToolResultEvent = {
    type: "tool_result";
    call_id: string;
    tool: AgentToolExecution;
    step: number;
};

export type AgentDoneEvent = {
    type: "done";
    result: AgentChatResponse;
};

export type AgentErrorEvent = {
    type: "error";
    message: string;
    status_code?: number;
};

export type AgentStreamEvent =
    | AgentStatusEvent
    | AgentRagEvent
    | AgentContextEvent
    | AgentAnswerDeltaEvent
    | AgentAnswerResetEvent
    | AgentToolStartEvent
    | AgentToolResultEvent
    | AgentDoneEvent
    | AgentErrorEvent;

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

export async function getAgentRecommendation(): Promise<AgentRecommendation> {
    const response = await fetch(`${API_BASE_URL}/agent/recommendation`, {
        cache: "no-store",
    });
    return parseResponse<AgentRecommendation>(response);
}

export async function* streamAgentChat(
    request: AgentChatRequest,
    signal?: AbortSignal,
): AsyncGenerator<AgentStreamEvent, void, void> {
    const response = await fetch(
        `${API_BASE_URL}/agent/chat/pydantic/stream`,
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Accept: "application/x-ndjson",
            },
            body: JSON.stringify(request),
            signal,
        },
    );

    if (!response.ok) {
        throw new Error(await getErrorMessage(response));
    }

    if (!response.body) {
        throw new Error("The browser did not receive a readable response stream.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
        const { done, value } = await reader.read();

        buffer += decoder.decode(value, {
            stream: !done,
        });

        let newlineIndex = buffer.indexOf("\n");
        while (newlineIndex >= 0) {
            const line = buffer.slice(0, newlineIndex).trim();
            buffer = buffer.slice(newlineIndex + 1);

            if (line) {
                yield parseAgentStreamEvent(line);
            }

            newlineIndex = buffer.indexOf("\n");
        }

        if (done) {
            break;
        }
    }

    const remainingLine = buffer.trim();
    if (remainingLine) {
        yield parseAgentStreamEvent(remainingLine);
    }
}

function parseAgentStreamEvent(line: string): AgentStreamEvent {
    let parsed: unknown;

    try {
        parsed = JSON.parse(line);
    } catch {
        throw new Error("The backend returned an invalid streaming event.");
    }

    if (
        !parsed ||
        typeof parsed !== "object" ||
        !("type" in parsed) ||
        typeof parsed.type !== "string"
    ) {
        throw new Error("The backend returned a malformed streaming event.");
    }

    return parsed as AgentStreamEvent;
}
