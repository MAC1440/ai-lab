"use client";

import { useCallback, useEffect, useState } from "react";
import {
  BotIcon,
  CheckCircle2Icon,
  CpuIcon,
  GaugeIcon,
  HardDriveIcon,
  MemoryStickIcon,
  RefreshCwIcon,
  SaveIcon,
  ShieldAlertIcon,
  SparklesIcon,
  TriangleAlertIcon,
  WandSparklesIcon,
} from "lucide-react";

import {
  getModelSettings,
  saveAgentModel,
  saveTaskStageModel,
  type AgentModelSettings,
  type DiscoveredModel,
  type ModelProvider,
  type ModelSettingsSnapshot,
  type TaskStage,
} from "@/features/model-settings/model-settings-api";
import { ModelLibraryPanel } from "@/features/model-settings/model-library-panel";
import {
  getModelCapabilities,
  getModelRecommendations,
  type ModelCapabilityProfile,
  type ModelRecommendations,
} from "@/features/model-settings/model-workspace-api";
import {
  autoConfigureRuntime,
  getHardwareSnapshot,
  getRuntimeSettings,
  saveRuntimeSettings,
  type HardwareSnapshot,
  type RuntimeSettings,
  type RuntimeStageSettings,
} from "@/features/runtime/runtime-api";
import { cn } from "@/lib/utils";

type AgentId = "general" | "coding" | "unity" | "web";
type RuntimeStage = "chat" | TaskStage;

const agentLabels: Record<AgentId, string> = {
  general: "General",
  coding: "Coding",
  unity: "Unity",
  web: "Web",
};

const stageLabels: Record<RuntimeStage, string> = {
  chat: "Chat",
  planning: "Planning",
  generation: "Generation",
  repair: "Repair",
};

export function ModelsRuntimeWorkspace() {
  const [modelSettings, setModelSettings] =
    useState<ModelSettingsSnapshot | null>(null);
  const [hardware, setHardware] = useState<HardwareSnapshot | null>(null);
  const [runtime, setRuntime] = useState<RuntimeSettings | null>(null);
  const [profiles, setProfiles] = useState<ModelCapabilityProfile[]>([]);
  const [recommendations, setRecommendations] =
    useState<ModelRecommendations | null>(null);
  const [discovered, setDiscovered] =
    useState<Record<string, DiscoveredModel[]>>({});
  const [loading, setLoading] = useState(true);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadWorkspace = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [
        modelResult,
        hardwareResult,
        runtimeResult,
        capabilityResult,
        recommendationResult,
      ] = await Promise.all([
        getModelSettings(),
        getHardwareSnapshot(),
        getRuntimeSettings(),
        getModelCapabilities(),
        getModelRecommendations(),
      ]);

      setModelSettings(modelResult);
      setHardware(hardwareResult);
      setRuntime(runtimeResult);
      setProfiles(capabilityResult.profiles);
      setRecommendations(recommendationResult);
    } catch (loadError) {
      setError(toMessage(loadError, "Unable to load model workspace."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadWorkspace(), 0);
    return () => window.clearTimeout(timer);
  }, [loadWorkspace]);

  const saveAgentAssignment = async (
    agentId: AgentId,
    assignment: AgentModelSettings,
  ) => {
    const key = `agent:${agentId}`;
    setBusyKey(key);
    setError(null);
    setNotice(null);

    try {
      await saveAgentModel(agentId, {
        provider_id: assignment.provider_id,
        model: assignment.model,
        generation: assignment.generation,
        assignment_source: assignment.assignment_source,
      });
      setNotice(`${agentLabels[agentId]} agent assignment saved.`);
      await loadWorkspace();
    } catch (saveError) {
      setError(toMessage(saveError, "Unable to save agent assignment."));
    } finally {
      setBusyKey(null);
    }
  };

  const saveStageAssignment = async (
    agentId: AgentId,
    stage: TaskStage,
    assignment: AgentModelSettings,
  ) => {
    const key = `stage:${agentId}:${stage}`;
    setBusyKey(key);
    setError(null);
    setNotice(null);

    try {
      await saveTaskStageModel(agentId, stage, {
        provider_id: assignment.provider_id,
        model: assignment.model,
        generation: assignment.generation,
      });
      setNotice(
        `${agentLabels[agentId]} ${stageLabels[stage].toLowerCase()} assignment saved.`,
      );
      await loadWorkspace();
    } catch (saveError) {
      setError(toMessage(saveError, "Unable to save stage assignment."));
    } finally {
      setBusyKey(null);
    }
  };

  const autoConfigure = async () => {
    setBusyKey("runtime:auto");
    setError(null);
    setNotice(null);

    try {
      const result = await autoConfigureRuntime();
      setRuntime(result);
      setNotice(
        `Runtime settings updated for a ${result.chat.num_ctx.toLocaleString(
          "en-US",
        )}-token context window.`,
      );
    } catch (autoError) {
      setError(toMessage(autoError, "Automatic configuration failed."));
    } finally {
      setBusyKey(null);
    }
  };

  const saveRuntime = async () => {
    if (!runtime) return;

    setBusyKey("runtime:save");
    setError(null);
    setNotice(null);

    try {
      const result = await saveRuntimeSettings(runtime);
      setRuntime(result);
      setNotice("Runtime stage settings saved.");
    } catch (saveError) {
      setError(toMessage(saveError, "Unable to save runtime settings."));
    } finally {
      setBusyKey(null);
    }
  };

  return (
    <section className="ai-lab-scrollbar flex min-h-0 flex-1 flex-col overflow-y-auto">
      <div className="mx-auto w-full max-w-7xl space-y-6 p-4 sm:p-6">
        <WorkspaceHeader
          loading={loading}
          busy={busyKey !== null}
          onRefresh={() => void loadWorkspace()}
        />

        {error ? (
          <MessageBanner
            tone="error"
            icon={TriangleAlertIcon}
            title="Model workspace error"
            message={error}
          />
        ) : null}

        {notice ? (
          <MessageBanner
            tone="success"
            icon={CheckCircle2Icon}
            title="Saved"
            message={notice}
          />
        ) : null}

        <HardwareOverview hardware={hardware} loading={loading} />

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
          <div className="min-w-0 space-y-6">
            <ProviderSection
              providers={modelSettings?.providers ?? []}
              discovered={discovered}
              hardware={hardware}
              profiles={profiles}
              loading={loading}
              onDiscovered={(providerId, models) =>
                setDiscovered((current) => ({
                  ...current,
                  [providerId]: models,
                }))
              }
              onNotice={setNotice}
              onError={setError}
              onWorkspaceRefresh={loadWorkspace}
            />

            <AssignmentSection
              snapshot={modelSettings}
              discovered={discovered}
              profiles={profiles}
              recommendations={recommendations}
              busyKey={busyKey}
              loading={loading}
              onSaveAgent={saveAgentAssignment}
              onSaveStage={saveStageAssignment}
            />
          </div>

          <aside className="space-y-6">
            <RuntimeSection
              runtime={runtime}
              hardware={hardware}
              busyKey={busyKey}
              loading={loading}
              onChange={setRuntime}
              onAutoConfigure={autoConfigure}
              onSave={saveRuntime}
            />

            <RecommendationsCard recommendations={recommendations} />
          </aside>
        </div>
      </div>
    </section>
  );
}

function WorkspaceHeader({
  loading,
  busy,
  onRefresh,
}: {
  loading: boolean;
  busy: boolean;
  onRefresh: () => void;
}) {
  return (
    <header className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-success dark:text-success">
          Model control plane
        </p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight text-foreground dark:text-foreground">
          Models and runtime
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground dark:text-muted-foreground">
          Browse local and cloud models, pull or register them with live
          progress, assign each agent explicitly, and tune runtime limits.
        </p>
      </div>

      <button
        type="button"
        onClick={onRefresh}
        disabled={loading || busy}
        className="inline-flex w-fit items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-xs font-medium text-foreground shadow-sm transition hover:bg-surface-hover disabled:opacity-50 dark:border-border dark:bg-surface-raised dark:text-foreground dark:hover:bg-surface-hover"
      >
        <RefreshCwIcon
          className={cn("size-3.5", loading && "animate-spin")}
        />
        Refresh workspace
      </button>
    </header>
  );
}

function HardwareOverview({
  hardware,
  loading,
}: {
  hardware: HardwareSnapshot | null;
  loading: boolean;
}) {
  const memoryGb = bytesToGb(hardware?.memory.total_bytes);
  const availableGb = bytesToGb(hardware?.memory.available_bytes);
  const gpuMemoryGb = bytesToGb(hardware?.gpu?.memory_total_bytes);

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <OverviewCard
        icon={CpuIcon}
        label="CPU"
        value={
          loading
            ? "Loading…"
            : `${hardware?.cpu.logical_cores ?? "—"} logical cores`
        }
        detail={hardware?.platform.processor || hardware?.platform.machine || "Unknown processor"}
      />
      <OverviewCard
        icon={MemoryStickIcon}
        label="System memory"
        value={loading ? "Loading…" : formatGb(memoryGb)}
        detail={`${formatGb(availableGb)} currently available`}
      />
      <OverviewCard
        icon={CpuIcon}
        label="GPU"
        value={loading ? "Loading…" : hardware?.gpu?.name || "Not detected"}
        detail={
          hardware?.gpu
            ? `${formatGb(gpuMemoryGb)} total VRAM`
            : "CPU-only inference remains available"
        }
      />
      <OverviewCard
        icon={GaugeIcon}
        label="Recommended context"
        value={
          loading
            ? "Loading…"
            : formatInteger(
                hardware?.recommendation.recommended_context_window,
              )
        }
        detail={`${hardware?.recommendation.recommended_parallel_requests ?? "—"} recommended parallel request`}
      />
    </div>
  );
}

function OverviewCard({
  icon: Icon,
  label,
  value,
  detail,
}: {
  icon: typeof CpuIcon;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-4 shadow-sm dark:border-border dark:bg-surface-raised">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-muted-foreground dark:text-muted-foreground">
          {label}
        </p>
        <div className="flex size-8 items-center justify-center rounded-lg bg-success/10 text-success dark:text-success">
          <Icon className="size-4" />
        </div>
      </div>
      <p className="mt-4 truncate text-base font-semibold text-foreground dark:text-foreground">
        {value}
      </p>
      <p className="mt-1 truncate text-[11px] text-muted-foreground">{detail}</p>
    </div>
  );
}

function ProviderSection({
  providers,
  discovered,
  hardware,
  profiles,
  loading,
  onDiscovered,
  onNotice,
  onError,
  onWorkspaceRefresh,
}: {
  providers: ModelProvider[];
  discovered: Record<string, DiscoveredModel[]>;
  hardware: HardwareSnapshot | null;
  profiles: ModelCapabilityProfile[];
  loading: boolean;
  onDiscovered: (
    providerId: string,
    models: DiscoveredModel[],
  ) => void;
  onNotice: (message: string | null) => void;
  onError: (message: string | null) => void;
  onWorkspaceRefresh: () => Promise<void>;
}) {
  return (
    <ModelLibraryPanel
      providers={providers}
      discovered={discovered}
      hardware={hardware}
      profiles={profiles}
      loading={loading}
      onDiscovered={onDiscovered}
      onNotice={onNotice}
      onError={onError}
      onWorkspaceRefresh={onWorkspaceRefresh}
    />
  );
}

function AssignmentSection({
  snapshot,
  discovered,
  profiles,
  recommendations,
  busyKey,
  loading,
  onSaveAgent,
  onSaveStage,
}: {
  snapshot: ModelSettingsSnapshot | null;
  discovered: Record<string, DiscoveredModel[]>;
  profiles: ModelCapabilityProfile[];
  recommendations: ModelRecommendations | null;
  busyKey: string | null;
  loading: boolean;
  onSaveAgent: (
    agentId: AgentId,
    assignment: AgentModelSettings,
  ) => Promise<void>;
  onSaveStage: (
    agentId: AgentId,
    stage: TaskStage,
    assignment: AgentModelSettings,
  ) => Promise<void>;
}) {
  if (loading) {
    return (
      <div className="rounded-2xl border border-border bg-surface p-8 text-center text-xs text-muted-foreground shadow-sm dark:border-border dark:bg-surface-raised">
        Loading model assignments…
      </div>
    );
  }

  if (!snapshot) return null;

  const agents = Object.keys(snapshot.agents) as AgentId[];

  return (
    <div className="rounded-2xl border border-border bg-surface shadow-sm dark:border-border dark:bg-surface-raised">
      <div className="border-b border-border p-4 sm:p-5 dark:border-border">
        <h3 className="text-sm font-semibold text-foreground dark:text-foreground">
          Agent and task-stage assignments
        </h3>
        <p className="mt-1 text-xs text-muted-foreground dark:text-muted-foreground">
          The base agent model handles chat. Optional stage overrides handle
          planning, file generation, and repair.
        </p>
      </div>

      <div className="divide-y divide-border dark:divide-border">
        {agents.map((agentId) => (
          <AgentAssignments
            key={agentId}
            agentId={agentId}
            snapshot={snapshot}
            discovered={discovered}
            profiles={profiles}
            recommendations={recommendations}
            busyKey={busyKey}
            onSaveAgent={onSaveAgent}
            onSaveStage={onSaveStage}
          />
        ))}
      </div>
    </div>
  );
}

function AgentAssignments({
  agentId,
  snapshot,
  discovered,
  profiles,
  recommendations,
  busyKey,
  onSaveAgent,
  onSaveStage,
}: {
  agentId: AgentId;
  snapshot: ModelSettingsSnapshot;
  discovered: Record<string, DiscoveredModel[]>;
  profiles: ModelCapabilityProfile[];
  recommendations: ModelRecommendations | null;
  busyKey: string | null;
  onSaveAgent: (
    agentId: AgentId,
    assignment: AgentModelSettings,
  ) => Promise<void>;
  onSaveStage: (
    agentId: AgentId,
    stage: TaskStage,
    assignment: AgentModelSettings,
  ) => Promise<void>;
}) {
  const base = snapshot.agents[agentId];
  const stages = snapshot.task_stages[agentId] ?? {};

  return (
    <div className="p-4 sm:p-5">
      <div className="flex items-center gap-3">
        <div className="flex size-9 items-center justify-center rounded-xl bg-success/10 text-success dark:text-success">
          <BotIcon className="size-4" />
        </div>
        <div>
          <h4 className="text-sm font-semibold text-foreground dark:text-foreground">
            {agentLabels[agentId]} agent
          </h4>
          <p className="text-[11px] text-muted-foreground">
            Base chat model and optional task-stage overrides
          </p>
        </div>
      </div>

      <div className="mt-4 grid gap-3 xl:grid-cols-2">
        <AssignmentEditor
          key={`base:${base.provider_id}:${base.model}:${base.assignment_source ?? ""}`}
          title="Base chat assignment"
          assignment={base}
          providers={snapshot.providers}
          discovered={discovered}
          profiles={profiles}
          saving={busyKey === `agent:${agentId}`}
          onSave={(value) => onSaveAgent(agentId, value)}
        />

        {(["planning", "generation", "repair"] as TaskStage[]).map(
          (stage) => {
            const assignment = stages[stage] ?? base;

            return (
              <AssignmentEditor
              key={`${stage}:${assignment.provider_id}:${assignment.model}:${assignment.assignment_source ?? ""}`}
              title={`${stageLabels[stage]} override`}
              assignment={assignment}
              providers={snapshot.providers}
              discovered={discovered}
              profiles={profiles}
              recommendation={recommendations?.recommendations[stage]}
              saving={busyKey === `stage:${agentId}:${stage}`}
              onSave={(value) => onSaveStage(agentId, stage, value)}
            />
            );
          },
        )}
      </div>
    </div>
  );
}

function AssignmentEditor({
  title,
  assignment,
  providers,
  discovered,
  profiles,
  recommendation,
  saving,
  onSave,
}: {
  title: string;
  assignment: AgentModelSettings;
  providers: ModelProvider[];
  discovered: Record<string, DiscoveredModel[]>;
  profiles: ModelCapabilityProfile[];
  recommendation?: ModelRecommendations["recommendations"][TaskStage];
  saving: boolean;
  onSave: (assignment: AgentModelSettings) => Promise<void>;
}) {
  const [draft, setDraft] = useState<AgentModelSettings>(assignment);

  const provider = providers.find((item) => item.id === draft.provider_id)
    ?? assignment.provider;
  const providerModels = discovered[draft.provider_id]?.map((item) => item.name)
    ?? profiles
      .filter((item) => item.provider_id === draft.provider_id)
      .map((item) => item.model);
  const modelOptions = Array.from(
    new Set([draft.model, ...providerModels].filter(Boolean)),
  ).sort();

  const profile = profiles.find(
    (item) =>
      item.provider_id === draft.provider_id
      && item.model === draft.model,
  );

  return (
    <div className="rounded-xl border border-border bg-surface-hover/60 p-4 dark:border-border dark:bg-surface-raised/40">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h5 className="text-xs font-semibold text-foreground dark:text-foreground">
            {title}
          </h5>
          <p className="mt-1 text-[10px] text-muted-foreground">
            {draft.assignment_source
              ? `Resolved from ${draft.assignment_source}`
              : "Explicit assignment"}
          </p>
        </div>

        {recommendation ? (
          <button
            type="button"
            onClick={() =>
              setDraft((current) => ({
                ...current,
                provider_id: recommendation.provider_id,
                model: recommendation.model,
              }))
            }
            className="inline-flex items-center gap-1 rounded-lg bg-success/10 px-2 py-1 text-[10px] font-medium text-success dark:text-success"
            title={`Benchmark score ${recommendation.score.toFixed(2)}`}
          >
            <WandSparklesIcon className="size-3" />
            Use recommendation
          </button>
        ) : null}
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <Field label="Provider">
          <select
            value={draft.provider_id}
            onChange={(event) => {
              const nextProvider = providers.find(
                (item) => item.id === event.target.value,
              );
              setDraft((current) => ({
                ...current,
                provider_id: event.target.value,
                provider: nextProvider ?? current.provider,
              }));
            }}
            className={inputClass}
          >
            {providers.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Model">
          <input
            list={`models-${title.replaceAll(" ", "-")}`}
            value={draft.model}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                model: event.target.value,
              }))
            }
            className={inputClass}
          />
          <datalist id={`models-${title.replaceAll(" ", "-")}`}>
            {modelOptions.map((model) => (
              <option key={model} value={model} />
            ))}
          </datalist>
        </Field>

        <NumberField
          label="Context window"
          value={draft.generation.context_window}
          min={1024}
          step={1024}
          onChange={(value) =>
            setDraft((current) => ({
              ...current,
              generation: {
                ...current.generation,
                context_window: value,
              },
            }))
          }
        />

        <NumberField
          label="Max output tokens"
          value={draft.generation.max_tokens}
          min={128}
          step={128}
          onChange={(value) =>
            setDraft((current) => ({
              ...current,
              generation: {
                ...current.generation,
                max_tokens: value,
              },
            }))
          }
        />

        <NumberField
          label="Temperature"
          value={draft.generation.temperature}
          min={0}
          max={2}
          step={0.05}
          onChange={(value) =>
            setDraft((current) => ({
              ...current,
              generation: {
                ...current.generation,
                temperature: value,
              },
            }))
          }
        />
      </div>

      {profile ? (
        <p className="mt-3 text-[10px] text-muted-foreground">
          Saved capability: {formatInteger(profile.context_window)} context,
          {" "}
          {formatInteger(profile.max_output_tokens)} max output,
          {" "}
          {profile.measured_tokens_per_second == null
            ? "not benchmarked"
            : `${profile.measured_tokens_per_second.toFixed(2)} tok/s`}.
        </p>
      ) : (
        <p className="mt-3 flex items-start gap-1.5 text-[10px] text-pending dark:text-pending">
          <ShieldAlertIcon className="mt-0.5 size-3 shrink-0" />
          No saved capability profile exists. Conservative inferred limits will
          be used.
        </p>
      )}

      <button
        type="button"
        onClick={() => void onSave(draft)}
        disabled={saving || !draft.model.trim() || !provider}
        className="mt-4 inline-flex items-center gap-2 rounded-lg bg-surface-raised px-3 py-2 text-xs font-medium text-accent-foreground disabled:opacity-50 dark:bg-surface-hover dark:text-foreground"
      >
        <SaveIcon className="size-3.5" />
        {saving ? "Saving…" : "Save assignment"}
      </button>
    </div>
  );
}

function RuntimeSection({
  runtime,
  hardware,
  busyKey,
  loading,
  onChange,
  onAutoConfigure,
  onSave,
}: {
  runtime: RuntimeSettings | null;
  hardware: HardwareSnapshot | null;
  busyKey: string | null;
  loading: boolean;
  onChange: (runtime: RuntimeSettings) => void;
  onAutoConfigure: () => Promise<void>;
  onSave: () => Promise<void>;
}) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-4 shadow-sm dark:border-border dark:bg-surface-raised">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-foreground dark:text-foreground">
            Runtime limits
          </h3>
          <p className="mt-1 text-xs text-muted-foreground dark:text-muted-foreground">
            Global stage defaults are clamped by each model capability profile.
          </p>
        </div>
        <HardDriveIcon className="size-4 text-success" />
      </div>

      {loading || !runtime ? (
        <div className="py-8 text-center text-xs text-muted-foreground">
          Loading runtime settings…
        </div>
      ) : (
        <>
          <div className="mt-4 space-y-4">
            {(["chat", "planning", "generation", "repair"] as RuntimeStage[]).map(
              (stage) => (
                <RuntimeStageEditor
                  key={stage}
                  stage={stage}
                  value={runtime[stage]}
                  onChange={(value) =>
                    onChange({
                      ...runtime,
                      automatic: false,
                      [stage]: value,
                    })
                  }
                />
              ),
            )}
          </div>

          <div className="mt-4 rounded-xl border border-success/30 bg-success/10 p-3 text-[11px] leading-relaxed text-success dark:border-success/30 dark:bg-success/10 dark:text-success">
            Hardware recommendation:{" "}
            {formatInteger(
              hardware?.recommendation.recommended_context_window,
            )}{" "}
            context tokens and{" "}
            {hardware?.recommendation.recommended_parallel_requests ?? "—"}{" "}
            parallel request.
          </div>

          <div className="mt-4 grid gap-2">
            <button
              type="button"
              onClick={() => void onAutoConfigure()}
              disabled={busyKey !== null}
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-xs font-medium text-success hover:bg-success/10 disabled:opacity-50 dark:border-success/30 dark:bg-success/10 dark:text-success"
            >
              <SparklesIcon className="size-3.5" />
              {busyKey === "runtime:auto"
                ? "Configuring…"
                : "Apply hardware recommendation"}
            </button>

            <button
              type="button"
              onClick={() => void onSave()}
              disabled={busyKey !== null}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-surface-raised px-3 py-2 text-xs font-medium text-accent-foreground disabled:opacity-50 dark:bg-surface-hover dark:text-foreground"
            >
              <SaveIcon className="size-3.5" />
              {busyKey === "runtime:save" ? "Saving…" : "Save runtime settings"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function RuntimeStageEditor({
  stage,
  value,
  onChange,
}: {
  stage: RuntimeStage;
  value: RuntimeStageSettings;
  onChange: (value: RuntimeStageSettings) => void;
}) {
  return (
    <details className="rounded-xl border border-border bg-surface-hover/60 p-3 open:bg-surface dark:border-border dark:bg-surface-raised/40 dark:open:bg-surface-raised">
      <summary className="cursor-pointer select-none text-xs font-semibold text-foreground dark:text-foreground">
        {stageLabels[stage]}
        <span className="ml-2 font-normal text-muted-foreground">
          {formatInteger(value.num_ctx)} ctx ·{" "}
          {formatInteger(value.max_tokens)} output
        </span>
      </summary>

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <NumberField
          label="Context"
          value={value.num_ctx}
          min={1024}
          step={1024}
          onChange={(next) => onChange({ ...value, num_ctx: next })}
        />
        <NumberField
          label="Max output"
          value={value.max_tokens}
          min={128}
          step={128}
          onChange={(next) => onChange({ ...value, max_tokens: next })}
        />
        <NumberField
          label="Reserve"
          value={value.reserve_tokens}
          min={0}
          step={128}
          onChange={(next) => onChange({ ...value, reserve_tokens: next })}
        />
        <NumberField
          label="Temperature"
          value={value.temperature}
          min={0}
          max={2}
          step={0.05}
          onChange={(next) => onChange({ ...value, temperature: next })}
        />
      </div>
    </details>
  );
}

function RecommendationsCard({
  recommendations,
}: {
  recommendations: ModelRecommendations | null;
}) {
  return (
    <div className="rounded-2xl border border-border bg-surface-raised p-4 text-foreground shadow-sm dark:border-border">
      <div className="flex items-center gap-2">
        <WandSparklesIcon className="size-4 text-success" />
        <h3 className="text-sm font-semibold">Benchmark recommendations</h3>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
        Recommendations rank benchmarked structured-output models. They are
        never applied automatically.
      </p>

      <div className="mt-4 space-y-3">
        {(["planning", "generation", "repair"] as TaskStage[]).map(
          (stage) => {
            const item = recommendations?.recommendations[stage];

            return (
              <div
                key={stage}
                className="rounded-xl border border-border bg-surface-raised/70 p-3"
              >
                <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                  {stageLabels[stage]}
                </p>
                {item ? (
                  <>
                    <p className="mt-1 break-all text-xs font-semibold text-foreground">
                      {item.model}
                    </p>
                    <p className="mt-1 text-[10px] text-muted-foreground">
                      {item.provider_id} · score {item.score.toFixed(2)}
                      {item.measured_tokens_per_second == null
                        ? ""
                        : ` · ${item.measured_tokens_per_second.toFixed(2)} tok/s`}
                    </p>
                  </>
                ) : (
                  <p className="mt-1 text-xs text-muted-foreground">
                    No benchmarked model yet.
                  </p>
                )}
              </div>
            );
          },
        )}
      </div>

      <p className="mt-4 text-[10px] text-muted-foreground">
        {recommendations?.benchmarked_model_count ?? 0} benchmarked model
        profile(s).
      </p>
    </div>
  );
}

function MessageBanner({
  tone,
  icon: Icon,
  title,
  message,
}: {
  tone: "error" | "success";
  icon: typeof TriangleAlertIcon;
  title: string;
  message: string;
}) {
  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded-xl border p-4 text-sm",
        tone === "error"
          ? "border-danger/30 bg-danger/10 text-danger dark:border-danger/30 dark:bg-danger/10 dark:text-danger"
          : "border-success/30 bg-success/10 text-success dark:border-success/30 dark:bg-success/10 dark:text-success",
      )}
    >
      <Icon className="mt-0.5 size-4 shrink-0" />
      <div>
        <p className="font-medium">{title}</p>
        <p className="mt-1 text-xs opacity-85">{message}</p>
      </div>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      <div className="mt-1.5">{children}</div>
    </label>
  );
}

function NumberField({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max?: number;
  step: number;
  onChange: (value: number) => void;
}) {
  return (
    <Field label={label}>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(event) => {
          const parsed = Number(event.target.value);
          if (Number.isFinite(parsed)) onChange(parsed);
        }}
        className={inputClass}
      />
    </Field>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-1 truncate font-medium text-foreground dark:text-foreground">
        {value}
      </dd>
    </div>
  );
}

const inputClass =
  "w-full rounded-lg border border-border bg-surface px-3 py-2 text-xs text-foreground outline-none ring-emerald-500/20 focus:border-success/30 focus:ring-4 dark:border-border dark:bg-surface-raised dark:text-foreground";

function toMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function bytesToGb(value: number | null | undefined): number | null {
  if (value == null) return null;
  return value / 1024 / 1024 / 1024;
}

function formatGb(value: number | null): string {
  return value == null ? "—" : `${value.toFixed(1)} GB`;
}

function formatBytes(value: number): string {
  if (value >= 1024 ** 3) {
    return `${(value / 1024 ** 3).toFixed(2)} GB`;
  }
  if (value >= 1024 ** 2) {
    return `${(value / 1024 ** 2).toFixed(1)} MB`;
  }
  return `${value.toLocaleString("en-US")} bytes`;
}

function formatInteger(value: number | null | undefined): string {
  return value == null ? "—" : value.toLocaleString("en-US");
}

function formatTier(
  tier: HardwareSnapshot["installed_models"][number]["tier"] | undefined,
): string {
  return tier?.replaceAll("_", " ") ?? "Unknown fit";
}

function tierClass(
  tier: HardwareSnapshot["installed_models"][number]["tier"] | undefined,
): string {
  switch (tier) {
    case "fastest":
      return "bg-success/10 text-success dark:text-success";
    case "balanced":
      return "bg-pending/10 text-pending dark:text-pending";
    case "maximum_practical":
      return "bg-pending/10 text-pending dark:text-pending";
    case "not_recommended":
      return "bg-danger/10 text-danger dark:text-danger";
    default:
      return "bg-surface-hover text-muted-foreground dark:bg-surface-hover dark:text-muted-foreground";
  }
}
