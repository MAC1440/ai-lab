"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIcon,
  Clock3Icon,
  DatabaseIcon,
  GaugeIcon,
  RefreshCwIcon,
  Trash2Icon,
  TriangleAlertIcon,
} from "lucide-react";

import {
  clearRuntimeMetrics,
  getRuntimeMetrics,
  type RuntimeMetric,
  type RuntimeMetricsSnapshot,
} from "@/features/runtime/runtime-api";
import { cn } from "@/lib/utils";

const stageOptions = [
  "",
  "chat",
  "planning",
  "generation",
  "repair",
];

export function PerformanceDashboard() {
  const [snapshot, setSnapshot] =
    useState<RuntimeMetricsSnapshot | null>(null);
  const [stage, setStage] = useState("");
  const [model, setModel] = useState("");
  const [loading, setLoading] = useState(true);
  const [clearing, setClearing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadMetrics = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await getRuntimeMetrics({
        limit: 100,
        stage: stage || undefined,
        model: model.trim() || undefined,
      });
      setSnapshot(result);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load runtime metrics.",
      );
    } finally {
      setLoading(false);
    }
  }, [model, stage]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadMetrics(), 0);
    return () => window.clearTimeout(timer);
  }, [loadMetrics]);

  const handleClear = async () => {
    if (!window.confirm("Clear all persisted runtime metrics?")) {
      return;
    }

    setClearing(true);
    setError(null);

    try {
      await clearRuntimeMetrics();
      await loadMetrics();
    } catch (clearError) {
      setError(
        clearError instanceof Error
          ? clearError.message
          : "Unable to clear runtime metrics.",
      );
    } finally {
      setClearing(false);
    }
  };

  const summary = snapshot?.summary;
  const history = snapshot?.history ?? [];

  return (
    <section className="ai-lab-scrollbar flex min-h-0 flex-1 flex-col overflow-y-auto">
      <div className="mx-auto w-full max-w-7xl space-y-6 p-4 sm:p-6">
        <header className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-success dark:text-success">
              Runtime telemetry
            </p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-foreground dark:text-foreground">
              Model performance history
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground dark:text-muted-foreground">
              Compare local model speed, response duration, context use,
              and token volume across agent stages.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void loadMetrics()}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-xs font-medium text-foreground shadow-sm transition hover:bg-surface-hover disabled:opacity-50 dark:border-border dark:bg-surface-raised dark:text-foreground dark:hover:bg-surface-hover"
            >
              <RefreshCwIcon
                className={cn("size-3.5", loading && "animate-spin")}
              />
              Refresh
            </button>

            <button
              type="button"
              onClick={() => void handleClear()}
              disabled={clearing || history.length === 0}
              className="inline-flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-xs font-medium text-danger transition hover:bg-danger/10 disabled:opacity-50 dark:border-danger/30 dark:bg-danger/10 dark:text-danger dark:hover:bg-danger/10"
            >
              <Trash2Icon className="size-3.5" />
              Clear history
            </button>
          </div>
        </header>

        {error ? (
          <div className="flex items-start gap-3 rounded-xl border border-pending/30 bg-pending/10 p-4 text-sm text-pending dark:border-pending/30 dark:bg-pending/10 dark:text-pending">
            <TriangleAlertIcon className="mt-0.5 size-4 shrink-0" />
            <div>
              <p className="font-medium">Metrics unavailable</p>
              <p className="mt-1 text-xs opacity-85">{error}</p>
            </div>
          </div>
        ) : null}

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <SummaryCard
            label="Recorded runs"
            value={formatInteger(summary?.run_count)}
            detail={
              snapshot?.persistent
                ? "Persisted in SQLite"
                : "Current process only"
            }
            icon={DatabaseIcon}
          />
          <SummaryCard
            label="Average speed"
            value={formatRate(summary?.average_tokens_per_second)}
            detail="Output tokens per second"
            icon={GaugeIcon}
          />
          <SummaryCard
            label="Average duration"
            value={formatDuration(summary?.average_duration_seconds)}
            detail="End-to-end model runtime"
            icon={Clock3Icon}
          />
          <SummaryCard
            label="Output tokens"
            value={formatInteger(summary?.total_output_tokens)}
            detail={`${formatInteger(summary?.total_input_tokens)} input tokens`}
            icon={ActivityIcon}
          />
        </div>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
          <div className="min-w-0 space-y-6">
            <PerformanceChart history={history} loading={loading} />
            <RuntimeHistoryTable history={history} loading={loading} />
          </div>

          <aside className="space-y-4">
            <div className="rounded-2xl border border-border bg-surface p-4 shadow-sm dark:border-border dark:bg-surface-raised">
              <h3 className="text-sm font-semibold text-foreground dark:text-foreground">
                Filter runs
              </h3>
              <p className="mt-1 text-xs text-muted-foreground dark:text-muted-foreground">
                Filters are applied to persisted history.
              </p>

              <div className="mt-4 space-y-4">
                <label className="block">
                  <span className="text-xs font-medium text-muted-foreground dark:text-muted-foreground">
                    Stage
                  </span>
                  <select
                    value={stage}
                    onChange={(event) => setStage(event.target.value)}
                    className="mt-1.5 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm outline-none ring-emerald-500/20 focus:border-success/30 focus:ring-4 dark:border-border dark:bg-surface-raised"
                  >
                    {stageOptions.map((option) => (
                      <option key={option || "all"} value={option}>
                        {option || "All stages"}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="block">
                  <span className="text-xs font-medium text-muted-foreground dark:text-muted-foreground">
                    Exact model name
                  </span>
                  <input
                    value={model}
                    onChange={(event) => setModel(event.target.value)}
                    placeholder="granite4.1:3b"
                    className="mt-1.5 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm outline-none ring-emerald-500/20 placeholder:text-muted-foreground focus:border-success/30 focus:ring-4 dark:border-border dark:bg-surface-raised"
                  />
                </label>

                <button
                  type="button"
                  onClick={() => {
                    setStage("");
                    setModel("");
                  }}
                  disabled={!stage && !model}
                  className="w-full rounded-lg border border-border px-3 py-2 text-xs font-medium text-muted-foreground transition hover:bg-surface-hover disabled:opacity-40 dark:border-border dark:text-muted-foreground dark:hover:bg-surface-raised"
                >
                  Reset filters
                </button>
              </div>
            </div>

            <LatestRunCard metric={snapshot?.latest ?? null} />
          </aside>
        </div>
      </div>
    </section>
  );
}

function SummaryCard({
  label,
  value,
  detail,
  icon: Icon,
}: {
  label: string;
  value: string;
  detail: string;
  icon: typeof ActivityIcon;
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
      <p className="mt-4 text-2xl font-semibold tracking-tight text-foreground dark:text-foreground">
        {value}
      </p>
      <p className="mt-1 text-[11px] text-muted-foreground">{detail}</p>
    </div>
  );
}

function PerformanceChart({
  history,
  loading,
}: {
  history: RuntimeMetric[];
  loading: boolean;
}) {
  const runs = useMemo(() => history.slice(0, 16).reverse(), [history]);
  const maximum = Math.max(
    1,
    ...runs.map((item) => item.tokens_per_second ?? 0),
  );

  return (
    <div className="rounded-2xl border border-border bg-surface p-4 shadow-sm sm:p-5 dark:border-border dark:bg-surface-raised">
      <div>
        <h3 className="text-sm font-semibold text-foreground dark:text-foreground">
          Output speed
        </h3>
        <p className="mt-1 text-xs text-muted-foreground dark:text-muted-foreground">
          Most recent 16 filtered runs, oldest to newest.
        </p>
      </div>

      <div className="mt-6 flex h-52 items-end gap-2 overflow-hidden rounded-xl border border-border bg-surface-hover/70 px-3 pt-5 dark:border-border dark:bg-surface-raised/40">
        {loading ? (
          <div className="m-auto text-xs text-muted-foreground">
            Loading performance history…
          </div>
        ) : runs.length === 0 ? (
          <div className="m-auto text-center text-xs text-muted-foreground">
            Complete an agent run to populate this chart.
          </div>
        ) : (
          runs.map((item, index) => {
            const speed = item.tokens_per_second ?? 0;
            const height = Math.max(4, (speed / maximum) * 100);

            return (
              <div
                key={`${item.recorded_at}-${index}`}
                className="group flex h-full min-w-0 flex-1 items-end"
                title={`${item.model}: ${formatRate(speed)}`}
              >
                <div
                  className="w-full rounded-t-md bg-success/75 transition group-hover:bg-success"
                  style={{ height: `${height}%` }}
                />
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

function RuntimeHistoryTable({
  history,
  loading,
}: {
  history: RuntimeMetric[];
  loading: boolean;
}) {
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-surface shadow-sm dark:border-border dark:bg-surface-raised">
      <div className="border-b border-border px-4 py-4 sm:px-5 dark:border-border">
        <h3 className="text-sm font-semibold text-foreground dark:text-foreground">
          Run history
        </h3>
        <p className="mt-1 text-xs text-muted-foreground dark:text-muted-foreground">
          Newest runs appear first.
        </p>
      </div>

      <div className="ai-lab-scrollbar overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-xs">
          <thead className="bg-surface-hover text-muted-foreground dark:bg-surface-raised/60 dark:text-muted-foreground">
            <tr>
              <th className="px-4 py-3 font-medium">Recorded</th>
              <th className="px-4 py-3 font-medium">Model</th>
              <th className="px-4 py-3 font-medium">Stage</th>
              <th className="px-4 py-3 text-right font-medium">Speed</th>
              <th className="px-4 py-3 text-right font-medium">Duration</th>
              <th className="px-4 py-3 text-right font-medium">Tokens</th>
              <th className="px-4 py-3 text-right font-medium">Context</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border dark:divide-border">
            {loading ? (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-10 text-center text-muted-foreground"
                >
                  Loading runtime history…
                </td>
              </tr>
            ) : history.length === 0 ? (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-10 text-center text-muted-foreground"
                >
                  No matching runs were found.
                </td>
              </tr>
            ) : (
              history.map((metric) => (
                <tr
                  key={`${metric.recorded_at}-${metric.agent_id}-${metric.stage}`}
                  className="text-foreground hover:bg-surface-hover/70 dark:text-muted-foreground dark:hover:bg-surface-raised/40"
                >
                  <td className="whitespace-nowrap px-4 py-3 text-muted-foreground">
                    {formatTimestamp(metric.recorded_at)}
                  </td>
                  <td className="max-w-48 truncate px-4 py-3 font-medium">
                    {metric.model || "Unknown"}
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-surface-hover px-2 py-1 text-[10px] font-medium text-muted-foreground dark:bg-surface-hover dark:text-muted-foreground">
                      {metric.stage}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right">
                    {formatRate(metric.tokens_per_second)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right">
                    {formatDuration(metric.duration_seconds)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right">
                    {formatInteger(metric.total_tokens)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right">
                    {formatInteger(metric.context_used_tokens)}
                    <span className="text-muted-foreground">
                      {" / "}
                      {formatInteger(metric.context_window)}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function LatestRunCard({
  metric,
}: {
  metric: RuntimeMetric | null;
}) {
  return (
    <div className="rounded-2xl border border-border bg-surface-raised p-4 text-foreground shadow-sm dark:border-border">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-success">
        Latest matching run
      </p>

      {metric ? (
        <dl className="mt-4 space-y-3 text-xs">
          <MetricRow label="Model" value={metric.model || "Unknown"} />
          <MetricRow label="Agent" value={metric.agent_id} />
          <MetricRow label="Stage" value={metric.stage} />
          <MetricRow
            label="Speed"
            value={formatRate(metric.tokens_per_second)}
          />
          <MetricRow
            label="Duration"
            value={formatDuration(metric.duration_seconds)}
          />
          <MetricRow
            label="Temperature"
            value={String(metric.temperature)}
          />
        </dl>
      ) : (
        <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
          No run matches the current filters.
        </p>
      )}
    </div>
  );
}

function MetricRow({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="break-all text-right font-medium text-foreground">
        {value}
      </dd>
    </div>
  );
}

function formatInteger(value: number | null | undefined): string {
  if (value == null) {
    return "—";
  }

  return new Intl.NumberFormat("en-US").format(value);
}

function formatRate(value: number | null | undefined): string {
  if (value == null) {
    return "—";
  }

  return `${value.toFixed(2)} tok/s`;
}

function formatDuration(value: number | null | undefined): string {
  if (value == null) {
    return "—";
  }

  if (value < 1) {
    return `${Math.round(value * 1000)} ms`;
  }

  return `${value.toFixed(2)} s`;
}

function formatTimestamp(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}
