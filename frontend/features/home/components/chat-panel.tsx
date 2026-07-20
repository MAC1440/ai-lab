"use client";

import {
    AlertCircleIcon,
    FolderCogIcon,
    SparklesIcon,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { TooltipProvider } from "@/components/ui/tooltip";
import {
    type AgentProfile,
    type AgentToolPolicy,
    cancelAgentRun,
    getAgentRecommendation,
    getAgents,
    streamAgentChat,
} from "@/features/agents/agent-api";
import {
    createConversation,
    deleteConversation,
    getConversation,
    listConversations,
    SessionSidebar,
    type ConversationSummary,
    updateConversation,
} from "@/features/sessions";
import { ChatInput } from "@/features/home/components/chat-input";
import { ChatMessageBubble } from "@/features/home/components/chat-message-bubble";
import { ChatHeader } from "@/features/home/components/chat-header";
import {
    applyAgentStreamEvent,
    buildHistory,
    createInitialAgentResult,
    defaultAgentSettings,
    type AgentChatSettings,
} from "@/features/home/components/agent-chat-state";
import type { HomeChatMessage } from "@/features/home/types";
import {
    VERIFICATION_FIX_REQUEST_EVENT,
    type VerificationFixRequestDetail,
} from "@/features/verification";
import { getActiveWorkspace } from "@/features/workspaces/workspace-api";

export function ChatPanel() {
    const [messages, setMessages] = useState<HomeChatMessage[]>([]);
    const [input, setInput] = useState("");
    const [error, setError] = useState<string | null>(null);
    const [isSending, setIsSending] = useState(false);
    const [sessions, setSessions] = useState<ConversationSummary[]>([]);
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [sessionsLoading, setSessionsLoading] = useState(false);
    const [showArchived, setShowArchived] = useState(false);

    const [agents, setAgents] = useState<AgentProfile[]>([]);
    const [selectedAgentId, setSelectedAgentId] = useState("general");
    const [agentsLoading, setAgentsLoading] = useState(true);
    const [recommendationReason, setRecommendationReason] =
        useState<string | null>(null);

    const [activeWorkspace, setActiveWorkspace] = useState<string | null>(null);
    const [workspaceLoading, setWorkspaceLoading] = useState(true);
    const [workspaceDialogOpen, setWorkspaceDialogOpen] = useState(false);

    const [settingsOpen, setSettingsOpen] = useState(false);
    const [settings, setSettings] =
        useState<AgentChatSettings>(defaultAgentSettings);

    const bottomRef = useRef<HTMLDivElement>(null);
    const nextToolPolicyRef = useRef<AgentToolPolicy>("auto");
    const freshHistoryForNextRequestRef = useRef(false);
    const nextRepairTaskIdRef = useRef<string | null>(null);
    const recommendedWorkspaceRef = useRef<string | null>(null);
    const abortControllerRef = useRef<AbortController | null>(null);
    const activeRunIdRef = useRef<string | null>(null);

    const selectedAgent = useMemo(
        () => agents.find((agent) => agent.id === selectedAgentId) ?? null,
        [agents, selectedAgentId],
    );

    const selectedAgentUsesTools = Boolean(
        selectedAgent?.tools.length && settings.toolsMode !== "disabled",
    );

    const refreshSessions = useCallback(async () => {
        if (!activeWorkspace) {
            setSessions([]);
            return;
        }
        setSessionsLoading(true);
        try {
            setSessions(await listConversations(showArchived));
        } catch (requestError) {
            setError(requestError instanceof Error ? requestError.message : "Could not load conversations.");
        } finally {
            setSessionsLoading(false);
        }
    }, [activeWorkspace, showArchived]);

    useEffect(() => {
        const loadId = window.setTimeout(() => {
            void refreshSessions();
        }, 0);
        return () => window.clearTimeout(loadId);
    }, [refreshSessions]);

    async function selectSession(session: ConversationSummary) {
        if (isSending) return;
        try {
            const conversation = await getConversation(session.session_id);
            setSessionId(conversation.session_id);
            setSelectedAgentId(conversation.agent_id);
            setSettings({
                ...defaultAgentSettings,
                ragTopK: conversation.rag_top_k,
                ragDistanceThreshold: conversation.rag_distance_threshold ?? "",
            });
            setMessages(conversation.messages.map((message) => ({
                id: message.message_id,
                role: message.role,
                content: message.content,
                agentResult: message.agent_result ?? undefined,
            })));
            setError(null);
        } catch (requestError) {
            setError(requestError instanceof Error ? requestError.message : "Conversation could not be opened.");
        }
    }

    function newConversation() {
        if (isSending) return;
        setSessionId(null);
        setMessages([]);
        setInput("");
        setError(null);
    }

    async function changeSessionStatus(session: ConversationSummary, status: "active" | "archived") {
        try {
            await updateConversation(session.session_id, { status });
            if (sessionId === session.session_id && status === "archived") newConversation();
            await refreshSessions();
        } catch (requestError) {
            setError(requestError instanceof Error ? requestError.message : "Conversation could not be updated.");
        }
    }

    async function renameSession(session: ConversationSummary) {
        const title = window.prompt("Conversation title", session.title)?.trim();
        if (!title || title === session.title) return;
        try {
            await updateConversation(session.session_id, { title });
            await refreshSessions();
        } catch (requestError) {
            setError(requestError instanceof Error ? requestError.message : "Conversation could not be renamed.");
        }
    }

    async function removeSession(session: ConversationSummary) {
        if (!window.confirm(`Permanently delete “${session.title}”?`)) return;
        try {
            await deleteConversation(session.session_id);
            if (sessionId === session.session_id) newConversation();
            await refreshSessions();
        } catch (requestError) {
            setError(requestError instanceof Error ? requestError.message : "Conversation could not be deleted.");
        }
    }

    useEffect(() => {
        bottomRef.current?.scrollIntoView({
            behavior: "smooth",
            block: "end",
        });
    }, [messages, isSending]);

    useEffect(() => {
        async function loadActiveWorkspace() {
            setWorkspaceLoading(true);

            try {
                const result = await getActiveWorkspace();
                setActiveWorkspace(result.workspace);
            } catch (requestError) {
                setError(
                    requestError instanceof Error
                        ? requestError.message
                        : "Could not load active workspace.",
                );
            } finally {
                setWorkspaceLoading(false);
            }
        }

        void loadActiveWorkspace();
    }, []);

    useEffect(() => {
        async function loadAgents() {
            setAgentsLoading(true);

            try {
                const result = await getAgents();
                setAgents(result);

                if (result.length > 0) {
                    setSelectedAgentId((current) => {
                        const stillExists = result.some(
                            (agent) => agent.id === current,
                        );

                        return stillExists ? current : result[0].id;
                    });
                }
            } catch (requestError) {
                setError(
                    requestError instanceof Error
                        ? requestError.message
                        : "Could not load agents.",
                );
            } finally {
                setAgentsLoading(false);
            }
        }

        void loadAgents();
    }, []);

    useEffect(() => {
        if (!activeWorkspace || agents.length === 0) return;
        if (recommendedWorkspaceRef.current === activeWorkspace) return;
        recommendedWorkspaceRef.current = activeWorkspace;
        void getAgentRecommendation()
            .then((recommendation) => {
                if (agents.some((agent) => agent.id === recommendation.agent_id)) {
                    setSelectedAgentId(recommendation.agent_id);
                    setSessionId(null);
                    setMessages([]);
                    setRecommendationReason(recommendation.reason);
                }
            })
            .catch((requestError: unknown) => {
                recommendedWorkspaceRef.current = null;
                setError(
                    requestError instanceof Error
                        ? requestError.message
                        : "Could not recommend an agent for this workspace.",
                );
            });
    }, [activeWorkspace, agents]);

    useEffect(() => {
        function handleVerificationFixRequest(event: Event) {
            const customEvent = event as CustomEvent<VerificationFixRequestDetail>;
            const prompt = customEvent.detail?.prompt;

            if (!prompt) {
                return;
            }

            setInput(prompt);
            setError(null);
            nextToolPolicyRef.current = customEvent.detail.toolPolicy;
            freshHistoryForNextRequestRef.current =
                customEvent.detail.freshContext;
            if (customEvent.detail.freshContext) {
                setSessionId(null);
                setMessages([]);
            }
            nextRepairTaskIdRef.current = customEvent.detail.repairTaskId;

            if (
                agents.some(
                    (agent) =>
                        agent.id === customEvent.detail.recommendedAgentId,
                )
            ) {
                setSelectedAgentId(customEvent.detail.recommendedAgentId);
                setRecommendationReason(
                    "Selected for the failed verification's project type.",
                );
            }
        }

        window.addEventListener(
            VERIFICATION_FIX_REQUEST_EVENT,
            handleVerificationFixRequest,
        );

        return () => {
            window.removeEventListener(
                VERIFICATION_FIX_REQUEST_EVENT,
                handleVerificationFixRequest,
            );
        };
    }, [agents]);

    async function handleSend() {
        const content = input.trim();

        if (!content || isSending || !selectedAgent) {
            return;
        }

        if (selectedAgentUsesTools && !activeWorkspace) {
            setError(
                `The ${selectedAgent.name} agent can use workspace tools. Select a workspace before sending this request.`,
            );
            setWorkspaceDialogOpen(true);
            return;
        }

        const distanceThreshold =
            settings.ragDistanceThreshold === ""
                ? null
                : settings.ragDistanceThreshold;

        let requestSessionId = sessionId;
        if (!requestSessionId) {
            try {
                const created = await createConversation({
                    agentId: selectedAgent.id,
                    ragTopK: settings.ragTopK,
                    ragDistanceThreshold: distanceThreshold,
                });
                requestSessionId = created.session_id;
                setSessionId(created.session_id);
            } catch (requestError) {
                setError(requestError instanceof Error ? requestError.message : "Conversation could not be created.");
                return;
            }
        }

        const userMessage: HomeChatMessage = {
            id: crypto.randomUUID(),
            role: "user",
            content,
        };

        const assistantPlaceholder: HomeChatMessage = {
            id: crypto.randomUUID(),
            role: "assistant",
            content: "",
            streamingStatus: "Preparing the selected agent",
            agentResult: createInitialAgentResult(
                selectedAgent,
                settings,
                distanceThreshold,
            ),
        };

        const history = requestSessionId || freshHistoryForNextRequestRef.current
            ? []
            : buildHistory(messages);
        const toolPolicy = nextToolPolicyRef.current;
        const repairTaskId = nextRepairTaskIdRef.current;
        const pendingMessages = [...messages, userMessage];

        nextToolPolicyRef.current = "auto";
        freshHistoryForNextRequestRef.current = false;
        nextRepairTaskIdRef.current = null;

        setMessages([...pendingMessages, assistantPlaceholder]);
        setInput("");
        setError(null);
        setIsSending(true);

        let receivedDoneEvent = false;
        const runId = crypto.randomUUID();
        const abortController = new AbortController();
        activeRunIdRef.current = runId;
        abortControllerRef.current = abortController;

        const updateAssistantMessage = (
            updater: (message: HomeChatMessage) => HomeChatMessage,
        ) => {
            setMessages((currentMessages) =>
                currentMessages.map((message) =>
                    message.id === assistantPlaceholder.id
                        ? updater(message)
                        : message,
                ),
            );
        };

        try {
            for await (const event of streamAgentChat({
                agent_id: selectedAgent.id,
                prompt: content,
                history: history.length > 0 ? history : null,
                rag_top_k: settings.ragTopK,
                rag_distance_threshold: distanceThreshold,
                tool_policy: toolPolicy,
                repair_task_id: repairTaskId,
                session_id: requestSessionId,
                run_id: runId,
                rag_mode: settings.ragMode,
                tools_enabled: settings.toolsMode === "default" ? null : settings.toolsMode === "enabled",
                enabled_tools: settings.toolsMode === "enabled" ? selectedAgent.tools : null,
            }, abortController.signal)) {
                if (event.type === "error") {
                    updateAssistantMessage((message) =>
                        applyAgentStreamEvent(message, event),
                    );
                    throw new Error(event.message);
                }

                if (event.type === "done") {
                    receivedDoneEvent = true;
                }

                updateAssistantMessage((message) =>
                    applyAgentStreamEvent(message, event),
                );
            }

            if (!receivedDoneEvent) {
                throw new Error(
                    "The agent stream ended before sending a final result.",
                );
            }
            await refreshSessions();
        } catch (requestError) {
            const stopped = requestError instanceof DOMException && requestError.name === "AbortError";
            const message =
                stopped
                    ? "Response stopped"
                    : requestError instanceof Error
                    ? requestError.message
                    : "The message could not be sent.";

            updateAssistantMessage((assistantMessage) => ({
                ...assistantMessage,
                streamingStatus: undefined,
                streamError: stopped ? undefined : assistantMessage.streamError ?? message,
            }));
            setError(stopped ? null : message);
        } finally {
            abortControllerRef.current = null;
            activeRunIdRef.current = null;
            setIsSending(false);
        }
    }

    function handleStop() {
        const runId = activeRunIdRef.current;
        abortControllerRef.current?.abort();
        if (runId) void cancelAgentRun(runId).catch(() => undefined);
    }

    function handleClear() {
        setSessionId(null);
        setMessages([]);
        setError(null);
        nextToolPolicyRef.current = "auto";
        freshHistoryForNextRequestRef.current = false;
        nextRepairTaskIdRef.current = null;
    }

    const inputDisabled =
        isSending ||
        agentsLoading ||
        !selectedAgent ||
        (selectedAgentUsesTools && !activeWorkspace);

    return (
        <TooltipProvider>
            <div className="flex h-screen min-h-0 bg-white dark:bg-zinc-950">
                <SessionSidebar
                    sessions={sessions}
                    selectedId={sessionId}
                    loading={sessionsLoading}
                    disabled={isSending || !activeWorkspace}
                    showArchived={showArchived}
                    onShowArchivedChange={setShowArchived}
                    onNew={newConversation}
                    onSelect={(session) => void selectSession(session)}
                    onArchive={(session) => void changeSessionStatus(session, "archived")}
                    onRename={(session) => void renameSession(session)}
                    onRestore={(session) => void changeSessionStatus(session, "active")}
                    onDelete={(session) => void removeSession(session)}
                />
                <div className="flex min-w-0 flex-1 flex-col">
                <ChatHeader
                    agents={agents}
                    agentsLoading={agentsLoading}
                    selectedAgent={selectedAgent}
                    selectedAgentId={selectedAgentId}
                    activeWorkspace={activeWorkspace}
                    workspaceLoading={workspaceLoading}
                    workspaceDialogOpen={workspaceDialogOpen}
                    settingsOpen={settingsOpen}
                    settings={settings}
                    recommendationReason={recommendationReason}
                    isSending={isSending}
                    canClear={messages.length > 0}
                    onAgentChange={(agentId) => {
                        setSelectedAgentId(agentId);
                        setSessionId(null);
                        setRecommendationReason(null);
                        setMessages([]);
                        setError(null);
                        nextToolPolicyRef.current = "auto";
                        freshHistoryForNextRequestRef.current = false;
                    }}
                    onWorkspaceDialogChange={setWorkspaceDialogOpen}
                    onWorkspaceSelected={(workspace) => {
                        setActiveWorkspace(workspace);
                        recommendedWorkspaceRef.current = null;
                        setSessionId(null);
                        setMessages([]);
                        setError(null);
                        nextToolPolicyRef.current = "auto";
                        freshHistoryForNextRequestRef.current = false;
                        setWorkspaceDialogOpen(false);
                    }}
                    onSettingsOpenChange={setSettingsOpen}
                    onSettingsChange={setSettings}
                    onClear={handleClear}
                    onAgentsRefresh={async () => setAgents(await getAgents())}
                />

                <main className="min-h-0 flex-1">
                    <ScrollArea className="h-full">
                        <div className="mx-auto max-w-5xl">
                            {messages.length === 0 ? (
                                <div className="flex min-h-[55vh] items-center justify-center px-6 py-16 text-center">
                                    <div className="max-w-xl space-y-3">
                                        <div className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300">
                                            <SparklesIcon className="size-6" />
                                        </div>

                                        <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
                                            {selectedAgent
                                                ? `Chat with ${selectedAgent.name}`
                                                : "Select an agent"}
                                        </h2>

                                        <p className="text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
                                            {selectedAgent?.description ??
                                                "Choose an agent to begin."}
                                        </p>

                                        {selectedAgentUsesTools && !activeWorkspace ? (
                                            <Button
                                                type="button"
                                                variant="outline"
                                                onClick={() => setWorkspaceDialogOpen(true)}
                                            >
                                                <FolderCogIcon className="mr-2 size-4" />
                                                Select a workspace for tools
                                            </Button>
                                        ) : null}
                                    </div>
                                </div>
                            ) : (
                                <div className="divide-y divide-zinc-100 dark:divide-zinc-900">
                                    {messages.map((message, index) => (
                                        <ChatMessageBubble
                                            key={message.id}
                                            message={message}
                                            isStreaming={
                                                isSending &&
                                                index === messages.length - 1 &&
                                                message.role === "assistant"
                                            }
                                        />
                                    ))}
                                </div>
                            )}

                            <div ref={bottomRef} />
                        </div>
                    </ScrollArea>
                </main>

                <footer className="border-t border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
                    <div className="mx-auto max-w-5xl">
                        {error ? (
                            <div className="mb-3 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">
                                <AlertCircleIcon className="mt-0.5 size-4 shrink-0" />
                                <span>{error}</span>
                            </div>
                        ) : null}

                        <ChatInput
                            value={input}
                            onChange={setInput}
                            onSubmit={handleSend}
                            disabled={inputDisabled}
                            streaming={isSending}
                            onStop={handleStop}
                            placeholder={
                                selectedAgentUsesTools && !activeWorkspace
                                    ? "Select a workspace before using this agent…"
                                    : selectedAgent
                                        ? `Message ${selectedAgent.name}…`
                                        : "Loading agents…"
                            }
                        />

                        <p className="mt-2 text-center text-[11px] text-zinc-400">
                            RAG progress, tool execution, and answer tokens are streamed from
                            the backend as newline-delimited JSON events.
                        </p>
                    </div>
                </footer>
                </div>
            </div>
        </TooltipProvider>
    );
}
