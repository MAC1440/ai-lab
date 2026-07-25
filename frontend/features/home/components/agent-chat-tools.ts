import type {
    AgentToolExecution,
} from "@/features/agents/agent-api";

export function upsertAgentTool(
    tools: AgentToolExecution[],
    callId: string,
    tool: AgentToolExecution,
): AgentToolExecution[] {
    const existingIndex = tools.findIndex(
        (item) => item.id === callId,
    );

    if (existingIndex < 0) {
        return [...tools, tool];
    }

    return tools.map((item, index) =>
        index === existingIndex ? tool : item
    );
}

export function toolStatusMessage(
    tool: AgentToolExecution,
): string {
    if (tool.status === "running") {
        return `Running ${tool.name}`;
    }

    if (tool.status === "success") {
        return `${tool.name} completed`;
    }

    return `${tool.name} failed`;
}
