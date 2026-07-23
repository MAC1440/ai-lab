"use client";

import { Loader2Icon, RotateCcwIcon, SaveIcon } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  deleteTaskStageModel,
  discoverModels,
  type AgentModelSettings,
  type DiscoveredModel,
  type ModelSettingsSnapshot,
  saveTaskStageModel,
  type TaskStage,
} from "@/features/model-settings/model-settings-api";

const STAGES: Array<{
  id: TaskStage;
  name: string;
  description: string;
}> = [
  {
    id: "planning",
    name: "Planning",
    description: "Chooses exact files and operation types.",
  },
  {
    id: "generation",
    name: "Generation",
    description: "Writes the complete typed multi-file change set.",
  },
  {
    id: "repair",
    name: "Repair",
    description: "Produces bounded fixes from verification output.",
  },
];

function StageCard({
  stage,
  agentId,
  snapshot,
  disabled,
  portalContainer,
  onChanged,
}: {
  stage: (typeof STAGES)[number];
  agentId: string;
  snapshot: ModelSettingsSnapshot;
  disabled: boolean;
  portalContainer: HTMLElement | null;
  onChanged: () => Promise<void>;
}) {
  const inherited = snapshot.agents[agentId];
  const override = snapshot.task_stages[agentId]?.[stage.id];
  const resolved = override ?? inherited;
  const [draft, setDraft] = useState<AgentModelSettings>(resolved);
  const [models, setModels] = useState<DiscoveredModel[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void discoverModels(draft.provider_id)
      .then((result) => {
        if (active) setModels(result.models);
      })
      .catch(() => {
        if (active) setModels([]);
      });
    return () => {
      active = false;
    };
  }, [draft.provider_id]);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      await onChanged();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Stage assignment failed.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="rounded-lg border border-zinc-800 p-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-medium">{stage.name}</p>
          <p className="mt-1 text-xs text-zinc-500">{stage.description}</p>
        </div>
        <Badge variant="outline">{override ? "override" : "agent default"}</Badge>
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label>Provider</Label>
          <Select
            value={draft.provider_id}
            disabled={disabled || busy}
            onValueChange={(providerId) => {
              const provider = snapshot.providers.find(
                (item) => item.id === providerId,
              );
              if (!provider) return;
              setDraft((current) => ({
                ...current,
                provider_id: providerId,
                model: "",
                provider,
              }));
            }}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent portalContainer={portalContainer}>
              {snapshot.providers.map((provider) => (
                <SelectItem key={provider.id} value={provider.id}>
                  {provider.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Model</Label>
          <Select
            value={draft.model}
            disabled={disabled || busy || models.length === 0}
            onValueChange={(model) =>
              setDraft((current) => ({ ...current, model }))
            }
          >
            <SelectTrigger>
              <SelectValue
                placeholder={
                  models.length ? "Select model" : "No discovered models"
                }
              />
            </SelectTrigger>
            <SelectContent portalContainer={portalContainer}>
              {models.map((model) => (
                <SelectItem key={model.name} value={model.name}>
                  {model.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      {error ? <p className="mt-2 text-xs text-red-300">{error}</p> : null}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          size="sm"
          disabled={disabled || busy || !draft.model}
          onClick={() =>
            void run(async () => {
              await saveTaskStageModel(agentId, stage.id, {
                provider_id: draft.provider_id,
                model: draft.model,
                generation: draft.generation,
              });
            })
          }
        >
          {busy ? (
            <Loader2Icon className="size-3.5 animate-spin" />
          ) : (
            <SaveIcon className="size-3.5" />
          )}
          Save {stage.name.toLowerCase()} model
        </Button>
        {override ? (
          <Button
            size="sm"
            variant="outline"
            disabled={disabled || busy}
            onClick={() =>
              void run(() => deleteTaskStageModel(agentId, stage.id))
            }
          >
            <RotateCcwIcon className="size-3.5" />
            Use agent default
          </Button>
        ) : null}
      </div>
    </article>
  );
}

export function ModelStageSettings({
  agentId,
  snapshot,
  disabled,
  portalContainer,
  onChanged,
}: {
  agentId: string;
  snapshot: ModelSettingsSnapshot;
  disabled: boolean;
  portalContainer: HTMLElement | null;
  onChanged: () => Promise<void>;
}) {
  return (
    <section className="space-y-3 border-t border-zinc-800 pt-4">
      <div>
        <h3 className="text-sm font-semibold">Task-stage model routing</h3>
        <p className="mt-1 text-xs leading-5 text-zinc-500">
          Assign different installed models to planning, code generation, and
          repair. Unset stages inherit the agent model above.
        </p>
      </div>
      {STAGES.map((stage) => (
        <StageCard
          key={[
            agentId,
            stage.id,
            snapshot.task_stages[agentId]?.[stage.id]?.provider_id ?? "default",
            snapshot.task_stages[agentId]?.[stage.id]?.model ??
              snapshot.agents[agentId]?.model ??
              "",
          ].join(":")}
          stage={stage}
          agentId={agentId}
          snapshot={snapshot}
          disabled={disabled}
          portalContainer={portalContainer}
          onChanged={onChanged}
        />
      ))}
    </section>
  );
}
