"use client";

import Link from "next/link";
import {
  BotIcon,
  ExternalLinkIcon,
  Loader2Icon,
  RefreshCwIcon,
  TriangleAlertIcon,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  discoverModels,
  getModelSettings,
  saveAgentModel,
  type AgentModelSettings,
  type DiscoveredModel,
  type ModelProvider,
  type ModelSettingsSnapshot,
} from "@/features/model-settings/model-settings-api";

export type ChatModelSelectionStatus = {
  loading: boolean;
  configured: boolean;
  providerId: string | null;
  providerName: string | null;
  model: string | null;
};

type ModelOption = {
  key: string;
  providerId: string;
  providerName: string;
  providerIsCloud: boolean;
  model: string;
  availability: DiscoveredModel["availability"];
};

type Props = {
  agentId: string;
  disabled: boolean;
  hasConversation: boolean;
  onStatusChange: (status: ChatModelSelectionStatus) => void;
  onAssignmentChanged: (
    assignment: AgentModelSettings,
  ) => void | Promise<void>;
  onError: (message: string | null) => void;
};

const DEFAULT_GENERATION = {
  temperature: 0.1,
  max_tokens: 2048,
  context_window: 8192,
};

export function ChatModelSelector({
  agentId,
  disabled,
  hasConversation,
  onStatusChange,
  onAssignmentChanged,
  onError,
}: Props) {
  const [snapshot, setSnapshot] =
    useState<ModelSettingsSnapshot | null>(null);
  const [discovered, setDiscovered] =
    useState<Record<string, DiscoveredModel[]>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [discoveryWarning, setDiscoveryWarning] =
    useState<string | null>(null);

  const publishStatus = useCallback(
    (
      assignment: AgentModelSettings | undefined,
      isLoading: boolean,
    ) => {
      const model = assignment?.model?.trim() ?? "";
      onStatusChange({
        loading: isLoading,
        configured: Boolean(model),
        providerId: assignment?.provider_id ?? null,
        providerName: assignment?.provider?.name ?? null,
        model: model || null,
      });
    },
    [onStatusChange],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setDiscoveryWarning(null);
    onError(null);
    publishStatus(undefined, true);

    try {
      const nextSnapshot = await getModelSettings();
      const assignment = nextSnapshot.agents[agentId];

      setSnapshot(nextSnapshot);
      publishStatus(assignment, false);

      const results = await Promise.allSettled(
        nextSnapshot.providers.map(async (provider) => ({
          provider,
          result: await discoverModels(provider.id),
        })),
      );

      const nextDiscovered: Record<string, DiscoveredModel[]> = {};
      const failedProviders: string[] = [];

      results.forEach((result, index) => {
        const provider = nextSnapshot.providers[index];
        if (result.status === "fulfilled") {
          nextDiscovered[provider.id] = result.value.result.models;
        } else {
          failedProviders.push(provider.name);
        }
      });

      setDiscovered(nextDiscovered);
      if (failedProviders.length > 0) {
        setDiscoveryWarning(
          `Could not refresh ${failedProviders.join(", ")}. The current assignment is still available.`,
        );
      }
    } catch (error) {
      setSnapshot(null);
      setDiscovered({});
      publishStatus(undefined, false);
      onError(
        error instanceof Error
          ? error.message
          : "Could not load model assignments.",
      );
    } finally {
      setLoading(false);
    }
  }, [agentId, onError, publishStatus]);

  useEffect(() => {
    void load();
  }, [load]);

  const assignment = snapshot?.agents[agentId];
  const options = useMemo(
    () => buildOptions(snapshot, discovered, agentId),
    [agentId, discovered, snapshot],
  );
  const selectedValue =
    assignment?.model?.trim()
      ? encodeModelKey(
          assignment.provider_id,
          assignment.model.trim(),
        )
      : undefined;

  const selectModel = async (value: string) => {
    if (!snapshot || saving) return;

    const selected = options.find((option) => option.key === value);
    if (!selected) return;

    if (
      hasConversation &&
      !window.confirm(
        "Changing the model starts a new conversation so messages are not mixed across runtimes. Continue?",
      )
    ) {
      return;
    }

    const provider = snapshot.providers.find(
      (item) => item.id === selected.providerId,
    );
    if (!provider) {
      onError("The selected model provider no longer exists.");
      return;
    }

    setSaving(true);
    onError(null);

    try {
      const saved = await saveAgentModel(agentId, {
        provider_id: selected.providerId,
        model: selected.model,
        generation:
          assignment?.generation ?? DEFAULT_GENERATION,
      });

      setSnapshot((current) =>
        current
          ? {
              ...current,
              agents: {
                ...current.agents,
                [agentId]: saved,
              },
            }
          : current,
      );
      publishStatus(saved, false);
      await onAssignmentChanged(saved);
    } catch (error) {
      onError(
        error instanceof Error
          ? error.message
          : "Could not save the model assignment.",
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex min-w-0 items-center gap-1.5">
      <Select
        value={selectedValue}
        onValueChange={(value) => void selectModel(value)}
        disabled={disabled || loading || saving || options.length === 0}
      >
        <SelectTrigger
          className="w-[190px] cursor-pointer sm:w-[250px]"
          aria-label="Model used by selected agent"
          title={
            assignment?.model
              ? `${assignment.provider.name} · ${assignment.model}`
              : "Select a model for this agent"
          }
        >
          {loading || saving ? (
            <span className="flex min-w-0 items-center gap-2">
              <Loader2Icon className="size-3.5 shrink-0 animate-spin" />
              <span className="truncate">
                {saving ? "Saving model…" : "Loading models…"}
              </span>
            </span>
          ) : (
            <SelectValue placeholder="Select agent model" />
          )}
        </SelectTrigger>
        <SelectContent>
          {groupOptions(options).map((group) => (
            <SelectGroup key={group.provider.id}>
              <SelectLabel>
                {group.provider.name}
                {group.provider.is_cloud ? " · cloud" : ""}
              </SelectLabel>
              {group.options.map((option) => (
                <SelectItem
                  key={option.key}
                  value={option.key}
                  className="cursor-pointer"
                >
                  <span className="flex min-w-0 items-center gap-2">
                    <BotIcon className="size-3.5 shrink-0 opacity-60" />
                    <span className="truncate">{option.model}</span>
                    {option.availability === "cloud" ? (
                      <span className="text-[9px] uppercase text-sky-600 dark:text-sky-400">
                        cloud
                      </span>
                    ) : null}
                  </span>
                </SelectItem>
              ))}
            </SelectGroup>
          ))}
        </SelectContent>
      </Select>

      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="size-9 cursor-pointer"
        onClick={() => void load()}
        disabled={disabled || loading || saving}
        title="Refresh available models"
        aria-label="Refresh available models"
      >
        <RefreshCwIcon
          className={`size-3.5 ${loading ? "animate-spin" : ""}`}
        />
      </Button>

      <Button
        asChild
        variant="ghost"
        size="icon"
        className="size-9 cursor-pointer"
        title="Open Models page"
      >
        <Link href="/models" aria-label="Open Models page">
          <ExternalLinkIcon className="size-3.5" />
        </Link>
      </Button>

      {discoveryWarning ? (
        <span
          className="hidden text-pending xl:inline-flex"
          title={discoveryWarning}
          aria-label={discoveryWarning}
        >
          <TriangleAlertIcon className="size-3.5" />
        </span>
      ) : null}
    </div>
  );
}

function buildOptions(
  snapshot: ModelSettingsSnapshot | null,
  discovered: Record<string, DiscoveredModel[]>,
  agentId: string,
): ModelOption[] {
  if (!snapshot) return [];

  const assignment = snapshot.agents[agentId];
  const options = new Map<string, ModelOption>();

  for (const provider of snapshot.providers) {
    for (const model of discovered[provider.id] ?? []) {
      const cleanModel = model.name.trim();
      if (!cleanModel || model.ready === false) continue;

      const key = encodeModelKey(provider.id, cleanModel);
      options.set(key, {
        key,
        providerId: provider.id,
        providerName: provider.name,
        providerIsCloud: Boolean(provider.is_cloud),
        model: cleanModel,
        availability: model.availability,
      });
    }
  }

  if (assignment?.model?.trim()) {
    const key = encodeModelKey(
      assignment.provider_id,
      assignment.model.trim(),
    );
    if (!options.has(key)) {
      options.set(key, {
        key,
        providerId: assignment.provider_id,
        providerName: assignment.provider.name,
        providerIsCloud: Boolean(assignment.provider.is_cloud),
        model: assignment.model.trim(),
        availability: assignment.provider.is_cloud
          ? "cloud"
          : assignment.provider.kind === "ollama"
            ? "local"
            : "remote",
      });
    }
  }

  return Array.from(options.values()).sort((left, right) => {
    const providerComparison = left.providerName.localeCompare(
      right.providerName,
    );
    return providerComparison || left.model.localeCompare(right.model);
  });
}

function groupOptions(options: ModelOption[]): Array<{
  provider: ModelProvider;
  options: ModelOption[];
}> {
  const grouped = new Map<
    string,
    { provider: ModelProvider; options: ModelOption[] }
  >();

  for (const option of options) {
    const existing = grouped.get(option.providerId);
    if (existing) {
      existing.options.push(option);
      continue;
    }

    grouped.set(option.providerId, {
      provider: {
        id: option.providerId,
        name: option.providerName,
        kind:
          option.availability === "remote"
            ? "openai_compatible"
            : "ollama",
        base_url: "",
        built_in: false,
        api_key_configured: false,
        is_cloud: option.providerIsCloud,
      },
      options: [option],
    });
  }

  return Array.from(grouped.values());
}

function encodeModelKey(
  providerId: string,
  model: string,
): string {
  return `${encodeURIComponent(providerId)}::${encodeURIComponent(model)}`;
}
