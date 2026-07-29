"use client";

import {
  ChevronDownIcon,
  Loader2Icon,
  SlidersHorizontalIcon,
  TriangleAlertIcon,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { type AgentProfile, getAgents } from "@/features/agents/agent-api";
import { KnowledgeSourcesDialog } from "@/features/knowledge-sources";
import { MCPSettingsDialog } from "@/features/mcp";
import { ModelSettingsDialog } from "@/features/model-settings";
import { ModelBenchmarkDialog } from "@/features/model-settings/model-benchmark-dialog";
import { ProjectIndexDialog } from "@/features/project-index";
import { ProjectTaskDialog } from "@/features/project-tasks";
import { RepairDialog } from "@/features/repairs";
import { ReliabilityBenchmarkDialog } from "@/features/reliability";
import { RuntimeSettingsDialog } from "@/features/runtime";
import { ScaffoldDialog } from "@/features/scaffolds";
import { SystemDialog } from "@/features/system";
import { VerificationDialog } from "@/features/verification";
import { getActiveWorkspace } from "@/features/workspaces/workspace-api";
import { cn } from "@/lib/utils";

export function DrawerManagementSection({
  collapsed,
  onExpand,
}: {
  collapsed: boolean;
  onExpand: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [agents, setAgents] = useState<AgentProfile[]>([]);
  const [workspaceReady, setWorkspaceReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshContext = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [agentResult, workspaceResult] = await Promise.all([
        getAgents(),
        getActiveWorkspace(),
      ]);
      setAgents(agentResult);
      setWorkspaceReady(Boolean(workspaceResult.workspace));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not load management context.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) void refreshContext();
  }, [open, refreshContext]);

  const toggle = () => {
    if (collapsed) {
      onExpand();
      setOpen(true);
      return;
    }
    setOpen((current) => !current);
  };

  return (
    <section className="mt-3 border-t border-border pt-3">
      <button
        type="button"
        onClick={toggle}
        className={cn(
          "flex w-full cursor-pointer items-center rounded-xl px-3 py-2.5 text-left text-muted-foreground transition hover:bg-surface-hover hover:text-foreground",
          collapsed ? "justify-center" : "gap-3",
          open && !collapsed && "bg-surface-hover text-foreground",
        )}
        aria-expanded={open}
        title={collapsed ? "Manage application" : undefined}
      >
        <SlidersHorizontalIcon className="size-4 shrink-0 text-accent" />
        {!collapsed ? (
          <>
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-medium">Manage</span>
              <span className="block truncate text-[10px] text-muted-foreground">
                Models, tools, runtime, and system
              </span>
            </span>
            {loading ? (
              <Loader2Icon className="size-3.5 animate-spin" />
            ) : (
              <ChevronDownIcon
                className={cn(
                  "size-3.5 transition-transform",
                  open && "rotate-180",
                )}
              />
            )}
          </>
        ) : null}
      </button>

      {open && !collapsed ? (
        <div className="mt-2 space-y-2 rounded-xl border border-border bg-surface-hover/45 p-2">
          {error ? (
            <div className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger/10 p-2 text-[10px] text-danger">
              <TriangleAlertIcon className="mt-0.5 size-3 shrink-0" />
              <span>{error}</span>
            </div>
          ) : null}

          <p className="px-1 text-[9px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            Workspace
          </p>
          <div className="grid gap-1.5">
            <ProjectTaskDialog disabled={!workspaceReady || loading} />
            <ProjectIndexDialog disabled={!workspaceReady || loading} />
            <VerificationDialog disabled={!workspaceReady || loading} />
            <RepairDialog disabled={!workspaceReady || loading} />
            <ScaffoldDialog disabled={!workspaceReady || loading} />
          </div>

          <div className="border-t border-border" />
          <p className="px-1 text-[9px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            Models and integrations
          </p>
          <div className="grid gap-1.5">
            <ModelSettingsDialog
              agents={agents}
              disabled={loading}
              onSaved={refreshContext}
            />
            <RuntimeSettingsDialog />
            <ModelBenchmarkDialog
              agents={agents}
              disabled={loading}
            />
            <ReliabilityBenchmarkDialog disabled={loading} />
            <MCPSettingsDialog
              agents={agents}
              disabled={loading}
            />
            <KnowledgeSourcesDialog disabled={loading} />
            <SystemDialog disabled={loading} />
          </div>
        </div>
      ) : null}
    </section>
  );
}
