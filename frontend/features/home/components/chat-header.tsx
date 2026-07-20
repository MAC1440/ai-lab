"use client";

import { FolderCogIcon, Loader2Icon, SparklesIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { type AgentProfile } from "@/features/agents/agent-api";
import { WorkspacePicker } from "@/features/workspaces";
import { AgentRuntimeDialog } from "./agent-runtime-dialog";
import { ManagementMenu } from "./management-menu";
import { type AgentChatSettings } from "./agent-chat-state";

export function ChatHeader({
    agents, agentsLoading, selectedAgent, selectedAgentId, activeWorkspace,
    workspaceLoading, workspaceDialogOpen, settingsOpen, settings,
    recommendationReason, isSending, canClear, onAgentChange,
    onWorkspaceDialogChange, onWorkspaceSelected, onSettingsOpenChange,
    onSettingsChange, onClear, onAgentsRefresh,
}: {
    agents: AgentProfile[];
    agentsLoading: boolean;
    selectedAgent: AgentProfile | null;
    selectedAgentId: string;
    activeWorkspace: string | null;
    workspaceLoading: boolean;
    workspaceDialogOpen: boolean;
    settingsOpen: boolean;
    settings: AgentChatSettings;
    recommendationReason: string | null;
    isSending: boolean;
    canClear: boolean;
    onAgentChange: (agentId: string) => void;
    onWorkspaceDialogChange: (open: boolean) => void;
    onWorkspaceSelected: (workspace: string) => void;
    onSettingsOpenChange: (open: boolean) => void;
    onSettingsChange: (settings: AgentChatSettings) => void;
    onClear: () => void;
    onAgentsRefresh: () => Promise<void>;
}) {
    return <header className="border-b border-zinc-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-950">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-3">
                <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-violet-100 text-violet-700 dark:bg-violet-950/60 dark:text-violet-300"><SparklesIcon className="size-5" /></div>
                <div className="hidden min-w-0 sm:block"><h1 className="text-sm font-semibold">AI Lab</h1><p className="truncate text-xs text-zinc-500">Local agent workspace</p></div>
            </div>
            <div className="flex min-w-0 items-center justify-end gap-2">
                <Dialog open={workspaceDialogOpen} onOpenChange={onWorkspaceDialogChange}>
                    <DialogTrigger asChild><Button type="button" variant="outline" size="sm" title={activeWorkspace ?? "No workspace selected"}><FolderCogIcon className="mr-2 size-4" /><span className="hidden lg:inline">{workspaceLoading ? "Loading…" : activeWorkspace ? "Workspace" : "Select workspace"}</span></Button></DialogTrigger>
                    <DialogContent className="max-w-2xl"><DialogTitle>Select workspace</DialogTitle><DialogDescription>Tool-enabled agents are confined to this folder.</DialogDescription><WorkspacePicker activeWorkspace={activeWorkspace} onWorkspaceSelected={onWorkspaceSelected} /></DialogContent>
                </Dialog>
                {agentsLoading ? <Loader2Icon className="size-4 animate-spin text-zinc-500" /> : agents.length ? <Select value={selectedAgentId} onValueChange={onAgentChange}><SelectTrigger className="w-[150px] sm:w-[180px]"><SelectValue placeholder="Select agent" /></SelectTrigger><SelectContent>{agents.map((agent) => <SelectItem key={agent.id} value={agent.id}>{agent.name}</SelectItem>)}</SelectContent></Select> : null}
                <AgentRuntimeDialog open={settingsOpen} onOpenChange={onSettingsOpenChange} settings={settings} onSettingsChange={onSettingsChange} />
                <ManagementMenu agents={agents} disabled={isSending || agentsLoading} workspaceReady={Boolean(activeWorkspace)} onAgentsChanged={onAgentsRefresh} />
                <Button type="button" variant="ghost" size="sm" onClick={onClear} disabled={!canClear || isSending} className="hidden md:inline-flex">Clear</Button>
            </div>
        </div>
        {selectedAgent ? <div className="mx-auto mt-2 flex max-w-5xl items-center gap-2 overflow-hidden text-xs text-zinc-500">
            <span className="shrink-0 font-medium text-zinc-700 dark:text-zinc-200">{selectedAgent.name}</span><span>•</span>
            <span className="shrink-0">{settings.ragMode === "default" ? `RAG ${selectedAgent.use_rag ? "on" : "off"} (default)` : `RAG ${settings.ragMode} (override)`}</span>
            <span>•</span><span className="truncate">{settings.toolsMode === "disabled" ? "Tools disabled" : selectedAgent.tools.length ? `${selectedAgent.tools.length} tools available` : "No tools"}</span>
            {recommendationReason ? <><span>•</span><span className="truncate text-emerald-600">{recommendationReason}</span></> : null}
        </div> : null}
    </header>;
}
