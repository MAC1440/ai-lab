"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BotIcon,
  CheckCircle2Icon,
  ChipIcon,
  CpuIcon,
  GaugeIcon,
  HardDriveIcon,
  MemoryStickIcon,
  RefreshCwIcon,
  SaveIcon,
  ServerIcon,
  ShieldAlertIcon,
  SparklesIcon,
  TriangleAlertIcon,
  WandSparklesIcon,
} from "lucide-react";

import {
  discoverModels,
  getModelSettings,
  saveAgentModel,
  saveTaskStageModel,
  testProvider,
  type AgentModelSettings,
  type DiscoveredModel,
  type ModelProvider,
  type ModelSettingsSnapshot,
  type TaskStage,
} from "@/features/model-settings/model-settings-api";
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

type AgentId = "coding" | "unity" | "web";
type RuntimeStage = "chat" | TaskStage;

const agentLabels: Record<AgentId, string> = {
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
    void loadWorkspace();
  }, [loadWorkspace]);

  const discoverProvider = async (provider: ModelProvider) => {
    const key = `discover:${provider.id}`;
    setBusyKey(key);
    setError(null);
    setNotice(null);

    try {
      const result = await discoverModels(provider.id);
      setDiscovered((current) => ({
        ...current,
        [provider.id]: result.models,
      }));
      setNotice(
        `Discovered ${result.models.length} model${
          result.models.length === 1 ? "" : "s"
        } from ${provider.name}.`,
      );
    } catch (discoverError) {
      setError(toMessage(discoverError, "Model discovery failed."));
    } finally {
      setBusyKey(null);
    }
  };

  const testProviderConnection = async (provider: ModelProvider) => {
    const key = `test:${provider.id}`;
    setBusyKey(key);
    setError(null);
    setNotice(null);

    try {
      const result = await testProvider(provider.id);
      setDiscovered((current) => ({
        ...current,
        [provider.id]: result.models,
      }));
      setNotice(result.message);
    } catch (testError) {
      setError(toMessage(testError, "Provider test failed."));
    } finally {
      setBusyKey(null);
    }
  };

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
              busyKey={busyKey}
              loading={loading}
              onDiscover={discoverProvider}
              onTest={testProviderConnection}
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
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-600 dark:text-emerald-400">
          Local inference control
        </p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-950 dark:text-zinc-50">
          Models and runtime
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
          Inspect installed models, verify provider connectivity, manage agent
          assignments, and keep context limits appropriate for this machine.
        </p>
      </div>

      <button
        type="button"
        onClick={onRefresh}
        disabled={loading || busy}
        className="inline-flex w-fit items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs font-medium text-zinc-700 shadow-sm transition hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
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
        icon={ChipIcon}
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
    <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
          {label}
        </p>
        <div className="flex size-8 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
          <Icon className="size-4" />
        </div>
      </div>
      <p className="mt-4 truncate text-base font-semibold text-zinc-950 dark:text-zinc-50">
        {value}
      </p>
      <p className="mt-1 truncate text-[11px] text-zinc-400">{detail}</p>
    </div>
  );
}

function ProviderSection({
  providers,
  discovered,
  hardware,
  profiles,
  busyKey,
  loading,
  onDiscover,
  onTest,
}: {
  providers: ModelProvider[];
  discovered: Record<string, DiscoveredModel[]>;
  hardware: HardwareSnapshot | null;
  profiles: ModelCapabilityProfile[];
  busyKey: string | null;
  loading: boolean;
  onDiscover: (provider: ModelProvider) => Promise<void>;
  onTest: (provider: ModelProvider) => Promise<void>;
}) {
  return (
    <div className="rounded-2xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      <div className="border-b border-zinc-200 p-4 sm:p-5 dark:border-zinc-800">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
          Providers and installed models
        </h3>
        <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
          Test the configured endpoint, discover models, and compare them with
          saved capability profiles.
        </p>
      </div>

      <div className="divide-y divide-zinc-100 dark:divide-zinc-900">
        {loading ? (
          <div className="p-8 text-center text-xs text-zinc-400">
            Loading providers…
          </div>
        ) : providers.length === 0 ? (
          <div className="p-8 text-center text-xs text-zinc-400">
            No model providers are configured.
          </div>
        ) : (
          providers.map((provider) => (
            <ProviderCard
              key={provider.id}
              provider={provider}
              models={
                discovered[provider.id]
                ?? hardware?.installed_models.map((model) => ({
                  name: model.name,
                  size: model.size_bytes,
                  modified_at: null,
                  warnings:
                    model.tier === "not_recommended"
                      ? ["This model may exceed the practical hardware tier."]
                      : [],
                }))
                ?? []
              }
              hardware={hardware}
              profiles={profiles}
              discovering={busyKey === `discover:${provider.id}`}
              testing={busyKey === `test:${provider.id}`}
              onDiscover={() => onDiscover(provider)}
              onTest={() => onTest(provider)}
            />
          ))
        )}
      </div>
    </div>
  );
}

function ProviderCard({
  provider,
  models,
  hardware,
  profiles,
  discovering,
  testing,
  onDiscover,
  onTest,
}: {
  provider: ModelProvider;
  models: DiscoveredModel[];
  hardware: HardwareSnapshot | null;
  profiles: ModelCapabilityProfile[];
  discovering: boolean;
  testing: boolean;
  onDiscover: () => Promise<void>;
  onTest: () => Promise<void>;
}) {
  return (
    <div className="p-4 sm:p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-zinc-100 text-zinc-600 dark:bg-zinc-900 dark:text-zinc-300">
            <ServerIcon className="size-4" />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h4 className="truncate text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                {provider.name}
              </h4>
              <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-[9px] font-medium uppercase tracking-wide text-zinc-500 dark:bg-zinc-800 dark:text-zinc-300">
                {provider.kind.replace("_", " ")}
              </span>
              {provider.built_in ? (
                <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[9px] font-medium uppercase tracking-wide text-emerald-600 dark:text-emerald-400">
                  Built in
                </span>
              ) : null}
            </div>
            <p className="mt-1 break-all font-mono text-[11px] text-zinc-400">
              {provider.base_url}
            </p>
          </div>
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => void onTest()}
            disabled={testing || discovering}
            className="rounded-lg border border-zinc-200 px-3 py-2 text-xs font-medium text-zinc-600 hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-900"
          >
            {testing ? "Testing…" : "Test"}
          </button>
          <button
            type="button"
            onClick={() => void onDiscover()}
            disabled={discovering || testing}
            className="rounded-lg bg-zinc-900 px-3 py-2 text-xs font-medium text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
          >
            {discovering ? "Discovering…" : "Discover models"}
          </button>
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {models.length === 0 ? (
          <div className="col-span-full rounded-xl border border-dashed border-zinc-200 p-5 text-center text-xs text-zinc-400 dark:border-zinc-800">
            Run discovery to list models from this provider.
          </div>
        ) : (
          models.map((model) => {
            const profile = profiles.find(
              (item) =>
                item.provider_id === provider.id
                && item.model === model.name,
            );
            const hardwareModel = hardware?.installed_models.find(
              (item) => item.name === model.name,
            );

            return (
              <ModelCard
                key={`${provider.id}:${model.name}`}
                model={model}
                profile={profile}
                hardwareTier={hardwareModel?.tier}
              />
            );
          })
        )}
      </div>
    </div>
  );
}

function ModelCard({
  model,
  profile,
  hardwareTier,
}: {
  model: DiscoveredModel;
  profile?: ModelCapabilityProfile;
  hardwareTier?: HardwareSnapshot["installed_models"][number]["tier"];
}) {
  const warnings = [
    ...model.warnings,
    ...(hardwareTier === "not_recommended"
      ? ["Model is above the practical hardware recommendation."]
      : []),
    ...(profile?.structured_output_mode === "unsupported"
      ? ["Structured task output is marked unsupported."]
      : []),
  ];

  return (
    <div className="rounded-xl border border-zinc-200 bg-zinc-50/60 p-4 dark:border-zinc-800 dark:bg-zinc-900/40">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            {model.name}
          </p>
          <p className="mt-1 text-[11px] text-zinc-400">
            {model.size ? formatBytes(model.size) : "Size unavailable"}
          </p>
        </div>

        <span
          className={cn(
            "rounded-full px-2 py-1 text-[9px] font-medium uppercase tracking-wide",
            tierClass(hardwareTier),
          )}
        >
          {formatTier(hardwareTier)}
        </span>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
        <Metric label="Context" value={formatInteger(profile?.context_window)} />
        <Metric
          label="Max output"
          value={formatInteger(profile?.max_output_tokens)}
        />
        <Metric
          label="Measured speed"
          value={
            profile?.measured_tokens_per_second == null
              ? "Not benchmarked"
              : `${profile.measured_tokens_per_second.toFixed(2)} tok/s`
          }
        />
        <Metric
          label="Structured mode"
          value={profile?.structured_output_mode ?? "Inferred"}
        />
      </dl>

      {warnings.length > 0 ? (
        <div className="mt-4 space-y-1.5">
          {warnings.map((warning) => (
            <p
              key={warning}
              className="flex items-start gap-2 text-[11px] leading-relaxed text-amber-700 dark:text-amber-300"
            >
              <ShieldAlertIcon className="mt-0.5 size-3 shrink-0" />
              {warning}
            </p>
          ))}
        </div>
      ) : null}
    </div>
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
      <div className="rounded-2xl border border-zinc-200 bg-white p-8 text-center text-xs text-zinc-400 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
        Loading model assignments…
      </div>
    );
  }

  if (!snapshot) return null;

  const agents = Object.keys(snapshot.agents) as AgentId[];

  return (
    <div className="rounded-2xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      <div className="border-b border-zinc-200 p-4 sm:p-5 dark:border-zinc-800">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
          Agent and task-stage assignments
        </h3>
        <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
          The base agent model handles chat. Optional stage overrides handle
          planning, file generation, and repair.
        </p>
      </div>

      <div className="divide-y divide-zinc-100 dark:divide-zinc-900">
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
        <div className="flex size-9 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
          <BotIcon className="size-4" />
        </div>
        <div>
          <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            {agentLabels[agentId]} agent
          </h4>
          <p className="text-[11px] text-zinc-400">
            Base chat model and optional task-stage overrides
          </p>
        </div>
      </div>

      <div className="mt-4 grid gap-3 xl:grid-cols-2">
        <AssignmentEditor
          title="Base chat assignment"
          assignment={base}
          providers={snapshot.providers}
          discovered={discovered}
          profiles={profiles}
          saving={busyKey === `agent:${agentId}`}
          onSave={(value) => onSaveAgent(agentId, value)}
        />

        {(["planning", "generation", "repair"] as TaskStage[]).map(
          (stage) => (
            <AssignmentEditor
              key={stage}
              title={`${stageLabels[stage]} override`}
              assignment={stages[stage] ?? base}
              providers={snapshot.providers}
              discovered={discovered}
              profiles={profiles}
              recommendation={recommendations?.recommendations[stage]}
              saving={busyKey === `stage:${agentId}:${stage}`}
              onSave={(value) => onSaveStage(agentId, stage, value)}
            />
          ),
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

  useEffect(() => {
    setDraft(assignment);
  }, [assignment]);

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
    <div className="rounded-xl border border-zinc-200 bg-zinc-50/60 p-4 dark:border-zinc-800 dark:bg-zinc-900/40">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h5 className="text-xs font-semibold text-zinc-800 dark:text-zinc-200">
            {title}
          </h5>
          <p className="mt-1 text-[10px] text-zinc-400">
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
            className="inline-flex items-center gap-1 rounded-lg bg-emerald-500/10 px-2 py-1 text-[10px] font-medium text-emerald-700 dark:text-emerald-300"
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
        <p className="mt-3 text-[10px] text-zinc-400">
          Saved capability: {formatInteger(profile.context_window)} context,
          {" "}
          {formatInteger(profile.max_output_tokens)} max output,
          {" "}
          {profile.measured_tokens_per_second == null
            ? "not benchmarked"
            : `${profile.measured_tokens_per_second.toFixed(2)} tok/s`}.
        </p>
      ) : (
        <p className="mt-3 flex items-start gap-1.5 text-[10px] text-amber-600 dark:text-amber-300">
          <ShieldAlertIcon className="mt-0.5 size-3 shrink-0" />
          No saved capability profile exists. Conservative inferred limits will
          be used.
        </p>
      )}

      <button
        type="button"
        onClick={() => void onSave(draft)}
        disabled={saving || !draft.model.trim() || !provider}
        className="mt-4 inline-flex items-center gap-2 rounded-lg bg-zinc-900 px-3 py-2 text-xs font-medium text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
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
    <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            Runtime limits
          </h3>
          <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
            Global stage defaults are clamped by each model capability profile.
          </p>
        </div>
        <HardDriveIcon className="size-4 text-emerald-500" />
      </div>

      {loading || !runtime ? (
        <div className="py-8 text-center text-xs text-zinc-400">
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

          <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50/70 p-3 text-[11px] leading-relaxed text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-200">
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
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-700 hover:bg-emerald-100 disabled:opacity-50 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-300"
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
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-zinc-900 px-3 py-2 text-xs font-medium text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
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
    <details className="rounded-xl border border-zinc-200 bg-zinc-50/60 p-3 open:bg-white dark:border-zinc-800 dark:bg-zinc-900/40 dark:open:bg-zinc-950">
      <summary className="cursor-pointer select-none text-xs font-semibold text-zinc-700 dark:text-zinc-200">
        {stageLabels[stage]}
        <span className="ml-2 font-normal text-zinc-400">
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
    <div className="rounded-2xl border border-zinc-200 bg-zinc-950 p-4 text-zinc-100 shadow-sm dark:border-zinc-800">
      <div className="flex items-center gap-2">
        <WandSparklesIcon className="size-4 text-emerald-400" />
        <h3 className="text-sm font-semibold">Benchmark recommendations</h3>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-zinc-400">
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
                className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-3"
              >
                <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">
                  {stageLabels[stage]}
                </p>
                {item ? (
                  <>
                    <p className="mt-1 break-all text-xs font-semibold text-zinc-100">
                      {item.model}
                    </p>
                    <p className="mt-1 text-[10px] text-zinc-400">
                      {item.provider_id} · score {item.score.toFixed(2)}
                      {item.measured_tokens_per_second == null
                        ? ""
                        : ` · ${item.measured_tokens_per_second.toFixed(2)} tok/s`}
                    </p>
                  </>
                ) : (
                  <p className="mt-1 text-xs text-zinc-500">
                    No benchmarked model yet.
                  </p>
                )}
              </div>
            );
          },
        )}
      </div>

      <p className="mt-4 text-[10px] text-zinc-500">
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
          ? "border-red-200 bg-red-50 text-red-800 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-200"
          : "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-200",
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
      <span className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">
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
      <dt className="text-[10px] uppercase tracking-wide text-zinc-400">
        {label}
      </dt>
      <dd className="mt-1 truncate font-medium text-zinc-700 dark:text-zinc-200">
        {value}
      </dd>
    </div>
  );
}

const inputClass =
  "w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs text-zinc-800 outline-none ring-emerald-500/20 focus:border-emerald-500 focus:ring-4 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-200";

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
      return "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
    case "balanced":
      return "bg-sky-500/10 text-sky-700 dark:text-sky-300";
    case "maximum_practical":
      return "bg-amber-500/10 text-amber-700 dark:text-amber-300";
    case "not_recommended":
      return "bg-red-500/10 text-red-700 dark:text-red-300";
    default:
      return "bg-zinc-200 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-300";
  }
}
