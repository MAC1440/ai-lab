"use client";

import {
  FolderCogIcon,
  Loader2Icon,
  SparklesIcon,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { type AgentProfile } from "@/features/agents/agent-api";
import {
  ChatModelSelector,
  type ChatModelSelectionStatus,
} from "@/features/home/components/chat-model-selector";
import type { AgentModelSettings } from "@/features/model-settings/model-settings-api";
import { WorkspacePicker } from "@/features/workspaces";
import { AgentRuntimeDialog } from "./agent-runtime-dialog";
import { type AgentChatSettings } from "./agent-chat-state";

export function ChatHeader({
  agents,
  agentsLoading,
  selectedAgent,
  selectedAgentId,
  activeWorkspace,
  workspaceLoading,
  workspaceDialogOpen,
  settingsOpen,
  settings,
  recommendationReason,
  modelStatus,
  isSending,
  canClear,
  hasConversation,
  onAgentChange,
  onWorkspaceDialogChange,
  onWorkspaceSelected,
  onSettingsOpenChange,
  onSettingsChange,
  onModelStatusChange,
  onModelAssignmentChanged,
  onModelError,
  onClear,
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
  modelStatus: ChatModelSelectionStatus;
  isSending: boolean;
  canClear: boolean;
  hasConversation: boolean;
  onAgentChange: (agentId: string) => void;
  onWorkspaceDialogChange: (open: boolean) => void;
  onWorkspaceSelected: (workspace: string) => void;
  onSettingsOpenChange: (open: boolean) => void;
  onSettingsChange: (settings: AgentChatSettings) => void;
  onModelStatusChange: (
    status: ChatModelSelectionStatus,
  ) => void;
  onModelAssignmentChanged: (
    assignment: AgentModelSettings,
  ) => void | Promise<void>;
  onModelError: (message: string | null) => void;
  onClear: () => void;
}) {
  return (
    <header className="border-b border-border bg-surface px-4 py-3">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-accent/15 text-accent">
            <SparklesIcon className="size-5" />
          </div>
          <div className="hidden min-w-0 sm:block">
            <h1 className="text-sm font-semibold text-foreground">
              AI Lab
            </h1>
            <p className="truncate text-xs text-muted-foreground">
              Local and cloud agent workspace
            </p>
          </div>
        </div>

        <div className="flex min-w-0 flex-1 flex-wrap items-center justify-end gap-2">
          <Dialog
            open={workspaceDialogOpen}
            onOpenChange={onWorkspaceDialogChange}
          >
            <DialogTrigger asChild>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="cursor-pointer"
                title={activeWorkspace ?? "No workspace selected"}
              >
                <FolderCogIcon className="mr-2 size-4" />
                <span className="hidden lg:inline">
                  {workspaceLoading
                    ? "Loading…"
                    : activeWorkspace
                      ? "Workspace"
                      : "Select workspace"}
                </span>
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogTitle>Select workspace</DialogTitle>
              <DialogDescription>
                Tool-enabled agents are confined to this folder.
              </DialogDescription>
              <WorkspacePicker
                activeWorkspace={activeWorkspace}
                onWorkspaceSelected={onWorkspaceSelected}
              />
            </DialogContent>
          </Dialog>

          {agentsLoading ? (
            <Loader2Icon className="size-4 animate-spin text-muted-foreground" />
          ) : agents.length ? (
            <Select
              value={selectedAgentId}
              onValueChange={onAgentChange}
              disabled={isSending}
            >
              <SelectTrigger className="w-[145px] cursor-pointer sm:w-[175px]">
                <SelectValue placeholder="Select agent" />
              </SelectTrigger>
              <SelectContent>
                {agents.map((agent) => (
                  <SelectItem
                    key={agent.id}
                    value={agent.id}
                    className="cursor-pointer"
                  >
                    {agent.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : null}

          {selectedAgent ? (
            <ChatModelSelector
              agentId={selectedAgent.id}
              disabled={isSending || agentsLoading}
              hasConversation={hasConversation}
              onStatusChange={onModelStatusChange}
              onAssignmentChanged={onModelAssignmentChanged}
              onError={onModelError}
            />
          ) : null}

          <AgentRuntimeDialog
            open={settingsOpen}
            onOpenChange={onSettingsOpenChange}
            settings={settings}
            onSettingsChange={onSettingsChange}
          />

          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onClear}
            disabled={!canClear || isSending}
            className="hidden cursor-pointer md:inline-flex"
          >
            Clear
          </Button>
        </div>
      </div>

      {selectedAgent ? (
        <div className="mx-auto mt-2 flex max-w-5xl flex-wrap items-center gap-2 overflow-hidden text-xs text-muted-foreground">
          <span className="shrink-0 font-medium text-foreground">
            {selectedAgent.name}
          </span>
          <span>•</span>
          <span
            className={
              modelStatus.configured
                ? "max-w-[24rem] truncate text-success"
                : "shrink-0 text-danger"
            }
          >
            {modelStatus.loading
              ? "Loading model assignment…"
              : modelStatus.configured
                ? `${modelStatus.providerName ?? modelStatus.providerId} · ${modelStatus.model}`
                : "Model required"}
          </span>
          <span>•</span>
          <span className="shrink-0">
            {settings.ragMode === "default"
              ? `RAG ${selectedAgent.use_rag ? "on" : "off"} (default)`
              : `RAG ${settings.ragMode} (override)`}
          </span>
          <span>•</span>
          <span className="truncate">
            {settings.toolsMode === "disabled"
              ? "Tools disabled"
              : selectedAgent.tools.length
                ? `${selectedAgent.tools.length} tools available`
                : "No tools"}
          </span>
          {recommendationReason ? (
            <>
              <span>•</span>
              <span className="truncate text-success">
                {recommendationReason}
              </span>
            </>
          ) : null}
        </div>
      ) : null}
    </header>
  );
}
