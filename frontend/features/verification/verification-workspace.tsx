"use client";

import Link from "next/link";
import {
  CheckCircle2Icon,
  CircleXIcon,
  Clock3Icon,
  FileWarningIcon,
  Loader2Icon,
  RefreshCwIcon,
  SearchIcon,
  ShieldCheckIcon,
  TerminalIcon,
  TriangleAlertIcon,
  WrenchIcon,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { listProjectTasks } from "@/features/project-tasks/project-task-api";
import type {
  ProjectTask,
  ProjectTaskArtifact,
  ProjectTaskEvent,
} from "@/features/project-tasks/project-task-types";
import { cn } from "@/lib/utils";

type VerificationState =
  | "running"
  | "passed"
  | "failed"
  | "not_started";

export function VerificationWorkspace() {
  const [tasks, setTasks] = useState<ProjectTask[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [stateFilter, setStateFilter] =
    useState<"" | VerificationState>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);

    try {
      const next = (await listProjectTasks(100)).filter(
        (task) =>
          Boolean(task.latest_verification_run_id)
          || ["ready_to_verify", "verifying", "needs_attention", "completed"]
            .includes(task.status),
      );

      setTasks(next);
      setSelectedTaskId((current) => {
        if (current && next.some((task) => task.task_id === current)) {
          return current;
        }
        return next[0]?.task_id ?? null;
      });
      setError(null);
    } catch (requestError) {
      setError(
        toMessage(requestError, "Verification history could not be loaded."),
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const selectedTask =
    tasks.find((task) => task.task_id === selectedTaskId) ?? null;

  const filteredTasks = useMemo(() => {
    const normalized = query.trim().toLowerCase();

    return tasks.filter((task) => {
      const state = deriveVerificationState(task);
      const matchesState = !stateFilter || state === stateFilter;
      const matchesQuery =
        !normalized
        || task.title.toLowerCase().includes(normalized)
        || task.goal.toLowerCase().includes(normalized)
        || (task.verification_profile_id ?? "")
          .toLowerCase()
          .includes(normalized)
        || (task.latest_verification_run_id ?? "")
          .toLowerCase()
          .includes(normalized);

      return matchesState && matchesQuery;
    });
  }, [query, stateFilter, tasks]);

  const counts = useMemo(
    () => ({
      running: tasks.filter(
        (task) => deriveVerificationState(task) === "running",
      ).length,
      passed: tasks.filter(
        (task) => deriveVerificationState(task) === "passed",
      ).length,
      failed: tasks.filter(
        (task) => deriveVerificationState(task) === "failed",
      ).length,
      ready: tasks.filter(
        (task) => deriveVerificationState(task) === "not_started",
      ).length,
    }),
    [tasks],
  );

  return (
    <section className="ai-lab-scrollbar flex min-h-0 flex-1 flex-col overflow-y-auto">
      <div className="mx-auto w-full max-w-7xl space-y-5 p-4 sm:p-6">
        <WorkspaceHeader
          loading={loading}
          onRefresh={() => void refresh()}
        />

        {error ? (
          <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-200">
            <TriangleAlertIcon className="mt-0.5 size-4 shrink-0" />
            <div>
              <p className="font-medium">Verification workspace error</p>
              <p className="mt-1 text-xs opacity-85">{error}</p>
            </div>
          </div>
        ) : null}

        <Summary counts={counts} />

        <div className="grid min-h-[38rem] overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm lg:grid-cols-[20rem_minmax(0,1fr)] dark:border-zinc-800 dark:bg-zinc-950">
          <aside className="flex min-h-0 flex-col border-b border-zinc-200 lg:border-r lg:border-b-0 dark:border-zinc-800">
            <div className="space-y-3 border-b border-zinc-200 p-3 dark:border-zinc-800">
              <label className="relative block">
                <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-3.5 -translate-y-1/2 text-zinc-400" />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search verification"
                  className={inputClass}
                />
              </label>

              <select
                value={stateFilter}
                onChange={(event) =>
                  setStateFilter(
                    event.target.value as "" | VerificationState,
                  )
                }
                className={selectClass}
              >
                <option value="">All states</option>
                <option value="running">Running</option>
                <option value="passed">Passed</option>
                <option value="failed">Failed</option>
                <option value="not_started">Ready / not started</option>
              </select>
            </div>

            <div className="ai-lab-scrollbar max-h-[28rem] space-y-2 overflow-y-auto p-3 lg:max-h-none lg:flex-1">
              {filteredTasks.map((task) => (
                <VerificationListItem
                  key={task.task_id}
                  task={task}
                  selected={task.task_id === selectedTaskId}
                  onSelect={() => setSelectedTaskId(task.task_id)}
                />
              ))}

              {!loading && filteredTasks.length === 0 ? (
                <div className="rounded-xl border border-dashed border-zinc-200 p-6 text-center dark:border-zinc-800">
                  <ShieldCheckIcon className="mx-auto size-6 text-zinc-300 dark:text-zinc-700" />
                  <p className="mt-3 text-xs text-zinc-400">
                    No verification runs match these filters.
                  </p>
                </div>
              ) : null}
            </div>
          </aside>

          <main className="ai-lab-scrollbar min-h-0 overflow-y-auto p-4 sm:p-5">
            {selectedTask ? (
              <VerificationDetails task={selectedTask} />
            ) : (
              <EmptySelection />
            )}
          </main>
        </div>
      </div>
    </section>
  );
}

function WorkspaceHeader({
  loading,
  onRefresh,
}: {
  loading: boolean;
  onRefresh: () => void;
}) {
  return (
    <header className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-600 dark:text-emerald-400">
          Workspace confidence
        </p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-950 dark:text-zinc-50">
          Verification
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
          Track task-linked checks, inspect persisted events and artifacts, and
          identify work that is ready for repair.
        </p>
      </div>

      <button
        type="button"
        onClick={onRefresh}
        disabled={loading}
        className="inline-flex w-fit items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs font-medium text-zinc-700 shadow-sm disabled:opacity-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200"
      >
        <RefreshCwIcon
          className={cn("size-3.5", loading && "animate-spin")}
        />
        Refresh
      </button>
    </header>
  );
}

function Summary({
  counts,
}: {
  counts: {
    running: number;
    passed: number;
    failed: number;
    ready: number;
  };
}) {
  const items = [
    ["Running", counts.running, "sky"],
    ["Passed", counts.passed, "emerald"],
    ["Failed", counts.failed, "red"],
    ["Ready", counts.ready, "amber"],
  ] as const;

  return (
    <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
      {items.map(([label, value, tone]) => (
        <div
          key={label}
          className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-950"
        >
          <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-400">
            {label}
          </p>
          <p
            className={cn(
              "mt-2 text-2xl font-semibold",
              tone === "sky" && "text-sky-600 dark:text-sky-400",
              tone === "emerald" && "text-emerald-600 dark:text-emerald-400",
              tone === "red" && "text-red-600 dark:text-red-400",
              tone === "amber" && "text-amber-600 dark:text-amber-400",
            )}
          >
            {value}
          </p>
        </div>
      ))}
    </div>
  );
}

function VerificationListItem({
  task,
  selected,
  onSelect,
}: {
  task: ProjectTask;
  selected: boolean;
  onSelect: () => void;
}) {
  const state = deriveVerificationState(task);
  const Icon =
    state === "passed"
      ? CheckCircle2Icon
      : state === "failed"
        ? CircleXIcon
        : state === "running"
          ? Loader2Icon
          : Clock3Icon;

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "w-full rounded-xl border p-3 text-left transition",
        selected
          ? "border-emerald-300 bg-emerald-50/70 dark:border-emerald-900 dark:bg-emerald-950/20"
          : "border-zinc-200 bg-white hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-950 dark:hover:border-zinc-700",
      )}
    >
      <div className="flex items-start gap-2">
        <Icon
          className={cn(
            "mt-0.5 size-4 shrink-0",
            state === "running" && "animate-spin text-sky-500",
            state === "passed" && "text-emerald-500",
            state === "failed" && "text-red-500",
            state === "not_started" && "text-amber-500",
          )}
        />

        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-zinc-800 dark:text-zinc-200">
            {task.title}
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className={cn("rounded-full border px-2 py-0.5 text-[9px] font-medium uppercase tracking-wide", verificationStateClass(state))}>
              {formatVerificationState(state)}
            </span>
            <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-[9px] text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
              attempt {task.attempt_count}/{task.max_attempts}
            </span>
          </div>
          <p className="mt-2 truncate font-mono text-[10px] text-zinc-400">
            {task.latest_verification_run_id ?? "No run ID"}
          </p>
        </div>
      </div>
    </button>
  );
}

function VerificationDetails({ task }: { task: ProjectTask }) {
  const state = deriveVerificationState(task);
  const verificationEvents = task.events.filter(isVerificationEvent);
  const verificationArtifacts = task.artifacts.filter(isVerificationArtifact);

  return (
    <div className="space-y-5">
      <header className="flex flex-col gap-4 border-b border-zinc-200 pb-5 sm:flex-row sm:items-start sm:justify-between dark:border-zinc-800">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg font-semibold text-zinc-950 dark:text-zinc-50">
              {task.title}
            </h3>
            <span className={cn("rounded-full border px-2 py-1 text-[9px] font-medium uppercase tracking-wide", verificationStateClass(state))}>
              {formatVerificationState(state)}
            </span>
          </div>
          <p className="mt-2 text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
            {task.goal}
          </p>
        </div>

        <Link
          href="/tasks"
          className="w-fit rounded-lg border border-zinc-200 px-3 py-2 text-xs font-medium text-zinc-600 hover:bg-zinc-50 dark:border-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-900"
        >
          Open task workflow
        </Link>
      </header>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Run ID"
          value={task.latest_verification_run_id ?? "Not started"}
        />
        <MetricCard
          label="Profile"
          value={task.verification_profile_id ?? "Auto / unresolved"}
        />
        <MetricCard
          label="Attempts"
          value={`${task.attempt_count} / ${task.max_attempts}`}
        />
        <MetricCard
          label="Repair task"
          value={task.repair_task_id ?? "None"}
        />
      </div>

      {task.last_error ? (
        <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-200">
          <FileWarningIcon className="mt-0.5 size-4 shrink-0" />
          <div>
            <p className="font-medium">Latest failure</p>
            <p className="mt-1 whitespace-pre-wrap text-xs leading-relaxed opacity-85">
              {task.last_error}
            </p>
          </div>
        </div>
      ) : null}

      <Section
        icon={TerminalIcon}
        title="Verification events"
        description="Persisted task events associated with checks, output, cancellation, and repair."
      >
        {verificationEvents.length > 0 ? (
          <div className="space-y-2">
            {verificationEvents.map((event) => (
              <EventCard key={event.event_id} event={event} />
            ))}
          </div>
        ) : (
          <EmptyPanel message="No verification-specific events are persisted for this task." />
        )}
      </Section>

      <Section
        icon={ShieldCheckIcon}
        title="Verification artifacts"
        description="Structured results and command payloads captured by the task lifecycle."
      >
        {verificationArtifacts.length > 0 ? (
          <div className="space-y-3">
            {verificationArtifacts.map((artifact) => (
              <ArtifactCard
                key={artifact.artifact_id}
                artifact={artifact}
              />
            ))}
          </div>
        ) : (
          <EmptyPanel message="No verification artifacts are attached to this task." />
        )}
      </Section>

      {state === "failed" ? (
        <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs leading-relaxed text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
          <WrenchIcon className="mt-0.5 size-4 shrink-0" />
          <p>
            This task needs attention. Open the task workflow to run the bounded
            repair stream; repair remains task-scoped so it can reuse the failed
            check, frozen context, and current attempt budget.
          </p>
        </div>
      ) : null}
    </div>
  );
}

function Section({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: typeof TerminalIcon;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="flex items-start gap-3">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-zinc-100 text-zinc-500 dark:bg-zinc-900 dark:text-zinc-300">
          <Icon className="size-4" />
        </div>
        <div>
          <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            {title}
          </h4>
          <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
            {description}
          </p>
        </div>
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function EventCard({ event }: { event: ProjectTaskEvent }) {
  return (
    <article className="rounded-xl border border-zinc-200 p-3 dark:border-zinc-800">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-[9px] font-medium uppercase tracking-wide text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
            {event.event_type.replaceAll("_", " ")}
          </span>
          <span className="text-[10px] text-zinc-400">
            {formatTimestamp(event.created_at)}
          </span>
        </div>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-zinc-600 dark:text-zinc-300">
        {event.message}
      </p>
      {Object.keys(event.payload).length > 0 ? (
        <details className="mt-3">
          <summary className="cursor-pointer text-[10px] font-medium text-zinc-400">
            Event payload
          </summary>
          <pre className="ai-lab-scrollbar mt-2 max-h-72 overflow-auto rounded-lg bg-zinc-950 p-3 text-[11px] text-zinc-300">
            {JSON.stringify(event.payload, null, 2)}
          </pre>
        </details>
      ) : null}
    </article>
  );
}

function ArtifactCard({
  artifact,
}: {
  artifact: ProjectTaskArtifact;
}) {
  return (
    <article className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
      <div className="flex flex-wrap items-center justify-between gap-2 bg-zinc-50 px-4 py-3 dark:bg-zinc-900/50">
        <span className="text-xs font-semibold text-zinc-800 dark:text-zinc-200">
          {artifact.artifact_type.replaceAll("_", " ")}
        </span>
        <span className="text-[10px] text-zinc-400">
          {formatTimestamp(artifact.created_at)}
        </span>
      </div>
      <pre className="ai-lab-scrollbar max-h-[30rem] overflow-auto whitespace-pre-wrap break-words bg-zinc-950 p-4 text-[11px] leading-relaxed text-zinc-300">
        {JSON.stringify(artifact.payload, null, 2)}
      </pre>
    </article>
  );
}

function MetricCard({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="min-w-0 rounded-xl border border-zinc-200 bg-zinc-50/60 p-3 dark:border-zinc-800 dark:bg-zinc-900/40">
      <p className="text-[9px] font-medium uppercase tracking-wide text-zinc-400">
        {label}
      </p>
      <p className="mt-2 break-all font-mono text-[11px] font-medium text-zinc-700 dark:text-zinc-200">
        {value}
      </p>
    </div>
  );
}

function EmptyPanel({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-dashed border-zinc-200 p-6 text-center text-xs text-zinc-400 dark:border-zinc-800">
      {message}
    </div>
  );
}

function EmptySelection() {
  return (
    <div className="flex min-h-[30rem] items-center justify-center">
      <div className="max-w-sm text-center">
        <ShieldCheckIcon className="mx-auto size-8 text-zinc-300 dark:text-zinc-700" />
        <p className="mt-4 text-sm font-medium text-zinc-600 dark:text-zinc-300">
          Select a verification record
        </p>
        <p className="mt-2 text-xs leading-relaxed text-zinc-400">
          Check status, task errors, persisted events, and structured artifacts
          will appear here.
        </p>
      </div>
    </div>
  );
}

function deriveVerificationState(
  task: ProjectTask,
): VerificationState {
  if (task.status === "verifying") return "running";
  if (task.status === "completed") return "passed";
  if (task.status === "needs_attention") return "failed";
  return "not_started";
}

function verificationStateClass(
  state: VerificationState,
): string {
  switch (state) {
    case "running":
      return "border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900 dark:bg-sky-950/30 dark:text-sky-300";
    case "passed":
      return "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-300";
    case "failed":
      return "border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300";
    default:
      return "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-300";
  }
}

function formatVerificationState(
  state: VerificationState,
): string {
  return state === "not_started" ? "ready / not started" : state;
}

function isVerificationEvent(event: ProjectTaskEvent): boolean {
  const text = `${event.event_type} ${event.message}`.toLowerCase();
  return [
    "verification",
    "verify",
    "check",
    "repair",
    "cancel",
    "output",
  ].some((token) => text.includes(token));
}

function isVerificationArtifact(
  artifact: ProjectTaskArtifact,
): boolean {
  const type = artifact.artifact_type.toLowerCase();
  return [
    "verification",
    "check",
    "repair",
    "result",
    "output",
  ].some((token) => type.includes(token));
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function toMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

const inputClass =
  "w-full rounded-lg border border-zinc-200 bg-white py-2 pr-3 pl-9 text-xs outline-none ring-emerald-500/20 focus:border-emerald-500 focus:ring-4 dark:border-zinc-800 dark:bg-zinc-900";

const selectClass =
  "w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs outline-none dark:border-zinc-800 dark:bg-zinc-900";
