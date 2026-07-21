"use client";

import { useCallback, useRef } from "react";

import {
    type AgentChatRequest,
    type AgentStreamEvent,
    cancelAgentRun,
    streamAgentChat,
} from "@/features/agents/agent-api";

export function useAgentStream() {
    const abortControllerRef = useRef<AbortController | null>(null);
    const activeRunIdRef = useRef<string | null>(null);

    const run = useCallback(async (
        request: Omit<AgentChatRequest, "run_id">,
        onEvent: (event: AgentStreamEvent) => void,
    ) => {
        const runId = crypto.randomUUID();
        const controller = new AbortController();
        activeRunIdRef.current = runId;
        abortControllerRef.current = controller;
        let receivedDone = false;

        try {
            for await (const event of streamAgentChat(
                { ...request, run_id: runId },
                controller.signal,
            )) {
                onEvent(event);
                if (event.type === "error") throw new Error(event.message);
                if (event.type === "done") receivedDone = true;
            }
            if (!receivedDone) {
                throw new Error(
                    "The agent stream ended before sending a final result.",
                );
            }
        } finally {
            abortControllerRef.current = null;
            activeRunIdRef.current = null;
        }
    }, []);

    const stop = useCallback(() => {
        const runId = activeRunIdRef.current;
        abortControllerRef.current?.abort();
        if (runId) void cancelAgentRun(runId).catch(() => undefined);
    }, []);

    return { run, stop };
}
