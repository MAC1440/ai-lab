"use client";

import {
    AlertCircleIcon,
    FolderCogIcon,
    Loader2Icon,
    Settings2Icon,
    SparklesIcon,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { TooltipProvider } from "@/components/ui/tooltip";
import {
    type AgentChatHistoryMessage,
    type AgentChatResponse,
    type AgentProfile,
    type AgentStreamEvent,
    type AgentToolPolicy,
    getAgentRecommendation,
    getAgents,
    streamAgentChat,
} from "@/features/agents/agent-api";
import { RepairDialog } from "@/features/repairs";
import { ModelSettingsDialog } from "@/features/model-settings";
import { ScaffoldDialog } from "@/features/scaffolds";
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
import type { HomeChatMessage } from "@/features/home/types";
import {
    VERIFICATION_FIX_REQUEST_EVENT,
    type VerificationFixRequestDetail,
    VerificationDialog,
} from "@/features/verification";
import { WorkspacePicker } from "@/features/workspaces";
import { getActiveWorkspace } from "@/features/workspaces/workspace-api";

type AgentChatSettings = {
    ragTopK: number;
    // An empty value is sent as null, which disables distance filtering.
    ragDistanceThreshold: number | "";
};

const defaultAgentSettings: AgentChatSettings = {
    ragTopK: 3,
    ragDistanceThreshold: 1,
};

function buildHistory(
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

function createInitialAgentResult(
    agent: AgentProfile,
    distanceThreshold: number | null,
): AgentChatResponse {
    return {
        answer: "",
        agent_id: agent.id,
        model: agent.model,
        steps: 0,
        tools_used: [],
        rag: {
            enabled: agent.use_rag,
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

function applyAgentStreamEvent(
    message: HomeChatMessage,
    event: AgentStreamEvent,
): HomeChatMessage {
    const currentResult = message.agentResult;

    switch (event.type) {
        case "status":
            return {
                ...message,
                streamingStatus: event.message,
                agentResult: currentResult
                    ? {
                        ...currentResult,
                        steps: event.step ?? currentResult.steps,
                    }
                    : currentResult,
            };

        case "rag":
            return currentResult
                ? {
                    ...message,
                    agentResult: {
                        ...currentResult,
                        rag: event.rag,
                    },
                }
                : message;

        case "context":
            return currentResult
                ? {
                    ...message,
                    agentResult: {
                        ...currentResult,
                        context: event.context,
                    },
                }
                : message;

        case "answer_delta":
            return {
                ...message,
                content: message.content + event.content,
                agentResult: currentResult
                    ? {
                        ...currentResult,
                        answer: currentResult.answer + event.content,
                        steps: event.step,
                    }
                    : currentResult,
            };

        case "answer_reset":
            return {
                ...message,
                content: "",
                agentResult: currentResult
                    ? {
                        ...currentResult,
                        answer: "",
                        steps: event.step,
                    }
                    : currentResult,
            };

        case "tool_start":
            return currentResult
                ? {
                    ...message,
                    streamingStatus: `Running ${event.name}`,
                    agentResult: {
                        ...currentResult,
                        steps: event.step,
                        tools_used: [
                            ...currentResult.tools_used,
                            {
                                id: event.call_id,
                                name: event.name,
                                arguments: event.arguments,
                                status: "running",
                            },
                        ],
                    },
                }
                : message;

        case "tool_result":
            return currentResult
                ? {
                    ...message,
                    streamingStatus:
                        event.tool.status === "success"
                            ? `${event.tool.name} completed`
                            : `${event.tool.name} failed`,
                    agentResult: {
                        ...currentResult,
                        steps: event.step,
                        tools_used: currentResult.tools_used.some(
                            (tool) => tool.id === event.call_id,
                        )
                            ? currentResult.tools_used.map((tool) =>
                                tool.id === event.call_id ? event.tool : tool,
                            )
                            : [...currentResult.tools_used, event.tool],
                    },
                }
                : message;

        case "done":
            return {
                ...message,
                content: event.result.answer,
                agentResult: event.result,
                streamingStatus: undefined,
                streamError: undefined,
            };

        case "error":
            return {
                ...message,
                streamingStatus: undefined,
                streamError: event.message,
            };

        default:
            return message;
    }
}

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

    const selectedAgent = useMemo(
        () => agents.find((agent) => agent.id === selectedAgentId) ?? null,
        [agents, selectedAgentId],
    );

    const selectedAgentUsesTools = Boolean(selectedAgent?.tools.length);

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
            })) {
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
            const message =
                requestError instanceof Error
                    ? requestError.message
                    : "The message could not be sent.";

            updateAssistantMessage((assistantMessage) => ({
                ...assistantMessage,
                streamingStatus: undefined,
                streamError: assistantMessage.streamError ?? message,
            }));
            setError(message);
        } finally {
            setIsSending(false);
        }
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
                <header className="border-b border-zinc-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-950">
                    <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3">
                        <div className="flex items-center gap-3">
                            <div className="flex size-9 items-center justify-center rounded-lg bg-violet-100 text-violet-700 dark:bg-violet-950/60 dark:text-violet-300">
                                <SparklesIcon className="size-5" />
                            </div>

                            <div>
                                <h1 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                                    AI Lab Agent Chat
                                </h1>
                                <p className="text-xs text-zinc-500 dark:text-zinc-400">
                                    RAG retrieval and workspace tools through FastAPI
                                </p>
                            </div>
                        </div>

                        <div className="flex flex-wrap items-center justify-end gap-2">
                            <div className="hidden max-w-[260px] items-center gap-2 rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 md:flex dark:border-zinc-800 dark:bg-zinc-900">
                                <FolderCogIcon className="size-4 shrink-0 text-violet-600 dark:text-violet-400" />

                                <div className="min-w-0">
                                    <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">
                                        Workspace
                                    </p>
                                    <p
                                        className="truncate text-xs font-medium text-zinc-800 dark:text-zinc-200"
                                        title={activeWorkspace ?? "No workspace selected"}
                                    >
                                        {workspaceLoading
                                            ? "Loading…"
                                            : activeWorkspace ?? "Not selected"}
                                    </p>
                                </div>
                            </div>

                            <Dialog
                                open={workspaceDialogOpen}
                                onOpenChange={setWorkspaceDialogOpen}
                            >
                                <DialogTrigger asChild>
                                    <Button type="button" variant="outline" size="sm">
                                        <FolderCogIcon className="mr-2 size-4" />
                                        {activeWorkspace
                                            ? "Change workspace"
                                            : "Select workspace"}
                                    </Button>
                                </DialogTrigger>

                                <DialogContent className="max-w-2xl">
                                    <DialogTitle>Select workspace</DialogTitle>
                                    <DialogDescription>
                                        Tool-enabled agents can only inspect files inside the
                                        selected folder. The workspace is selected through the
                                        workspace API and is not sent inside every chat request.
                                    </DialogDescription>

                                    <WorkspacePicker
                                        activeWorkspace={activeWorkspace}
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
                                    />
                                </DialogContent>
                            </Dialog>

                            <VerificationDialog
                                disabled={!activeWorkspace || isSending}
                            />

                            <RepairDialog
                                disabled={!activeWorkspace || isSending}
                            />

                            <ScaffoldDialog
                                disabled={!activeWorkspace || isSending}
                            />

                            <ModelSettingsDialog
                                agents={agents}
                                disabled={isSending || agentsLoading}
                                onSaved={async () => {
                                    const refreshed = await getAgents();
                                    setAgents(refreshed);
                                }}
                            />

                            {agentsLoading ? (
                                <div className="flex items-center gap-2 px-2 text-xs text-zinc-500">
                                    <Loader2Icon className="size-4 animate-spin" />
                                    Loading agents…
                                </div>
                            ) : agents.length > 0 ? (
                                <Select
                                    value={selectedAgentId}
                                    onValueChange={(agentId) => {
                                        setSelectedAgentId(agentId);
                                        setSessionId(null);
                                        setRecommendationReason(null);
                                        setMessages([]);
                                        setError(null);
                                        nextToolPolicyRef.current = "auto";
                                        freshHistoryForNextRequestRef.current = false;
                                    }}
                                >
                                    <SelectTrigger className="w-[180px]">
                                        <SelectValue placeholder="Select agent" />
                                    </SelectTrigger>

                                    <SelectContent>
                                        {agents.map((agent) => (
                                            <SelectItem key={agent.id} value={agent.id}>
                                                {agent.name}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            ) : null}

                            <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
                                <DialogTrigger asChild>
                                    <Button type="button" variant="outline" size="sm">
                                        <Settings2Icon className="mr-2 size-4" />
                                        Retrieval
                                    </Button>
                                </DialogTrigger>

                                <DialogContent className="max-w-lg">
                                    <DialogTitle>Agent retrieval settings</DialogTitle>
                                    <DialogDescription>
                                        These values map directly to the supported
                                        <code className="mx-1">
                                            /agent/chat/pydantic/stream
                                        </code>
                                        request fields. Agents with RAG disabled safely ignore
                                        them.
                                    </DialogDescription>

                                    <div className="grid gap-4 py-2 sm:grid-cols-2">
                                        <div className="space-y-2">
                                            <Label htmlFor="rag-top-k">RAG top K</Label>
                                            <Input
                                                id="rag-top-k"
                                                type="number"
                                                min={1}
                                                max={10}
                                                step={1}
                                                value={settings.ragTopK}
                                                onChange={(event) => {
                                                    const value = Number(event.target.value);

                                                    setSettings((current) => ({
                                                        ...current,
                                                        ragTopK: Number.isFinite(value)
                                                            ? Math.min(10, Math.max(1, Math.trunc(value)))
                                                            : 3,
                                                    }));
                                                }}
                                            />
                                            <p className="text-xs text-zinc-500">
                                                Number of candidate chunks requested from Chroma.
                                            </p>
                                        </div>

                                        <div className="space-y-2">
                                            <Label htmlFor="rag-distance-threshold">
                                                Distance threshold
                                            </Label>
                                            <Input
                                                id="rag-distance-threshold"
                                                type="number"
                                                min={0}
                                                step={0.05}
                                                placeholder="Empty disables filtering"
                                                value={settings.ragDistanceThreshold}
                                                onChange={(event) => {
                                                    const rawValue = event.target.value;

                                                    setSettings((current) => ({
                                                        ...current,
                                                        ragDistanceThreshold:
                                                            rawValue === ""
                                                                ? ""
                                                                : Math.max(0, Number(rawValue)),
                                                    }));
                                                }}
                                            />
                                            <p className="text-xs text-zinc-500">
                                                Smaller distances are generally closer matches. Leave
                                                empty to send null and disable the filter.
                                            </p>
                                        </div>
                                    </div>

                                    <div className="flex justify-end gap-2">
                                        <Button
                                            type="button"
                                            variant="outline"
                                            onClick={() => setSettings(defaultAgentSettings)}
                                        >
                                            Reset
                                        </Button>
                                        <Button
                                            type="button"
                                            onClick={() => setSettingsOpen(false)}
                                        >
                                            Done
                                        </Button>
                                    </div>
                                </DialogContent>
                            </Dialog>

                            <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                onClick={handleClear}
                                disabled={messages.length === 0 || isSending}
                            >
                                Clear
                            </Button>
                        </div>
                    </div>

                    {selectedAgent ? (
                        <div className="mx-auto mt-3 flex max-w-5xl flex-wrap items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">
                            <span className="font-medium text-zinc-700 dark:text-zinc-200">
                                {selectedAgent.name}
                            </span>
                            <span>•</span>
                            <span>{selectedAgent.model}</span>
                            <span>•</span>
                            <span>
                                {selectedAgent.use_rag ? "RAG enabled" : "RAG disabled"}
                            </span>
                            <span>•</span>
                            <span>
                                {selectedAgent.tools.length > 0
                                    ? `Tools: ${selectedAgent.tools.join(", ")}`
                                    : "No tools"}
                            </span>
                            {recommendationReason ? (
                                <>
                                    <span>•</span>
                                    <span className="text-emerald-600 dark:text-emerald-400">
                                        {recommendationReason}
                                    </span>
                                </>
                            ) : null}
                        </div>
                    ) : null}
                </header>

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
