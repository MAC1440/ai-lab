import {
    type AgentChatHistoryMessage,
    type AgentChatResponse,
    type AgentProfile,
    type AgentStreamEvent,
    type AgentToolExecution,
} from "@/features/agents/agent-api";
import { mapRuntimeMetric } from "@/features/home/components/agent-chat-metrics";
import {
    toolStatusMessage,
    upsertAgentTool,
} from "@/features/home/components/agent-chat-tools";
import type { HomeChatMessage } from "@/features/home/types";

export type AgentChatSettings = {
    ragTopK: number;
    ragDistanceThreshold: number | "";
    ragMode: "default" | "enabled" | "disabled";
    toolsMode: "default" | "enabled" | "disabled";
};

export const defaultAgentSettings: AgentChatSettings = {
    ragTopK: 3,
    ragDistanceThreshold: 1,
    ragMode: "default",
    toolsMode: "default",
};

export function buildHistory(
    messages: HomeChatMessage[],
): AgentChatHistoryMessage[] {
    return messages
        .filter((message) => message.content.trim().length > 0)
        .map((message) => ({
            role: message.role,
            content: message.content,
        }))
        .slice(-12);
}

export function createInitialAgentResult(
    agent: AgentProfile,
    settings: AgentChatSettings,
    distanceThreshold: number | null,
): AgentChatResponse {
    const ragEnabled = settings.ragMode === "default"
        ? agent.use_rag
        : settings.ragMode === "enabled";

    return {
        answer: "",
        agent_id: agent.id,
        model: agent.model,
        steps: 0,
        tools_used: [],
        rag: {
            enabled: ragEnabled,
            resolved_from: settings.ragMode === "default"
                ? "profile"
                : "request",
            context_found: false,
            retrieved_count: 0,
            included_count: 0,
            sources: [],
            distances: [],
            distance_threshold: distanceThreshold,
        },
        context: {
            enabled: false,
            workspace: null,
            project_types: [],
            selected_project_root: null,
            files_included: [],
            file_count: 0,
            prompt_paths_found: [],
            tree_entries: 0,
            tree_truncated: false,
            characters: 0,
            max_characters: 0,
            skipped_paths: [],
        },
    };
}

export function applyAgentStreamEvent(
    message: HomeChatMessage,
    event: AgentStreamEvent,
): HomeChatMessage {
    switch (event.type) {
        case "status":
            return applyStatusEvent(message, event);

        case "rag":
            return applyRagEvent(message, event);

        case "context":
            return applyContextEvent(message, event);

        case "answer_delta":
            return applyAnswerDeltaEvent(message, event);

        case "answer_reset":
            return applyAnswerResetEvent(message, event);

        case "tool_start":
            return applyToolStartEvent(message, event);

        case "tool_result":
            return applyToolResultEvent(message, event);

        case "metrics":
            return applyMetricsEvent(message, event);

        case "done":
            return applyDoneEvent(message, event);

        case "error":
            return applyErrorEvent(message, event);

        default:
            return assertNever(event);
    }
}

type StatusEvent = Extract<
    AgentStreamEvent,
    { type: "status" }
>;

type RagEvent = Extract<
    AgentStreamEvent,
    { type: "rag" }
>;

type ContextEvent = Extract<
    AgentStreamEvent,
    { type: "context" }
>;

type AnswerDeltaEvent = Extract<
    AgentStreamEvent,
    { type: "answer_delta" }
>;

type AnswerResetEvent = Extract<
    AgentStreamEvent,
    { type: "answer_reset" }
>;

type ToolStartEvent = Extract<
    AgentStreamEvent,
    { type: "tool_start" }
>;

type ToolResultEvent = Extract<
    AgentStreamEvent,
    { type: "tool_result" }
>;

type MetricsEvent = Extract<
    AgentStreamEvent,
    { type: "metrics" }
>;

type DoneEvent = Extract<
    AgentStreamEvent,
    { type: "done" }
>;

type ErrorEvent = Extract<
    AgentStreamEvent,
    { type: "error" }
>;

function applyStatusEvent(
    message: HomeChatMessage,
    event: StatusEvent,
): HomeChatMessage {
    return {
        ...message,
        streamingStatus: event.message,
        agentResult: message.agentResult
            ? {
                ...message.agentResult,
                steps: event.step
                    ?? message.agentResult.steps,
            }
            : undefined,
    };
}

function applyRagEvent(
    message: HomeChatMessage,
    event: RagEvent,
): HomeChatMessage {
    if (!message.agentResult) {
        return message;
    }

    return {
        ...message,
        agentResult: {
            ...message.agentResult,
            rag: event.rag,
        },
    };
}

function applyContextEvent(
    message: HomeChatMessage,
    event: ContextEvent,
): HomeChatMessage {
    if (!message.agentResult) {
        return message;
    }

    return {
        ...message,
        agentResult: {
            ...message.agentResult,
            context: event.context,
        },
    };
}

function applyAnswerDeltaEvent(
    message: HomeChatMessage,
    event: AnswerDeltaEvent,
): HomeChatMessage {
    return {
        ...message,
        content: message.content + event.content,
        agentResult: message.agentResult
            ? {
                ...message.agentResult,
                steps: event.step,
            }
            : undefined,
    };
}

function applyAnswerResetEvent(
    message: HomeChatMessage,
    event: AnswerResetEvent,
): HomeChatMessage {
    return {
        ...message,
        content: "",
        agentResult: message.agentResult
            ? {
                ...message.agentResult,
                steps: event.step,
            }
            : undefined,
    };
}

function applyToolStartEvent(
    message: HomeChatMessage,
    event: ToolStartEvent,
): HomeChatMessage {
    if (!message.agentResult) {
        return message;
    }

    const tool: AgentToolExecution = {
        id: event.call_id,
        name: event.name,
        arguments: event.arguments,
        status: "running",
    };

    return {
        ...message,
        streamingStatus: toolStatusMessage(tool),
        agentResult: {
            ...message.agentResult,
            steps: event.step,
            tools_used: upsertAgentTool(
                message.agentResult.tools_used,
                event.call_id,
                tool,
            ),
        },
    };
}

function applyToolResultEvent(
    message: HomeChatMessage,
    event: ToolResultEvent,
): HomeChatMessage {
    if (!message.agentResult) {
        return message;
    }

    return {
        ...message,
        streamingStatus: toolStatusMessage(event.tool),
        agentResult: {
            ...message.agentResult,
            steps: event.step,
            tools_used: upsertAgentTool(
                message.agentResult.tools_used,
                event.call_id,
                event.tool,
            ),
        },
    };
}

function applyMetricsEvent(
    message: HomeChatMessage,
    event: MetricsEvent,
): HomeChatMessage {
    return {
        ...message,
        metrics: mapRuntimeMetric(
            event.metrics,
            message.metrics,
        ),
    };
}

function applyDoneEvent(
    message: HomeChatMessage,
    event: DoneEvent,
): HomeChatMessage {
    const finalMetrics = event.result.runtime_metric
        ? mapRuntimeMetric(
            {
                ...event.result.runtime_metric,
                metric_kind: "measured",
                final: true,
            },
            message.metrics,
        )
        : message.metrics;

    return {
        ...message,
        content: event.result.answer,
        agentResult: event.result,
        metrics: finalMetrics,
        streamingStatus: undefined,
        streamError: undefined,
    };
}

function applyErrorEvent(
    message: HomeChatMessage,
    event: ErrorEvent,
): HomeChatMessage {
    return {
        ...message,
        streamingStatus: undefined,
        streamError: event.message,
    };
}

function assertNever(value: never): never {
    throw new Error(
        `Unhandled agent stream event: ${JSON.stringify(value)}`,
    );
}
