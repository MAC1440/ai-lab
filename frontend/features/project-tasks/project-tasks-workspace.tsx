"use client";

import { useSearchParams } from "next/navigation";
import {
  CheckCircle2Icon,
  CircleDotIcon,
  FolderKanbanIcon,
  Loader2Icon,
  PlusIcon,
  RefreshCwIcon,
  SearchIcon,
  TriangleAlertIcon,
  XIcon,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { getAgentRecommendation } from "@/features/agents/agent-api";
import { rejectChangeSet } from "@/features/changes/change-api";
import {
  cancelProjectTask,
  createProjectTask,
  getProjectTask,
  listProjectTasks,
  resumeProjectTask,
  streamProjectTask,
  streamProjectTaskApprovalAndVerification,
  streamProjectTaskRepair,
} from "@/features/project-tasks/project-task-api";
import { resolveProjectTaskAgentId } from "@/features/project-tasks/project-task-agent.mjs";
import { ProjectTaskDetails } from "@/features/project-tasks/project-task-details";
import type {
  ProjectTask,
  ProjectTaskStatus,
  ProjectTaskStreamEvent,
} from "@/features/project-tasks/project-task-types";
import { cn } from "@/lib/utils";

const POLL_INTERVAL_MS = 3000;
const MAX_LIVE_EVENTS = 80;
const MAX_VERIFICATION_OUTPUT = 80_000;

type ActiveAction = "run" | "verify" | "repair" | "reject" | "cancel";
type AgentId = "coding" | "unity" | "web";

const statusOptions: Array<{
  value: "" | ProjectTaskStatus;
  label: string;
}> = [
  { value: "", label: "All statuses" },
  { value: "queued", label: "Queued" },
  { value: "ready", label: "Ready" },
  { value: "running", label: "Running" },
  { value: "awaiting_approval", label: "Awaiting approval" },
  { value: "ready_to_verify", label: "Ready to verify" },
  { value: "verifying", label: "Verifying" },
  { value: "paused", label: "Paused" },
  { value: "needs_attention", label: "Needs attention" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
];

export function ProjectTasksWorkspace() {
  const searchParams = useSearchParams();
  const [tasks, setTasks] = useState<ProjectTask[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(
    searchParams.get("create") === "1",
  );
  const [title, setTitle] = useState("");
  const [goal, setGoal] = useState("");
  const [agentId, setAgentId] = useState<AgentId>("coding");
  const [agentReason, setAgentReason] = useState(
    "Coding is the safe fallback until workspace detection completes.",
  );
  const [verificationProfileId, setVerificationProfileId] = useState("");
  const [maxAttempts, setMaxAttempts] = useState(3);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] =
    useState<"" | ProjectTaskStatus>("");
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [activeAction, setActiveAction] = useState<{
    taskId: string;
    kind: ActiveAction;
  } | null>(null);
  const [liveEvents, setLiveEvents] = useState<ProjectTaskStreamEvent[]>([]);
  const [verificationOutput, setVerificationOutput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const agentSelectionTouchedRef = useRef(false);

  const selectedTask =
    tasks.find((task) => task.task_id === selectedTaskId) ?? null;

  const filteredTasks = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return tasks.filter((task) => {
      const statusMatches =
        !statusFilter || task.status === statusFilter;
      const queryMatches =
        !normalizedQuery
        || task.title.toLowerCase().includes(normalizedQuery)
        || task.goal.toLowerCase().includes(normalizedQuery)
        || task.agent_id.toLowerCase().includes(normalizedQuery);

      return statusMatches && queryMatches;
    });
  }, [query, statusFilter, tasks]);

  const counts = useMemo(() => {
    const active = tasks.filter((task) =>
      ["queued", "ready", "running", "verifying"].includes(task.status),
    ).length;
    const review = tasks.filter((task) =>
      ["awaiting_approval", "ready_to_verify"].includes(task.status),
    ).length;
    const attention = tasks.filter(
      (task) => task.status === "needs_attention",
    ).length;
    const completed = tasks.filter(
      (task) => task.status === "completed",
    ).length;

    return { active, review, attention, completed };
  }, [tasks]);

  const mergeTask = useCallback((task: ProjectTask) => {
    setTasks((current) => {
      const exists = current.some(
        (item) => item.task_id === task.task_id,
      );
      const next = exists
        ? current.map((item) =>
            item.task_id === task.task_id ? task : item,
          )
        : [task, ...current];

      return next.sort((left, right) =>
        right.updated_at.localeCompare(left.updated_at),
      );
    });
  }, []);

  const refresh = useCallback(async () => {
    try {
      const next = await listProjectTasks();
      setTasks(next);
      setSelectedTaskId((current) => {
        if (current && next.some((task) => task.task_id === current)) {
          return current;
        }
        return next[0]?.task_id ?? null;
      });
      setError(null);
    } catch (requestError) {
      setError(toMessage(requestError, "Project tasks could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();

    void getAgentRecommendation()
      .then((recommendation) => {
        if (agentSelectionTouchedRef.current) return;
        setAgentId(
          resolveProjectTaskAgentId(
            recommendation.agent_id,
          ) as AgentId,
        );
        setAgentReason(recommendation.reason);
      })
      .catch(() => {
        setAgentId("coding");
        setAgentReason(
          "Workspace recommendation was unavailable; Coding is selected as the safe fallback.",
        );
      });
  }, [refresh]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      if (!controllerRef.current) void refresh();
    }, POLL_INTERVAL_MS);

    return () => window.clearInterval(interval);
  }, [refresh]);

  useEffect(
    () => () => {
      controllerRef.current?.abort();
    },
    [],
  );

  function recordEvent(event: ProjectTaskStreamEvent) {
    setLiveEvents((current) =>
      [...current, event].slice(-MAX_LIVE_EVENTS),
    );

    if (event.task) mergeTask(event.task);

    if (event.type === "output" && typeof event.content === "string") {
      setVerificationOutput((current) =>
        (current + event.content).slice(-MAX_VERIFICATION_OUTPUT),
      );
    }

    if (event.type === "verification_done" && event.task) {
      mergeTask(event.task);
    }
  }

  async function consumeStream(
    task: ProjectTask,
    kind: ActiveAction,
    streamFactory: (
      signal: AbortSignal,
    ) => AsyncGenerator<ProjectTaskStreamEvent, void, void>,
  ) {
    if (controllerRef.current) return;

    const controller = new AbortController();
    controllerRef.current = controller;
    setActiveAction({ taskId: task.task_id, kind });
    setSelectedTaskId(task.task_id);
    setLiveEvents([]);
    if (kind === "verify") setVerificationOutput("");
    setError(null);

    try {
      for await (const event of streamFactory(controller.signal)) {
        recordEvent(event);
      }
      mergeTask(await getProjectTask(task.task_id));
    } catch (requestError) {
      const stopped =
        requestError instanceof DOMException
        && requestError.name === "AbortError";

      if (!stopped) {
        setError(toMessage(requestError, "The project task workflow failed."));
        try {
          mergeTask(await getProjectTask(task.task_id));
        } catch {
          // Preserve the stream error as the primary failure.
        }
      }
    } finally {
      controllerRef.current = null;
      setActiveAction(null);
    }
  }

  async function createAndRun() {
    if (!title.trim() || !goal.trim() || activeAction || creating) {
      return;
    }

    setCreating(true);
    setError(null);

    try {
      const task = await createProjectTask({
        title: title.trim(),
        goal: goal.trim(),
        agent_id: agentId,
        verification_profile_id:
          verificationProfileId.trim() || null,
        max_attempts: maxAttempts,
      });

      mergeTask(task);
      setSelectedTaskId(task.task_id);
      setShowCreate(false);
      setTitle("");
      setGoal("");
      setVerificationProfileId("");
      await runTask(task);
    } catch (requestError) {
      setError(toMessage(requestError, "Project task could not be created."));
    } finally {
      setCreating(false);
    }
  }

  async function runTask(task: ProjectTask) {
    let runnable = task;

    if (task.status !== "queued" && task.status !== "ready") {
      try {
        runnable = await resumeProjectTask(task.task_id);
        mergeTask(runnable);
      } catch (requestError) {
        setError(
          toMessage(requestError, "Project task could not be resumed."),
        );
        return;
      }
    }

    const runId = crypto.randomUUID().replaceAll("-", "");
    await consumeStream(runnable, "run", (signal) =>
      streamProjectTask(runnable.task_id, runId, signal),
    );
  }

  async function approveAndVerify(task: ProjectTask) {
    const applying = task.status === "awaiting_approval";

    if (
      applying
      && !window.confirm(
        `Apply all ${task.proposal_count} reviewed file changes and immediately run verification?`,
      )
    ) {
      return;
    }

    await consumeStream(task, "verify", (signal) =>
      streamProjectTaskApprovalAndVerification(task.task_id, signal),
    );
  }

  async function repairTask(task: ProjectTask) {
    const runId = crypto.randomUUID().replaceAll("-", "");
    await consumeStream(task, "repair", (signal) =>
      streamProjectTaskRepair(task.task_id, runId, signal),
    );
  }

  async function rejectTask(task: ProjectTask) {
    if (
      !task.current_change_set_id
      || !window.confirm("Reject this complete change set?")
    ) {
      return;
    }

    setActiveAction({ taskId: task.task_id, kind: "reject" });
    setError(null);

    try {
      await rejectChangeSet(task.current_change_set_id);
      mergeTask(await getProjectTask(task.task_id));
    } catch (requestError) {
      setError(toMessage(requestError, "The change set could not be rejected."));
    } finally {
      setActiveAction(null);
    }
  }

  async function cancelTask(task: ProjectTask) {
    setActiveAction({ taskId: task.task_id, kind: "cancel" });
    controllerRef.current?.abort();

    try {
      mergeTask(await cancelProjectTask(task.task_id));
    } catch (requestError) {
      setError(
        toMessage(requestError, "Project task could not be cancelled."),
      );
    } finally {
      controllerRef.current = null;
      setActiveAction(null);
    }
  }

  return (
    <section className="flex min-h-0 flex-1 flex-col">
      <div className="border-b border-zinc-200 bg-white px-4 py-4 dark:border-zinc-800 dark:bg-zinc-950 sm:px-6">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-600 dark:text-emerald-400">
              Deterministic coding workflow
            </p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-950 dark:text-zinc-50">
              Project tasks
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
              Plan, freeze project context, generate a reviewable change set,
              apply it deliberately, verify the workspace, and repair bounded
              failures.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setShowCreate((current) => !current)}
              disabled={Boolean(activeAction) || creating}
              className="inline-flex items-center gap-2 rounded-lg bg-zinc-900 px-3 py-2 text-xs font-medium text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
            >
              {showCreate ? (
                <XIcon className="size-3.5" />
              ) : (
                <PlusIcon className="size-3.5" />
              )}
              {showCreate ? "Close form" : "New task"}
            </button>

            <button
              type="button"
              onClick={() => {
                setLoading(true);
                void refresh();
              }}
              disabled={loading || Boolean(activeAction)}
              className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs font-medium text-zinc-700 shadow-sm disabled:opacity-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200"
            >
              <RefreshCwIcon
                className={cn("size-3.5", loading && "animate-spin")}
              />
              Refresh
            </button>
          </div>
        </div>
      </div>

      <div className="ai-lab-scrollbar min-h-0 flex-1 overflow-y-auto bg-zinc-50/50 dark:bg-zinc-950">
        <div className="mx-auto w-full max-w-7xl space-y-4 p-4 sm:p-6">
          {error ? (
            <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-200">
              <TriangleAlertIcon className="mt-0.5 size-4 shrink-0" />
              <div>
                <p className="font-medium">Task workflow error</p>
                <p className="mt-1 text-xs opacity-85">{error}</p>
              </div>
            </div>
          ) : null}

          <TaskSummary counts={counts} />

          {showCreate ? (
            <CreateTaskPanel
              title={title}
              goal={goal}
              agentId={agentId}
              agentReason={agentReason}
              verificationProfileId={verificationProfileId}
              maxAttempts={maxAttempts}
              creating={creating}
              blocked={Boolean(activeAction)}
              onTitleChange={setTitle}
              onGoalChange={setGoal}
              onAgentChange={(value) => {
                agentSelectionTouchedRef.current = true;
                setAgentId(value);
                setAgentReason("Selected manually for this task.");
              }}
              onVerificationProfileChange={setVerificationProfileId}
              onMaxAttemptsChange={setMaxAttempts}
              onSubmit={() => void createAndRun()}
            />
          ) : null}

          <div className="grid min-h-[36rem] overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm lg:grid-cols-[19rem_minmax(0,1fr)] dark:border-zinc-800 dark:bg-zinc-950">
            <aside className="flex min-h-0 flex-col border-b border-zinc-200 lg:border-r lg:border-b-0 dark:border-zinc-800">
              <div className="space-y-3 border-b border-zinc-200 p-3 dark:border-zinc-800">
                <label className="relative block">
                  <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-3.5 -translate-y-1/2 text-zinc-400" />
                  <input
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Search tasks"
                    className="w-full rounded-lg border border-zinc-200 bg-white py-2 pr-3 pl-9 text-xs outline-none ring-emerald-500/20 focus:border-emerald-500 focus:ring-4 dark:border-zinc-800 dark:bg-zinc-900"
                  />
                </label>

                <select
                  value={statusFilter}
                  onChange={(event) =>
                    setStatusFilter(
                      event.target.value as "" | ProjectTaskStatus,
                    )
                  }
                  className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs outline-none dark:border-zinc-800 dark:bg-zinc-900"
                >
                  {statusOptions.map((option) => (
                    <option key={option.value || "all"} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="ai-lab-scrollbar max-h-[26rem] space-y-2 overflow-y-auto p-3 lg:max-h-none lg:flex-1">
                {filteredTasks.map((task) => (
                  <TaskListItem
                    key={task.task_id}
                    task={task}
                    selected={selectedTaskId === task.task_id}
                    active={
                      activeAction?.taskId === task.task_id
                    }
                    onSelect={() => {
                      setSelectedTaskId(task.task_id);
                      setLiveEvents([]);
                      setVerificationOutput("");
                    }}
                  />
                ))}

                {!loading && filteredTasks.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-zinc-200 p-6 text-center dark:border-zinc-800">
                    <FolderKanbanIcon className="mx-auto size-5 text-zinc-300 dark:text-zinc-700" />
                    <p className="mt-3 text-xs text-zinc-400">
                      {tasks.length === 0
                        ? "No project tasks yet."
                        : "No tasks match these filters."}
                    </p>
                  </div>
                ) : null}
              </div>
            </aside>

            <main className="ai-lab-scrollbar min-h-0 overflow-y-auto p-4 sm:p-5">
              {selectedTask ? (
                <ProjectTaskDetails
                  task={selectedTask}
                  liveEvents={
                    activeAction?.taskId === selectedTask.task_id
                      ? liveEvents
                      : []
                  }
                  verificationOutput={
                    selectedTaskId === selectedTask.task_id
                      ? verificationOutput
                      : ""
                  }
                  action={
                    activeAction?.taskId === selectedTask.task_id
                      ? activeAction.kind
                      : null
                  }
                  onRun={(task) => void runTask(task)}
                  onApproveAndVerify={(task) =>
                    void approveAndVerify(task)
                  }
                  onReject={(task) => void rejectTask(task)}
                  onRepair={(task) => void repairTask(task)}
                  onCancel={(task) => void cancelTask(task)}
                />
              ) : (
                <div className="flex min-h-[28rem] items-center justify-center">
                  <div className="max-w-sm text-center">
                    <FolderKanbanIcon className="mx-auto size-8 text-zinc-300 dark:text-zinc-700" />
                    <p className="mt-4 text-sm font-medium text-zinc-600 dark:text-zinc-300">
                      Select or create a project task
                    </p>
                    <p className="mt-2 text-xs leading-relaxed text-zinc-400">
                      Tasks keep planning, context, file changes, verification,
                      and repair in one reviewable lifecycle.
                    </p>
                  </div>
                </div>
              )}
            </main>
          </div>
        </div>
      </div>
    </section>
  );
}

function TaskSummary({
  counts,
}: {
  counts: {
    active: number;
    review: number;
    attention: number;
    completed: number;
  };
}) {
  const cards = [
    { label: "Active", value: counts.active, tone: "sky" },
    { label: "Needs review", value: counts.review, tone: "amber" },
    { label: "Needs attention", value: counts.attention, tone: "red" },
    { label: "Completed", value: counts.completed, tone: "emerald" },
  ] as const;

  return (
    <div className="grid gap-3 grid-cols-2 xl:grid-cols-4">
      {cards.map((card) => (
        <div
          key={card.label}
          className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-950"
        >
          <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-400">
            {card.label}
          </p>
          <p
            className={cn(
              "mt-2 text-2xl font-semibold",
              card.tone === "sky" && "text-sky-600 dark:text-sky-400",
              card.tone === "amber" && "text-amber-600 dark:text-amber-400",
              card.tone === "red" && "text-red-600 dark:text-red-400",
              card.tone === "emerald"
                && "text-emerald-600 dark:text-emerald-400",
            )}
          >
            {card.value}
          </p>
        </div>
      ))}
    </div>
  );
}

function CreateTaskPanel({
  title,
  goal,
  agentId,
  agentReason,
  verificationProfileId,
  maxAttempts,
  creating,
  blocked,
  onTitleChange,
  onGoalChange,
  onAgentChange,
  onVerificationProfileChange,
  onMaxAttemptsChange,
  onSubmit,
}: {
  title: string;
  goal: string;
  agentId: AgentId;
  agentReason: string;
  verificationProfileId: string;
  maxAttempts: number;
  creating: boolean;
  blocked: boolean;
  onTitleChange: (value: string) => void;
  onGoalChange: (value: string) => void;
  onAgentChange: (value: AgentId) => void;
  onVerificationProfileChange: (value: string) => void;
  onMaxAttemptsChange: (value: number) => void;
  onSubmit: () => void;
}) {
  return (
    <section className="rounded-2xl border border-emerald-200 bg-white p-4 shadow-sm sm:p-5 dark:border-emerald-900/60 dark:bg-zinc-950">
      <div>
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
          Create a bounded project task
        </h3>
        <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
          State the expected behavior, constraints, files or systems involved,
          and acceptance criteria. The task will start immediately.
        </p>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="space-y-4">
          <Field label="Task title">
            <input
              value={title}
              onChange={(event) => onTitleChange(event.target.value)}
              placeholder="Add an inventory pickup system"
              maxLength={160}
              className={inputClass}
            />
          </Field>

          <Field label="Bounded goal">
            <textarea
              value={goal}
              onChange={(event) => onGoalChange(event.target.value)}
              placeholder="Describe expected behavior, constraints, affected areas, and acceptance criteria."
              rows={6}
              maxLength={12_000}
              className={cn(inputClass, "resize-y")}
            />
          </Field>
        </div>

        <div className="space-y-4">
          <Field label="Agent">
            <select
              value={agentId}
              onChange={(event) =>
                onAgentChange(event.target.value as AgentId)
              }
              className={inputClass}
            >
              <option value="coding">Coding</option>
              <option value="unity">Unity</option>
              <option value="web">Web</option>
            </select>
            <p className="mt-2 text-[11px] leading-relaxed text-zinc-400">
              {agentReason}
            </p>
          </Field>

          <Field label="Verification profile ID">
            <input
              value={verificationProfileId}
              onChange={(event) =>
                onVerificationProfileChange(event.target.value)
              }
              placeholder="Optional"
              className={inputClass}
            />
          </Field>

          <Field label="Maximum attempts">
            <select
              value={maxAttempts}
              onChange={(event) =>
                onMaxAttemptsChange(Number(event.target.value))
              }
              className={inputClass}
            >
              {[1, 2, 3, 4, 5].map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </Field>

          <button
            type="button"
            onClick={onSubmit}
            disabled={
              !title.trim()
              || !goal.trim()
              || blocked
              || creating
            }
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-500 px-4 py-2.5 text-xs font-semibold text-emerald-950 disabled:opacity-50"
          >
            {creating ? (
              <Loader2Icon className="size-4 animate-spin" />
            ) : (
              <PlusIcon className="size-4" />
            )}
            {creating ? "Creating…" : "Create and run"}
          </button>
        </div>
      </div>
    </section>
  );
}

function TaskListItem({
  task,
  selected,
  active,
  onSelect,
}: {
  task: ProjectTask;
  selected: boolean;
  active: boolean;
  onSelect: () => void;
}) {
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
        {task.status === "completed" ? (
          <CheckCircle2Icon className="mt-0.5 size-4 shrink-0 text-emerald-500" />
        ) : active ? (
          <Loader2Icon className="mt-0.5 size-4 shrink-0 animate-spin text-sky-500" />
        ) : (
          <CircleDotIcon className="mt-0.5 size-4 shrink-0 text-zinc-400" />
        )}

        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-zinc-800 dark:text-zinc-200">
            {task.title}
          </p>

          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <span className={cn("rounded-full border px-2 py-0.5 text-[9px] font-medium uppercase tracking-wide", statusClass(task.status))}>
              {task.status.replaceAll("_", " ")}
            </span>
            <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-[9px] text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
              {task.agent_id}
            </span>
          </div>

          <p className="mt-2 truncate text-[10px] text-zinc-400">
            {task.phase.replaceAll("_", " ")} · attempt {task.attempt_count}/
            {task.max_attempts}
          </p>
        </div>
      </div>
    </button>
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

const inputClass =
  "w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-800 outline-none ring-emerald-500/20 placeholder:text-zinc-400 focus:border-emerald-500 focus:ring-4 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200";

function statusClass(status: ProjectTaskStatus): string {
  switch (status) {
    case "completed":
      return "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-300";
    case "running":
    case "verifying":
      return "border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900 dark:bg-sky-950/30 dark:text-sky-300";
    case "awaiting_approval":
    case "ready_to_verify":
      return "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-300";
    case "needs_attention":
      return "border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300";
    case "cancelled":
      return "border-zinc-200 bg-zinc-100 text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-400";
    default:
      return "border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-900 dark:bg-violet-950/30 dark:text-violet-300";
  }
}

function toMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}
