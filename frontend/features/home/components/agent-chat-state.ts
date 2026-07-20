import {
    type AgentChatHistoryMessage,
    type AgentChatResponse,
    type AgentProfile,
    type AgentStreamEvent,
} from "@/features/agents/agent-api";
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

export function buildHistory(messages: HomeChatMessage[]): AgentChatHistoryMessage[] {
    return messages
        .filter((message) => message.content.trim().length > 0)
        .map((message) => ({ role: message.role, content: message.content }))
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
            resolved_from: settings.ragMode === "default" ? "profile" : "request",
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
    const result = message.agentResult;
    switch (event.type) {
        case "status":
            return { ...message, streamingStatus: event.message, agentResult: result ? { ...result, steps: event.step ?? result.steps } : result };
        case "rag":
            return result ? { ...message, agentResult: { ...result, rag: event.rag } } : message;
        case "context":
            return result ? { ...message, agentResult: { ...result, context: event.context } } : message;
        case "answer_delta":
            return { ...message, content: message.content + event.content, agentResult: result ? { ...result, answer: result.answer + event.content, steps: event.step } : result };
        case "answer_reset":
            return { ...message, content: "", agentResult: result ? { ...result, answer: "", steps: event.step } : result };
        case "tool_start":
            return result ? {
                ...message,
                streamingStatus: `Running ${event.name}`,
                agentResult: { ...result, steps: event.step, tools_used: [...result.tools_used, { id: event.call_id, name: event.name, arguments: event.arguments, status: "running" }] },
            } : message;
        case "tool_result":
            return result ? {
                ...message,
                streamingStatus: event.tool.status === "success" ? `${event.tool.name} completed` : `${event.tool.name} failed`,
                agentResult: {
                    ...result,
                    steps: event.step,
                    tools_used: result.tools_used.some((tool) => tool.id === event.call_id)
                        ? result.tools_used.map((tool) => tool.id === event.call_id ? event.tool : tool)
                        : [...result.tools_used, event.tool],
                },
            } : message;
        case "done":
            return { ...message, content: event.result.answer, agentResult: event.result, streamingStatus: undefined, streamError: undefined };
        case "error":
            return { ...message, streamingStatus: undefined, streamError: event.message };
        default:
            return message;
    }
}
