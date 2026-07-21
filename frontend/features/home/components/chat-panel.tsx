"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { TooltipProvider } from "@/components/ui/tooltip";
import {
    type AgentProfile,
    getAgentRecommendation,
    getAgents,
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
import { ChatHeader } from "@/features/home/components/chat-header";
import { ChatComposer } from "@/features/home/components/chat-composer";
import { ChatTranscript } from "@/features/home/components/chat-transcript";
import {
    applyAgentStreamEvent,
    buildHistory,
    createInitialAgentResult,
    defaultAgentSettings,
    type AgentChatSettings,
} from "@/features/home/components/agent-chat-state";
import type { HomeChatMessage } from "@/features/home/types";
import { getActiveWorkspace } from "@/features/workspaces/workspace-api";
import { useAgentStream } from "@/features/home/hooks/use-agent-stream";
import {
    type ExternalAgentRequest,
    useExternalAgentRequest,
} from "@/features/home/hooks/use-external-agent-request";

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
    const recommendedWorkspaceRef = useRef<string | null>(null);
    const agentStream = useAgentStream();

    const loadExternalRequest = useCallback((request: ExternalAgentRequest) => {
        setInput(request.prompt);
        setError(null);
        if (request.freshContext) {
            setSessionId(null);
            setMessages([]);
        }
        if (agents.some((agent) => agent.id === request.recommendedAgentId)) {
            setSelectedAgentId(request.recommendedAgentId);
            setRecommendationReason(request.recommendationReason);
        }
    }, [agents]);
    const externalRequest = useExternalAgentRequest(loadExternalRequest);

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

        const pendingRequest = externalRequest.consume();
        const history = requestSessionId || pendingRequest.freshContext
            ? []
            : buildHistory(messages);
        const toolPolicy = pendingRequest.toolPolicy;
        const repairTaskId = pendingRequest.repairTaskId;
        const projectTaskId = pendingRequest.projectTaskId;
        const pendingMessages = [...messages, userMessage];

        setMessages([...pendingMessages, assistantPlaceholder]);
        setInput("");
        setError(null);
        setIsSending(true);

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
            await agentStream.run({
                agent_id: selectedAgent.id,
                prompt: content,
                history: history.length > 0 ? history : null,
                rag_top_k: settings.ragTopK,
                rag_distance_threshold: distanceThreshold,
                tool_policy: toolPolicy,
                repair_task_id: repairTaskId,
                project_task_id: projectTaskId,
                session_id: requestSessionId,
                rag_mode: settings.ragMode,
                // Keep the legacy boolean during the API migration. Current
                // backends prioritize rag_mode; older backends understand this
                // field instead of silently falling back to the agent profile.
                rag_enabled: settings.ragMode === "default"
                    ? null
                    : settings.ragMode === "enabled",
                tools_enabled: settings.toolsMode === "default" ? null : settings.toolsMode === "enabled",
                enabled_tools: settings.toolsMode === "enabled" ? selectedAgent.tools : null,
            }, (event) => {
                updateAssistantMessage((message) =>
                    applyAgentStreamEvent(message, event),
                );
            });
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
            setIsSending(false);
        }
    }

    function handleStop() {
        agentStream.stop();
    }

    function handleClear() {
        setSessionId(null);
        setMessages([]);
        setError(null);
        externalRequest.reset();
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
                        externalRequest.reset();
                    }}
                    onWorkspaceDialogChange={setWorkspaceDialogOpen}
                    onWorkspaceSelected={(workspace) => {
                        setActiveWorkspace(workspace);
                        recommendedWorkspaceRef.current = null;
                        setSessionId(null);
                        setMessages([]);
                        setError(null);
                        externalRequest.reset();
                        setWorkspaceDialogOpen(false);
                    }}
                    onSettingsOpenChange={setSettingsOpen}
                    onSettingsChange={setSettings}
                    onClear={handleClear}
                    onAgentsRefresh={async () => setAgents(await getAgents())}
                />

                <ChatTranscript
                    messages={messages}
                    isSending={isSending}
                    selectedAgent={selectedAgent}
                    selectedAgentUsesTools={selectedAgentUsesTools}
                    activeWorkspace={activeWorkspace}
                    onSelectWorkspace={() => setWorkspaceDialogOpen(true)}
                    bottomRef={bottomRef}
                />
                <ChatComposer
                    error={error}
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
                </div>
            </div>
        </TooltipProvider>
    );
}
