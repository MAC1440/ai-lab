import {
    type AgentChatHistoryMessage,
    type AgentChatResponse,
    type AgentProfile,
    type AgentRuntimeMetric,
    type AgentStreamEvent,
    type AgentToolExecution,
} from "@/features/agents/agent-api";
import type {
    HomeChatMessage,
    OllamaCompletionMetrics,
} from "@/features/home/types";

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

function mapRuntimeMetric(
    metric: AgentRuntimeMetric,
    current?: OllamaCompletionMetrics,
): OllamaCompletionMetrics {
    return {
        ...current,
        totalDurationMs: metric.duration_seconds * 1000,
        promptEvalCount: metric.input_tokens ?? current?.promptEvalCount,
        evalCount: metric.output_tokens,
        tokensPerSecond: metric.tokens_per_second ?? undefined,
        contextWindow: metric.context_window,
        contextUsedTokens:
            metric.context_used_tokens ?? current?.contextUsedTokens,
        contextRemainingTokens:
            metric.context_remaining_tokens ?? current?.contextRemainingTokens,
        maxOutputTokens: metric.max_tokens,
        safeInputTokens: metric.safe_input_tokens ?? current?.safeInputTokens,
        temperature: metric.temperature,
        live: !metric.final,
        metricKind: metric.metric_kind,
    };
}

function upsertTool(
    tools: AgentToolExecution[],
    callId: string,
    tool: AgentToolExecution,
): AgentToolExecution[] {
    const existingIndex = tools.findIndex((item) => item.id === callId);
    if (existingIndex < 0) {
        return [...tools, tool];
    }

    return tools.map((item, index) =>
        index === existingIndex ? tool : item
    );
}

export function applyAgentStreamEvent(
    message: HomeChatMessage,
    event: AgentStreamEvent,
): HomeChatMessage {
    const result = message.agentResult;

    switch (event.type) {
        case "status":
            return {
                ...message,
                streamingStatus: event.message,
                agentResult: result
                    ? {
                        ...result,
                        steps: event.step ?? result.steps,
                    }
                    : result,
            };

        case "rag":
            return result
                ? {
                    ...message,
                    agentResult: {
                        ...result,
                        rag: event.rag,
                    },
                }
                : message;

        case "context":
            return result
                ? {
                    ...message,
                    agentResult: {
                        ...result,
                        context: event.context,
                    },
                }
                : message;

        case "answer_delta":
            return {
                ...message,
                content: message.content + event.content,
                agentResult: result
                    ? {
                        ...result,
                        steps: event.step,
                    }
                    : result,
            };

        case "answer_reset":
            return {
                ...message,
                content: "",
                agentResult: result
                    ? {
                        ...result,
                        steps: event.step,
                    }
                    : result,
            };

        case "tool_start": {
            if (!result) return message;

            const runningTool: AgentToolExecution = {
                id: event.call_id,
                name: event.name,
                arguments: event.arguments,
                status: "running",
            };

            return {
                ...message,
                streamingStatus: `Running ${event.name}`,
                agentResult: {
                    ...result,
                    steps: event.step,
                    tools_used: upsertTool(
                        result.tools_used,
                        event.call_id,
                        runningTool,
                    ),
                },
            };
        }

        case "tool_result":
            return result
                ? {
                    ...message,
                    streamingStatus: event.tool.status === "success"
                        ? `${event.tool.name} completed`
                        : `${event.tool.name} failed`,
                    agentResult: {
                        ...result,
                        steps: event.step,
                        tools_used: upsertTool(
                            result.tools_used,
                            event.call_id,
                            event.tool,
                        ),
                    },
                }
                : message;

        case "metrics":
            return {
                ...message,
                metrics: mapRuntimeMetric(event.metrics, message.metrics),
            };

        case "done":
            return {
                ...message,
                content: event.result.answer,
                agentResult: event.result,
                metrics: event.result.runtime_metric
                    ? mapRuntimeMetric(
                        {
                            ...event.result.runtime_metric,
                            metric_kind: "measured",
                            final: true,
                        },
                        message.metrics,
                    )
                    : message.metrics,
                streamingStatus: undefined,
                streamError: undefined,
            };

        case "error":
            return {
                ...message,
                streamingStatus: undefined,
                streamError: event.message,
            };

        default: {
            const exhaustive: never = event;
            return exhaustive;
        }
    }
}
