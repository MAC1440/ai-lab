"use client";

import Link from "next/link";
import {
  CheckCircle2Icon,
  FileDiffIcon,
  FilePlus2Icon,
  FileX2Icon,
  FolderPenIcon,
  RefreshCwIcon,
  SearchIcon,
  ShieldAlertIcon,
  Trash2Icon,
  TriangleAlertIcon,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { rejectChangeSet } from "@/features/changes/change-api";
import {
  getProjectTask,
  listProjectTasks,
} from "@/features/project-tasks/project-task-api";
import type { ProjectTask } from "@/features/project-tasks/project-task-types";
import { cn } from "@/lib/utils";

type ChangeState = "review" | "applied" | "rejected" | "attention";

export function ChangesWorkspace() {
  const [tasks, setTasks] = useState<ProjectTask[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [stateFilter, setStateFilter] = useState<"" | ChangeState>("");
  const [loading, setLoading] = useState(true);
  const [rejecting, setRejecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const next = (await listProjectTasks(100)).filter(
        (task) =>
          Boolean(task.current_change_set_id)
          || task.proposal_count > 0
          || task.proposals.length > 0,
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
      setError(toMessage(requestError, "Change sets could not be loaded."));
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
      const state = deriveChangeState(task);
      const matchesState = !stateFilter || state === stateFilter;
      const matchesQuery =
        !normalized
        || task.title.toLowerCase().includes(normalized)
        || task.goal.toLowerCase().includes(normalized)
        || (task.current_change_set_id ?? "")
          .toLowerCase()
          .includes(normalized)
        || task.proposals.some((proposal) =>
          proposalSearchText(proposal).includes(normalized),
        );

      return matchesState && matchesQuery;
    });
  }, [query, stateFilter, tasks]);

  const counts = useMemo(
    () => ({
      review: tasks.filter((task) => deriveChangeState(task) === "review").length,
      applied: tasks.filter((task) => deriveChangeState(task) === "applied").length,
      rejected: tasks.filter((task) => deriveChangeState(task) === "rejected").length,
      attention: tasks.filter((task) => deriveChangeState(task) === "attention").length,
    }),
    [tasks],
  );

  async function rejectSelected() {
    if (
      !selectedTask?.current_change_set_id
      || !window.confirm("Reject this complete change set?")
    ) {
      return;
    }

    setRejecting(true);
    setError(null);
    setNotice(null);

    try {
      await rejectChangeSet(selectedTask.current_change_set_id);
      const updated = await getProjectTask(selectedTask.task_id);
      setTasks((current) =>
        current.map((task) =>
          task.task_id === updated.task_id ? updated : task,
        ),
      );
      setNotice("The change set was rejected.");
    } catch (requestError) {
      setError(toMessage(requestError, "The change set could not be rejected."));
    } finally {
      setRejecting(false);
    }
  }

  return (
    <section className="ai-lab-scrollbar flex min-h-0 flex-1 flex-col overflow-y-auto">
      <div className="mx-auto w-full max-w-7xl space-y-5 p-4 sm:p-6">
        <WorkspaceHeader
          loading={loading}
          onRefresh={() => void refresh()}
        />

        {error ? (
          <Banner
            tone="error"
            title="Changes workspace error"
            message={error}
          />
        ) : null}

        {notice ? (
          <Banner
            tone="success"
            title="Change set updated"
            message={notice}
          />
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
                  placeholder="Search changes"
                  className={inputClass}
                />
              </label>

              <select
                value={stateFilter}
                onChange={(event) =>
                  setStateFilter(event.target.value as "" | ChangeState)
                }
                className={selectClass}
              >
                <option value="">All states</option>
                <option value="review">Needs review</option>
                <option value="applied">Applied</option>
                <option value="rejected">Rejected</option>
                <option value="attention">Needs attention</option>
              </select>
            </div>

            <div className="ai-lab-scrollbar max-h-[28rem] space-y-2 overflow-y-auto p-3 lg:max-h-none lg:flex-1">
              {filteredTasks.map((task) => (
                <ChangeSetListItem
                  key={task.task_id}
                  task={task}
                  selected={task.task_id === selectedTaskId}
                  onSelect={() => setSelectedTaskId(task.task_id)}
                />
              ))}

              {!loading && filteredTasks.length === 0 ? (
                <div className="rounded-xl border border-dashed border-zinc-200 p-6 text-center dark:border-zinc-800">
                  <FileDiffIcon className="mx-auto size-6 text-zinc-300 dark:text-zinc-700" />
                  <p className="mt-3 text-xs text-zinc-400">
                    No change sets match these filters.
                  </p>
                </div>
              ) : null}
            </div>
          </aside>

          <main className="ai-lab-scrollbar min-h-0 overflow-y-auto p-4 sm:p-5">
            {selectedTask ? (
              <ChangeSetDetails
                task={selectedTask}
                rejecting={rejecting}
                onReject={() => void rejectSelected()}
              />
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
          Reviewable file operations
        </p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-950 dark:text-zinc-50">
          Changes
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
          Inspect task-linked file operations before applying them. Approval
          remains inside the task lifecycle so application and verification
          happen together.
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
  counts: Record<ChangeState, number>;
}) {
  const items = [
    ["Needs review", counts.review, "amber"],
    ["Applied", counts.applied, "emerald"],
    ["Rejected", counts.rejected, "zinc"],
    ["Needs attention", counts.attention, "red"],
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
              tone === "amber" && "text-amber-600 dark:text-amber-400",
              tone === "emerald" && "text-emerald-600 dark:text-emerald-400",
              tone === "zinc" && "text-zinc-500",
              tone === "red" && "text-red-600 dark:text-red-400",
            )}
          >
            {value}
          </p>
        </div>
      ))}
    </div>
  );
}

function ChangeSetListItem({
  task,
  selected,
  onSelect,
}: {
  task: ProjectTask;
  selected: boolean;
  onSelect: () => void;
}) {
  const state = deriveChangeState(task);

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
        <FileDiffIcon className="mt-0.5 size-4 shrink-0 text-zinc-400" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-zinc-800 dark:text-zinc-200">
            {task.title}
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className={cn("rounded-full border px-2 py-0.5 text-[9px] font-medium uppercase tracking-wide", changeStateClass(state))}>
              {state.replaceAll("_", " ")}
            </span>
            <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-[9px] text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
              {task.proposal_count} file{task.proposal_count === 1 ? "" : "s"}
            </span>
          </div>
          <p className="mt-2 truncate font-mono text-[10px] text-zinc-400">
            {task.current_change_set_id ?? "Historical task-linked changes"}
          </p>
        </div>
      </div>
    </button>
  );
}

function ChangeSetDetails({
  task,
  rejecting,
  onReject,
}: {
  task: ProjectTask;
  rejecting: boolean;
  onReject: () => void;
}) {
  const state = deriveChangeState(task);

  return (
    <div className="space-y-5">
      <header className="flex flex-col gap-4 border-b border-zinc-200 pb-5 sm:flex-row sm:items-start sm:justify-between dark:border-zinc-800">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg font-semibold text-zinc-950 dark:text-zinc-50">
              {task.title}
            </h3>
            <span className={cn("rounded-full border px-2 py-1 text-[9px] font-medium uppercase tracking-wide", changeStateClass(state))}>
              {state.replaceAll("_", " ")}
            </span>
          </div>
          <p className="mt-2 text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
            {task.goal}
          </p>
          <p className="mt-3 break-all font-mono text-[10px] text-zinc-400">
            Change set: {task.current_change_set_id ?? "not currently active"}
          </p>
        </div>

        <div className="flex shrink-0 flex-wrap gap-2">
          <Link
            href={`/tasks`}
            className="rounded-lg border border-zinc-200 px-3 py-2 text-xs font-medium text-zinc-600 hover:bg-zinc-50 dark:border-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-900"
          >
            Open task
          </Link>

          {task.current_change_set_id && state === "review" ? (
            <button
              type="button"
              onClick={onReject}
              disabled={rejecting}
              className="inline-flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs font-medium text-red-700 disabled:opacity-50 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300"
            >
              <Trash2Icon className="size-3.5" />
              {rejecting ? "Rejecting…" : "Reject set"}
            </button>
          ) : null}
        </div>
      </header>

      {task.last_error ? (
        <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-200">
          <ShieldAlertIcon className="mt-0.5 size-4 shrink-0" />
          <div>
            <p className="font-medium">Task error</p>
            <p className="mt-1 text-xs leading-relaxed opacity-85">
              {task.last_error}
            </p>
          </div>
        </div>
      ) : null}

      <div>
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            Proposed operations
          </h4>
          <span className="text-xs text-zinc-400">
            {task.proposals.length} proposal{task.proposals.length === 1 ? "" : "s"}
          </span>
        </div>

        <div className="mt-3 space-y-3">
          {task.proposals.map((proposal, index) => (
            <ProposalCard
              key={proposalKey(proposal, index)}
              proposal={proposal}
              index={index}
            />
          ))}

          {task.proposals.length === 0 ? (
            <div className="rounded-xl border border-dashed border-zinc-200 p-8 text-center text-xs text-zinc-400 dark:border-zinc-800">
              This task records a change-set relationship but no proposal
              payload is currently attached.
            </div>
          ) : null}
        </div>
      </div>

      <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-4 text-xs leading-relaxed text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
        Apply is intentionally performed from the task workspace. That keeps
        file application, verification profile selection, streamed checks, and
        repair state in one atomic workflow.
      </div>
    </div>
  );
}

function ProposalCard({
  proposal,
  index,
}: {
  proposal: ProjectTask["proposals"][number];
  index: number;
}) {
  const record = proposal as unknown as Record<string, unknown>;
  const operation = firstString(
    record.operation,
    record.operation_type,
    record.action,
    "change",
  );
  const path = firstString(
    record.file_path,
    record.path,
    record.destination_path,
    `Proposal ${index + 1}`,
  );
  const summary = firstString(
    record.summary,
    record.reason,
    record.description,
    "No summary provided.",
  );
  const oldText = firstString(record.old_text, record.before, "");
  const newText = firstString(record.new_text, record.content, record.after, "");

  const Icon =
    operation === "create"
      ? FilePlus2Icon
      : operation === "delete"
        ? FileX2Icon
        : FolderPenIcon;

  return (
    <article className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
      <div className="flex items-start gap-3 bg-zinc-50 px-4 py-3 dark:bg-zinc-900/50">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-white text-zinc-500 shadow-sm dark:bg-zinc-950">
          <Icon className="size-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="break-all font-mono text-xs font-medium text-zinc-800 dark:text-zinc-200">
              {path}
            </p>
            <span className="rounded-full bg-zinc-200 px-2 py-0.5 text-[9px] font-medium uppercase text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
              {operation}
            </span>
          </div>
          <p className="mt-1 text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">
            {summary}
          </p>
        </div>
      </div>

      {(oldText || newText) ? (
        <div className="grid gap-px bg-zinc-200 md:grid-cols-2 dark:bg-zinc-800">
          <CodePane label="Before" content={oldText || "—"} />
          <CodePane label="After" content={newText || "—"} />
        </div>
      ) : (
        <details className="px-4 py-3">
          <summary className="cursor-pointer text-xs font-medium text-zinc-500">
            Raw proposal data
          </summary>
          <pre className="ai-lab-scrollbar mt-3 max-h-80 overflow-auto rounded-lg bg-zinc-950 p-3 text-[11px] text-zinc-300">
            {JSON.stringify(proposal, null, 2)}
          </pre>
        </details>
      )}
    </article>
  );
}

function CodePane({
  label,
  content,
}: {
  label: string;
  content: string;
}) {
  return (
    <div className="min-w-0 bg-white p-3 dark:bg-zinc-950">
      <p className="text-[9px] font-medium uppercase tracking-wide text-zinc-400">
        {label}
      </p>
      <pre className="ai-lab-scrollbar mt-2 max-h-72 overflow-auto whitespace-pre-wrap break-words font-mono text-[11px] leading-relaxed text-zinc-600 dark:text-zinc-300">
        {content}
      </pre>
    </div>
  );
}

function Banner({
  tone,
  title,
  message,
}: {
  tone: "error" | "success";
  title: string;
  message: string;
}) {
  const Icon = tone === "error" ? TriangleAlertIcon : CheckCircle2Icon;

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

function EmptySelection() {
  return (
    <div className="flex min-h-[30rem] items-center justify-center">
      <div className="max-w-sm text-center">
        <FileDiffIcon className="mx-auto size-8 text-zinc-300 dark:text-zinc-700" />
        <p className="mt-4 text-sm font-medium text-zinc-600 dark:text-zinc-300">
          Select a change set
        </p>
        <p className="mt-2 text-xs leading-relaxed text-zinc-400">
          Task-linked proposals, file operations, and validation context will
          appear here.
        </p>
      </div>
    </div>
  );
}

function deriveChangeState(task: ProjectTask): ChangeState {
  if (task.status === "needs_attention") return "attention";
  if (task.status === "awaiting_approval") return "review";
  if (task.status === "cancelled" && !task.current_change_set_id) {
    return "rejected";
  }
  if (
    ["ready_to_verify", "verifying", "completed"].includes(task.status)
  ) {
    return "applied";
  }
  return task.current_change_set_id ? "review" : "rejected";
}

function changeStateClass(state: ChangeState): string {
  switch (state) {
    case "review":
      return "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-300";
    case "applied":
      return "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-300";
    case "attention":
      return "border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300";
    default:
      return "border-zinc-200 bg-zinc-100 text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-400";
  }
}

function proposalKey(
  proposal: ProjectTask["proposals"][number],
  index: number,
): string {
  const record = proposal as unknown as Record<string, unknown>;
  return firstString(
    record.proposal_id,
    record.id,
    record.file_path,
    record.path,
    String(index),
  );
}

function proposalSearchText(
  proposal: ProjectTask["proposals"][number],
): string {
  try {
    return JSON.stringify(proposal).toLowerCase();
  } catch {
    return "";
  }
}

function firstString(...values: unknown[]): string {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) return value;
  }
  return "";
}

function toMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

const inputClass =
  "w-full rounded-lg border border-zinc-200 bg-white py-2 pr-3 pl-9 text-xs outline-none ring-emerald-500/20 focus:border-emerald-500 focus:ring-4 dark:border-zinc-800 dark:bg-zinc-900";

const selectClass =
  "w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs outline-none dark:border-zinc-800 dark:bg-zinc-900";
