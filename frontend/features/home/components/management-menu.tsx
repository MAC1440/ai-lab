"use client";

import { SlidersHorizontalIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { KnowledgeSourcesDialog } from "@/features/knowledge-sources";
import { MCPSettingsDialog } from "@/features/mcp";
import { ModelSettingsDialog } from "@/features/model-settings";
import { ModelBenchmarkDialog } from "@/features/model-settings/model-benchmark-dialog";
import { ProjectTaskDialog } from "@/features/project-tasks";
import { RepairDialog } from "@/features/repairs";
import { ScaffoldDialog } from "@/features/scaffolds";
import { SystemDialog } from "@/features/system";
import { VerificationDialog } from "@/features/verification";
import { type AgentProfile } from "@/features/agents/agent-api";

export function ManagementMenu({ agents, disabled, workspaceReady, onAgentsChanged }: {
    agents: AgentProfile[];
    disabled: boolean;
    workspaceReady: boolean;
    onAgentsChanged: () => Promise<void>;
}) {
    return <Popover>
        <PopoverTrigger asChild><Button type="button" variant="ghost" size="sm"><SlidersHorizontalIcon className="mr-2 size-4" />Manage</Button></PopoverTrigger>
        <PopoverContent align="end" className="w-[320px] p-3">
            <p className="mb-3 text-xs font-medium uppercase tracking-wide text-zinc-500">Workspace and application tools</p>
            <div className="grid grid-cols-2 gap-2">
                <ProjectTaskDialog disabled={!workspaceReady || disabled} />
                <VerificationDialog disabled={!workspaceReady || disabled} />
                <RepairDialog disabled={!workspaceReady || disabled} />
                <ScaffoldDialog disabled={!workspaceReady || disabled} />
                <ModelSettingsDialog agents={agents} disabled={disabled} onSaved={onAgentsChanged} />
                <ModelBenchmarkDialog agents={agents} disabled={disabled} />
                <MCPSettingsDialog agents={agents} disabled={disabled} />
                <SystemDialog disabled={disabled} />
                <KnowledgeSourcesDialog disabled={disabled} />
            </div>
        </PopoverContent>
    </Popover>;
}
