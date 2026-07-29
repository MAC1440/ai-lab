"use client";

import {
  CheckCircle2Icon,
  CloudIcon,
  DownloadIcon,
  HardDriveDownloadIcon,
  LoaderCircleIcon,
  RefreshCwIcon,
  SearchIcon,
  ServerIcon,
  ShieldAlertIcon,
  TriangleAlertIcon,
  WifiIcon,
} from "lucide-react";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type KeyboardEvent,
  type ReactNode,
} from "react";

import {
  discoverModels,
  pullOllamaModel,
  testProvider,
  type DiscoveredModel,
  type ModelProvider,
  type PullProgressEvent,
} from "@/features/model-settings/model-settings-api";
import type { ModelCapabilityProfile } from "@/features/model-settings/model-workspace-api";
import type { HardwareSnapshot } from "@/features/runtime/runtime-api";
import { cn } from "@/lib/utils";

type PullState = PullProgressEvent & {
  startedAt: number;
};

type Props = {
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
};

export function ModelLibraryPanel({
  providers,
  discovered,
  hardware,
  profiles,
  loading,
  onDiscovered,
  onNotice,
  onError,
  onWorkspaceRefresh,
}: Props) {
  const [providerBusy, setProviderBusy] = useState<
    Record<string, "discover" | "test" | undefined>
  >({});
  const [pulls, setPulls] = useState<Record<string, PullState>>({});
  const discoveredOnce = useRef(new Set<string>());

  const localPullProvider = providers.find(supportsPull);
  const providerIds = providers.map((provider) => provider.id).join("|");

  const loadProvider = async (
    provider: ModelProvider,
    announce = true,
  ) => {
    setProviderBusy((current) => ({
      ...current,
      [provider.id]: "discover",
    }));

    try {
      const result = await discoverModels(provider.id);
      onDiscovered(provider.id, result.models);
      if (announce) {
        onNotice(
          `Found ${result.models.length} model${
            result.models.length === 1 ? "" : "s"
          } from ${provider.name}.`,
        );
      }
    } catch (error) {
      if (announce) {
        onError(toMessage(error, "Model discovery failed."));
      }
    } finally {
      setProviderBusy((current) => ({
        ...current,
        [provider.id]: undefined,
      }));
    }
  };

  useEffect(() => {
    for (const provider of providers) {
      if (discoveredOnce.current.has(provider.id)) continue;
      discoveredOnce.current.add(provider.id);
      void loadProvider(provider, false);
    }
    // Providers are intentionally keyed by id. Manual refresh handles URL/key edits.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [providerIds]);

  const testConnection = async (provider: ModelProvider) => {
    onError(null);
    onNotice(null);
    setProviderBusy((current) => ({
      ...current,
      [provider.id]: "test",
    }));

    try {
      const result = await testProvider(provider.id);
      onDiscovered(provider.id, result.models);
      onNotice(result.message);
    } catch (error) {
      onError(toMessage(error, "Provider test failed."));
    } finally {
      setProviderBusy((current) => ({
        ...current,
        [provider.id]: undefined,
      }));
    }
  };

  const startPull = async (
    provider: ModelProvider,
    rawModel: string,
  ) => {
    const model = rawModel.trim();
    if (!model) return;

    const key = pullKey(provider.id, model);
    onError(null);
    onNotice(null);
    setPulls((current) => ({
      ...current,
      [key]: {
        type: "progress",
        provider_id: provider.id,
        model,
        status: "Starting pull…",
        total: null,
        completed: null,
        percent: null,
        startedAt: Date.now(),
      },
    }));

    try {
      await pullOllamaModel(
        provider.id,
        model,
        (event) => {
          setPulls((current) => ({
            ...current,
            [key]: {
              ...event,
              startedAt: current[key]?.startedAt ?? Date.now(),
            },
          }));
        },
      );

      const result = await discoverModels(provider.id);
      onDiscovered(provider.id, result.models);
      await onWorkspaceRefresh();
      onNotice(
        `${model} is ready through ${provider.name}.`,
      );
    } catch (error) {
      const message = toMessage(error, "Model pull failed.");
      setPulls((current) => ({
        ...current,
        [key]: {
          ...(current[key] ?? {
            provider_id: provider.id,
            model,
            total: null,
            completed: null,
            percent: null,
            startedAt: Date.now(),
          }),
          type: "error",
          status: "error",
          error: message,
        },
      }));
      onError(message);
    }
  };

  return (
    <div className="rounded-2xl border border-border bg-surface shadow-sm dark:border-border dark:bg-surface-raised">
      <div className="flex flex-col gap-3 border-b border-border p-4 sm:flex-row sm:items-start sm:justify-between sm:p-5 dark:border-border">
        <div>
          <h3 className="text-sm font-semibold text-foreground dark:text-foreground">
            Model library
          </h3>
          <p className="mt-1 max-w-3xl text-xs leading-relaxed text-muted-foreground dark:text-muted-foreground">
            Browse ready local and cloud models, pull new local models,
            register cloud shortcuts through local Ollama, and watch download
            progress without leaving AI Lab.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-[10px]">
          <LibraryLegend icon={HardDriveDownloadIcon} label="Local" />
          <LibraryLegend icon={CloudIcon} label="Cloud" />
          <LibraryLegend icon={WifiIcon} label="Remote API" />
        </div>
      </div>

      <div className="divide-y divide-border dark:divide-border">
        {loading && providers.length === 0 ? (
          <div className="p-8 text-center text-xs text-muted-foreground">
            Loading providers…
          </div>
        ) : providers.length === 0 ? (
          <div className="p-8 text-center text-xs text-muted-foreground">
            No model providers are configured.
          </div>
        ) : (
          providers.map((provider) => (
            <ProviderLibraryCard
              key={provider.id}
              provider={provider}
              models={providerModels(provider, discovered, hardware)}
              hardware={hardware}
              profiles={profiles}
              localPullProvider={localPullProvider}
              pulls={pulls}
              busy={providerBusy[provider.id]}
              onDiscover={() => loadProvider(provider)}
              onTest={() => testConnection(provider)}
              onPull={startPull}
            />
          ))
        )}
      </div>
    </div>
  );
}

function ProviderLibraryCard({
  provider,
  models,
  hardware,
  profiles,
  localPullProvider,
  pulls,
  busy,
  onDiscover,
  onTest,
  onPull,
}: {
  provider: ModelProvider;
  models: DiscoveredModel[];
  hardware: HardwareSnapshot | null;
  profiles: ModelCapabilityProfile[];
  localPullProvider?: ModelProvider;
  pulls: Record<string, PullState>;
  busy?: "discover" | "test";
  onDiscover: () => Promise<void>;
  onTest: () => Promise<void>;
  onPull: (
    provider: ModelProvider,
    model: string,
  ) => Promise<void>;
}) {
  const [query, setQuery] = useState("");
  const [pullName, setPullName] = useState("");
  const cloudProvider = isCloudProvider(provider);
  const canPull = supportsPull(provider);
  const latestPull = useMemo(
    () =>
      Object.values(pulls)
        .filter((item) => item.provider_id === provider.id)
        .sort((left, right) => right.startedAt - left.startedAt)[0],
    [provider.id, pulls],
  );

  const filteredModels = useMemo(() => {
    const clean = query.trim().toLowerCase();
    if (!clean) return models;
    return models.filter((model) => {
      const details = model.details ?? {};
      return [
        model.name,
        model.availability,
        details.family,
        details.parameter_size,
        details.quantization_level,
      ]
        .filter(Boolean)
        .some((value) =>
          String(value).toLowerCase().includes(clean),
        );
    });
  }, [models, query]);

  return (
    <section className="p-4 sm:p-5">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="flex min-w-0 gap-3">
          <div
            className={cn(
              "flex size-10 shrink-0 items-center justify-center rounded-xl",
              cloudProvider
                ? "bg-sky-500/10 text-sky-600 dark:text-sky-400"
                : "bg-success/10 text-success",
            )}
          >
            {cloudProvider ? (
              <CloudIcon className="size-4" />
            ) : (
              <ServerIcon className="size-4" />
            )}
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h4 className="truncate text-sm font-semibold text-foreground dark:text-foreground">
                {provider.name}
              </h4>
              <Badge>
                {cloudProvider
                  ? "Direct cloud"
                  : provider.kind.replace("_", " ")}
              </Badge>
              {provider.built_in ? (
                <Badge tone="success">Built in</Badge>
              ) : null}
              {canPull ? (
                <Badge tone="success">Pull enabled</Badge>
              ) : null}
            </div>
            <p className="mt-1 break-all font-mono text-[11px] text-muted-foreground">
              {provider.base_url}
            </p>
            <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
              {cloudProvider
                ? "Models on this provider are ready immediately. Pulling is only needed when you want a cloud shortcut routed through local Ollama."
                : canPull
                  ? "Pull local models or cloud references. Cloud pulls require this Ollama installation to be signed in."
                  : "This provider exposes ready remote models but does not support Ollama pulls."}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            onClick={() => void onTest()}
            disabled={busy != null}
            className={secondaryButtonClass}
          >
            {busy === "test" ? (
              <LoaderCircleIcon className="size-3.5 animate-spin" />
            ) : (
              <WifiIcon className="size-3.5" />
            )}
            {busy === "test" ? "Testing…" : "Test"}
          </button>
          <button
            type="button"
            onClick={() => void onDiscover()}
            disabled={busy != null}
            className={primaryButtonClass}
          >
            <RefreshCwIcon
              className={cn(
                "size-3.5",
                busy === "discover" && "animate-spin",
              )}
            />
            {busy === "discover" ? "Refreshing…" : "Refresh models"}
          </button>
        </div>
      </div>

      {canPull ? (
        <div className="mt-4 rounded-xl border border-success/20 bg-success/5 p-3 dark:border-success/20 dark:bg-success/5">
          <div className="flex flex-col gap-2 sm:flex-row">
            <label className="relative min-w-0 flex-1">
              <DownloadIcon className="pointer-events-none absolute left-3 top-2.5 size-3.5 text-muted-foreground" />
              <input
                value={pullName}
                onChange={(event: ChangeEvent<HTMLInputElement>) => setPullName(event.target.value)}
                onKeyDown={(event: KeyboardEvent<HTMLInputElement>) => {
                  if (event.key === "Enter" && pullName.trim()) {
                    event.preventDefault();
                    void onPull(provider, pullName);
                  }
                }}
                placeholder="Pull qwen3:4b or qwen3.5:cloud"
                className={`${inputClass} pl-9`}
              />
            </label>
            <button
              type="button"
              onClick={() => void onPull(provider, pullName)}
              disabled={!pullName.trim() || isPulling(latestPull)}
              className={primaryButtonClass}
            >
              {isPulling(latestPull) ? (
                <LoaderCircleIcon className="size-3.5 animate-spin" />
              ) : (
                <DownloadIcon className="size-3.5" />
              )}
              Pull model
            </button>
          </div>
          <p className="mt-2 text-[10px] leading-relaxed text-muted-foreground">
            Local models download their weights. A <code>:cloud</code> or{" "}
            <code>-cloud</code> reference creates a lightweight local entry and
            runs remotely after Ollama authentication.
          </p>
          {latestPull ? (
            <PullProgressCard state={latestPull} />
          ) : null}
        </div>
      ) : null}

      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <label className="relative w-full sm:max-w-sm">
          <SearchIcon className="pointer-events-none absolute left-3 top-2.5 size-3.5 text-muted-foreground" />
          <input
            value={query}
            onChange={(event: ChangeEvent<HTMLInputElement>) => setQuery(event.target.value)}
            placeholder="Search model name, family, or size"
            className={`${inputClass} pl-9`}
          />
        </label>
        <p className="text-[11px] text-muted-foreground">
          {filteredModels.length} of {models.length} model
          {models.length === 1 ? "" : "s"}
        </p>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {models.length === 0 ? (
          <EmptyModels cloud={cloudProvider} />
        ) : filteredModels.length === 0 ? (
          <div className="col-span-full rounded-xl border border-dashed border-border p-5 text-center text-xs text-muted-foreground dark:border-border">
            No models match “{query}”.
          </div>
        ) : (
          filteredModels.map((model) => {
            const profile = profiles.find(
              (item) =>
                item.provider_id === provider.id
                && item.model === model.name,
            );
            const hardwareModel = hardware?.installed_models.find(
              (item) => item.name === model.name,
            );
            const localReference =
              model.pull_name || suggestCloudReference(model.name);
            const pullTarget =
              canPull
                ? provider
                : cloudProvider && localPullProvider
                  ? localPullProvider
                  : undefined;
            const pullReference =
              pullTarget?.id === provider.id
                ? model.name
                : localReference;
            const pullState = pullTarget
              ? pulls[pullKey(pullTarget.id, pullReference)]
              : undefined;

            return (
              <LibraryModelCard
                key={`${provider.id}:${model.name}`}
                provider={provider}
                model={model}
                profile={profile}
                hardwareTier={hardwareModel?.tier}
                pullTarget={pullTarget}
                pullReference={pullReference}
                pullState={pullState}
                onPull={onPull}
              />
            );
          })
        )}
      </div>
    </section>
  );
}

function LibraryModelCard({
  provider,
  model,
  profile,
  hardwareTier,
  pullTarget,
  pullReference,
  pullState,
  onPull,
}: {
  provider: ModelProvider;
  model: DiscoveredModel;
  profile?: ModelCapabilityProfile;
  hardwareTier?: HardwareSnapshot["installed_models"][number]["tier"];
  pullTarget?: ModelProvider;
  pullReference: string;
  pullState?: PullState;
  onPull: (
    provider: ModelProvider,
    model: string,
  ) => Promise<void>;
}) {
  const availability =
    model.availability
    ?? (isCloudProvider(provider) ? "cloud" : "local");
  const remote = availability !== "local";
  const warnings = [
    ...model.warnings,
    ...(!remote && hardwareTier === "not_recommended"
      ? ["Model is above the practical hardware recommendation."]
      : []),
    ...(profile?.structured_output_mode === "unsupported"
      ? ["Structured task output is marked unsupported."]
      : []),
  ];

  return (
    <article className="rounded-xl border border-border bg-surface-hover/60 p-4 dark:border-border dark:bg-surface-raised/40">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-foreground dark:text-foreground">
            {model.name}
          </p>
          <p className="mt-1 text-[11px] text-muted-foreground">
            {remote
              ? availability === "cloud"
                ? "Cloud hosted"
                : "Remote provider"
              : model.size
                ? formatBytes(model.size)
                : "Local size unavailable"}
          </p>
        </div>
        <Badge tone={remote ? "cloud" : "success"}>
          {availability === "cloud"
            ? "Cloud ready"
            : availability === "remote"
              ? "Remote ready"
              : "Installed"}
        </Badge>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
        <Metric
          label="Parameters"
          value={model.details?.parameter_size ?? "—"}
        />
        <Metric
          label="Quantization"
          value={model.details?.quantization_level ?? "—"}
        />
        <Metric
          label="Context"
          value={formatInteger(profile?.context_window)}
        />
        <Metric
          label="Structured mode"
          value={profile?.structured_output_mode ?? "Inferred"}
        />
      </dl>

      {!remote ? (
        <div className="mt-3">
          <span
            className={cn(
              "rounded-full px-2 py-1 text-[9px] font-medium uppercase tracking-wide",
              tierClass(hardwareTier),
            )}
          >
            {formatTier(hardwareTier)}
          </span>
        </div>
      ) : null}

      {warnings.length > 0 ? (
        <div className="mt-4 space-y-1.5">
          {warnings.map((warning) => (
            <p
              key={warning}
              className="flex items-start gap-2 text-[11px] leading-relaxed text-pending dark:text-pending"
            >
              <ShieldAlertIcon className="mt-0.5 size-3 shrink-0" />
              {warning}
            </p>
          ))}
        </div>
      ) : null}

      {pullTarget ? (
        <div className="mt-4 rounded-lg border border-border bg-surface p-3 dark:border-border dark:bg-surface-raised">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <p className="text-[10px] text-muted-foreground">
                {pullTarget.id === provider.id
                  ? availability === "cloud"
                    ? "Cloud reference on this Ollama provider"
                    : "Installed on this Ollama provider"
                  : "Create a local Ollama cloud reference"}
              </p>
              <p className="mt-1 break-all font-mono text-[11px] text-foreground">
                {pullReference}
              </p>
            </div>
            <button
              type="button"
              onClick={() => void onPull(pullTarget, pullReference)}
              disabled={isPulling(pullState)}
              className={`${secondaryButtonClass} shrink-0 justify-center`}
            >
              {isPulling(pullState) ? (
                <LoaderCircleIcon className="size-3.5 animate-spin" />
              ) : availability === "cloud" ? (
                <CloudIcon className="size-3.5" />
              ) : (
                <DownloadIcon className="size-3.5" />
              )}
              {pullTarget.id !== provider.id
                ? `Pull to ${pullTarget.name}`
                : availability === "cloud"
                  ? "Refresh cloud model"
                  : "Update model"}
            </button>
          </div>
          {pullState ? (
            <PullProgressCard state={pullState} compact />
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

function PullProgressCard({
  state,
  compact = false,
}: {
  state: PullState;
  compact?: boolean;
}) {
  const failed = state.type === "error";
  const done = state.type === "done";
  const percent = state.percent;
  const determinate = percent != null;

  return (
    <div
      className={cn(
        "mt-3 rounded-lg border p-3",
        failed
          ? "border-danger/30 bg-danger/5"
          : done
            ? "border-success/30 bg-success/5"
            : "border-border bg-surface",
      )}
    >
      <div className="flex items-start gap-2">
        {failed ? (
          <TriangleAlertIcon className="mt-0.5 size-3.5 shrink-0 text-danger" />
        ) : done ? (
          <CheckCircle2Icon className="mt-0.5 size-3.5 shrink-0 text-success" />
        ) : (
          <LoaderCircleIcon className="mt-0.5 size-3.5 shrink-0 animate-spin text-success" />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-3">
            <p className="truncate text-[11px] font-medium text-foreground">
              {state.model}
            </p>
            <span className="text-[10px] tabular-nums text-muted-foreground">
              {determinate ? `${percent.toFixed(1)}%` : "Working"}
            </span>
          </div>
          <p
            className={cn(
              "mt-1 text-[10px] leading-relaxed",
              failed ? "text-danger" : "text-muted-foreground",
            )}
          >
            {state.error || state.status}
          </p>

          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-hover">
            <div
              className={cn(
                "h-full rounded-full bg-success transition-all",
                !determinate && !done && "w-1/3 animate-pulse",
              )}
              style={
                determinate
                  ? { width: `${Math.max(2, percent)}%` }
                  : undefined
              }
            />
          </div>

          {!compact && state.completed != null ? (
            <p className="mt-2 text-[10px] text-muted-foreground">
              {formatBytes(state.completed)}
              {state.total ? ` of ${formatBytes(state.total)}` : ""}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function EmptyModels({ cloud }: { cloud: boolean }) {
  return (
    <div className="col-span-full rounded-xl border border-dashed border-border p-6 text-center dark:border-border">
      <div className="mx-auto flex size-10 items-center justify-center rounded-xl bg-surface-hover text-muted-foreground">
        {cloud ? (
          <CloudIcon className="size-4" />
        ) : (
          <DownloadIcon className="size-4" />
        )}
      </div>
      <p className="mt-3 text-xs font-medium text-foreground">
        {cloud ? "No cloud models returned" : "No models installed yet"}
      </p>
      <p className="mx-auto mt-1 max-w-md text-[11px] leading-relaxed text-muted-foreground">
        {cloud
          ? "Confirm the API key, then test or refresh this provider."
          : "Enter a model name above to pull it. Progress will appear here while Ollama downloads or registers the model."}
      </p>
    </div>
  );
}

function LibraryLegend({
  icon: Icon,
  label,
}: {
  icon: typeof CloudIcon;
  label: string;
}) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-hover px-2.5 py-1 text-muted-foreground dark:border-border dark:bg-surface-hover">
      <Icon className="size-3" />
      {label}
    </span>
  );
}

function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "success" | "cloud";
}) {
  return (
    <span
      className={cn(
        "rounded-full px-2 py-0.5 text-[9px] font-medium uppercase tracking-wide",
        tone === "success"
          ? "bg-success/10 text-success"
          : tone === "cloud"
            ? "bg-sky-500/10 text-sky-600 dark:text-sky-400"
            : "bg-surface-hover text-muted-foreground",
      )}
    >
      {children}
    </span>
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

function providerModels(
  provider: ModelProvider,
  discovered: Record<string, DiscoveredModel[]>,
  hardware: HardwareSnapshot | null,
): DiscoveredModel[] {
  const fromProvider = discovered[provider.id];
  if (fromProvider) return fromProvider;

  if (!provider.built_in || provider.kind !== "ollama") {
    return [];
  }

  return (
    hardware?.installed_models.map((model) => ({
      name: model.name,
      size: model.size_bytes,
      modified_at: null,
      warnings:
        model.tier === "not_recommended"
          ? ["This model may exceed the practical hardware tier."]
          : [],
      availability: "local" as const,
      ready: true,
      pull_name: model.name,
    })) ?? []
  );
}

function pullKey(providerId: string, model: string): string {
  return `${providerId}\u0000${model.trim()}`;
}

function supportsPull(provider: ModelProvider): boolean {
  if (provider.supports_pull != null) {
    return provider.supports_pull;
  }
  return provider.kind === "ollama" && !isCloudProvider(provider);
}

function isCloudProvider(provider: ModelProvider): boolean {
  if (provider.is_cloud != null) return provider.is_cloud;

  try {
    const hostname = new URL(provider.base_url).hostname.toLowerCase();
    return hostname === "ollama.com" || hostname.endsWith(".ollama.com");
  } catch {
    return false;
  }
}

function suggestCloudReference(model: string): string {
  const clean = model.trim();
  const lower = clean.toLowerCase();
  if (lower.endsWith(":cloud") || lower.endsWith("-cloud")) {
    return clean;
  }
  if (clean.includes(":")) {
    const index = clean.lastIndexOf(":");
    return `${clean.slice(0, index + 1)}${clean.slice(index + 1)}-cloud`;
  }
  return `${clean}:cloud`;
}

function isPulling(state?: PullState): boolean {
  return state?.type === "progress";
}

function toMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function formatBytes(value: number): string {
  if (value >= 1024 ** 3) {
    return `${(value / 1024 ** 3).toFixed(2)} GB`;
  }
  if (value >= 1024 ** 2) {
    return `${(value / 1024 ** 2).toFixed(1)} MB`;
  }
  if (value >= 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${value.toLocaleString("en-US")} bytes`;
}

function formatInteger(
  value: number | null | undefined,
): string {
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
      return "bg-success/10 text-success";
    case "balanced":
    case "maximum_practical":
      return "bg-pending/10 text-pending";
    case "not_recommended":
      return "bg-danger/10 text-danger";
    default:
      return "bg-surface-hover text-muted-foreground";
  }
}

const inputClass =
  "w-full rounded-lg border border-border bg-surface px-3 py-2 text-xs text-foreground outline-none ring-emerald-500/20 focus:border-success/30 focus:ring-4 dark:border-border dark:bg-surface-raised dark:text-foreground";

const secondaryButtonClass =
  "inline-flex cursor-pointer items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs font-medium text-muted-foreground transition hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-50 dark:border-border dark:text-muted-foreground dark:hover:bg-surface-raised";

const primaryButtonClass =
  "inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg bg-surface-raised px-3 py-2 text-xs font-medium text-accent-foreground transition disabled:cursor-not-allowed disabled:opacity-50 dark:bg-surface-hover dark:text-foreground";
