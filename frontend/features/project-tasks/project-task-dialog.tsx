"use client";

import {
  CheckCircle2Icon,
  CircleDotIcon,
  ListTodoIcon,
  Loader2Icon,
  PlusIcon,
  RefreshCwIcon,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
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
  ProjectTaskStreamEvent,
} from "@/features/project-tasks/project-task-types";
import { cn } from "@/lib/utils";

const POLL_INTERVAL_MS = 3000;
const MAX_LIVE_EVENTS = 80;
const MAX_VERIFICATION_OUTPUT = 80_000;

type ActiveAction = "run" | "verify" | "repair" | "reject" | "cancel";

function taskBadgeClass(task: ProjectTask) {
  return cn(
    "border text-[9px] uppercase tracking-wide",
    task.status === "completed" &&
      "border-emerald-900 bg-emerald-950 text-emerald-300",
    (task.status === "running" || task.status === "verifying") &&
      "border-sky-900 bg-sky-950 text-sky-300",
    task.status === "awaiting_approval" &&
      "border-amber-900 bg-amber-950 text-amber-300",
    task.status === "needs_attention" &&
      "border-red-900 bg-red-950 text-red-300",
  );
}

export function ProjectTaskDialog({ disabled = false }: { disabled?: boolean }) {
  const [open, setOpen] = useState(false);
  const [tasks, setTasks] = useState<ProjectTask[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(true);
  const [title, setTitle] = useState("");
  const [goal, setGoal] = useState("");
  const [agentId, setAgentId] = useState<"unity" | "coding" | "web">("coding");
  const [agentReason, setAgentReason] = useState(
    "Coding is the safe fallback until the workspace recommendation loads.",
  );
  const [loading, setLoading] = useState(false);
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

  const mergeTask = useCallback((task: ProjectTask) => {
    setTasks((current) => {
      const exists = current.some((item) => item.task_id === task.task_id);
      const next = exists
        ? current.map((item) => (item.task_id === task.task_id ? task : item))
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
      setSelectedTaskId((current) => current ?? next[0]?.task_id ?? null);
      setError(null);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Project tasks could not be loaded.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    const interval = window.setInterval(() => {
      if (!controllerRef.current) void refresh();
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [open, refresh]);

  useEffect(
    () => () => {
      controllerRef.current?.abort();
    },
    [],
  );

  function handleOpenChange(nextOpen: boolean) {
    if (nextOpen) {
      agentSelectionTouchedRef.current = false;
      setLoading(true);
      void refresh();
      void getAgentRecommendation()
        .then((recommendation) => {
          if (agentSelectionTouchedRef.current) return;
          setAgentId(
            resolveProjectTaskAgentId(
              recommendation.agent_id,
            ) as typeof agentId,
          );
          setAgentReason(recommendation.reason);
        })
        .catch(() => {
          setAgentId("coding");
          setAgentReason(
            "Workspace recommendation was unavailable; Coding is selected as the safe fallback.",
          );
        });
    } else {
      controllerRef.current?.abort();
      controllerRef.current = null;
      setActiveAction(null);
    }
    setOpen(nextOpen);
  }

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
        requestError instanceof DOMException &&
        requestError.name === "AbortError";
      if (!stopped) {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "The project task workflow failed.",
        );
        try {
          mergeTask(await getProjectTask(task.task_id));
        } catch {
          // Keep the stream error as the primary failure.
        }
      }
    } finally {
      controllerRef.current = null;
      setActiveAction(null);
    }
  }

  async function createAndRun() {
    if (!title.trim() || !goal.trim() || activeAction || creating) return;
    setCreating(true);
    setError(null);
    try {
      const task = await createProjectTask({
        title: title.trim(),
        goal: goal.trim(),
        agent_id: agentId,
      });
      mergeTask(task);
      setSelectedTaskId(task.task_id);
      setShowCreate(false);
      setTitle("");
      setGoal("");
      await runTask(task);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Project task could not be created.",
      );
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
          requestError instanceof Error
            ? requestError.message
            : "Project task could not be resumed.",
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
      applying &&
      !window.confirm(
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
      !task.current_change_set_id ||
      !window.confirm("Reject this complete change set?")
    ) {
      return;
    }
    setActiveAction({ taskId: task.task_id, kind: "reject" });
    setError(null);
    try {
      await rejectChangeSet(task.current_change_set_id);
      mergeTask(await getProjectTask(task.task_id));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The change set could not be rejected.",
      );
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
        requestError instanceof Error
          ? requestError.message
          : "Project task could not be cancelled.",
      );
    } finally {
      controllerRef.current = null;
      setActiveAction(null);
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" size="sm" disabled={disabled}>
          <ListTodoIcon className="size-4" />
          Tasks
        </Button>
      </DialogTrigger>
      <DialogContent className="h-[92vh] max-h-[92vh] max-w-[96vw] overflow-hidden p-0 xl:max-w-7xl">
        <div className="flex h-full min-h-0 flex-col">
          <header className="flex items-start justify-between gap-4 border-b border-zinc-800 px-5 py-4 pr-12">
            <div>
              <DialogTitle>Production project tasks</DialogTitle>
              <DialogDescription>
                Plan, freeze context, generate, review, apply, verify, and
                repair without routing through general chat.
              </DialogDescription>
            </div>
            <div className="flex gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={Boolean(activeAction) || creating}
                onClick={() => setShowCreate((current) => !current)}
              >
                <PlusIcon className="size-4" />
                New task
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={loading || Boolean(activeAction)}
                onClick={() => {
                  setLoading(true);
                  void refresh();
                }}
              >
                <RefreshCwIcon
                  className={cn("size-4", loading && "animate-spin")}
                />
                Refresh
              </Button>
            </div>
          </header>

          {error ? (
            <p className="mx-5 mt-4 rounded-lg border border-red-900 bg-red-950/40 p-3 text-sm text-red-300">
              {error}
            </p>
          ) : null}

          {showCreate ? (
            <section className="mx-5 mt-4 grid gap-3 rounded-xl border border-zinc-800 bg-zinc-950 p-4 md:grid-cols-[minmax(0,1fr)_200px]">
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <Label htmlFor="task-title">Task title</Label>
                  <Input
                    id="task-title"
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    placeholder="Add an inventory pickup system"
                    maxLength={160}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="task-goal">Bounded goal</Label>
                  <Textarea
                    id="task-goal"
                    value={goal}
                    onChange={(event) => setGoal(event.target.value)}
                    placeholder="Describe expected behavior, constraints, and acceptance criteria."
                    rows={4}
                    maxLength={12000}
                  />
                </div>
              </div>
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <Label>Agent</Label>
                  <Select
                    value={agentId}
                    onValueChange={(value) => {
                      agentSelectionTouchedRef.current = true;
                      setAgentId(value as typeof agentId);
                      setAgentReason("Selected manually for this task.");
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="unity">Unity</SelectItem>
                      <SelectItem value="coding">Coding</SelectItem>
                      <SelectItem value="web">Web</SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-xs leading-5 text-zinc-500">
                    {agentReason}
                  </p>
                </div>
                <Button
                  type="button"
                  className="w-full"
                  disabled={
                    !title.trim() ||
                    !goal.trim() ||
                    Boolean(activeAction) ||
                    creating
                  }
                  onClick={() => void createAndRun()}
                >
                  {creating ? (
                    <Loader2Icon className="size-4 animate-spin" />
                  ) : (
                    <PlusIcon className="size-4" />
                  )}
                  Create and run
                </Button>
              </div>
            </section>
          ) : null}

          <div className="grid min-h-0 flex-1 lg:grid-cols-[280px_minmax(0,1fr)]">
            <aside className="min-h-0 overflow-y-auto border-r border-zinc-800 p-3">
              <div className="space-y-2">
                {tasks.map((task) => (
                  <button
                    key={task.task_id}
                    type="button"
                    className={cn(
                      "w-full rounded-lg border p-3 text-left transition",
                      selectedTaskId === task.task_id
                        ? "border-violet-700 bg-violet-950/30"
                        : "border-zinc-800 bg-zinc-950 hover:border-zinc-700",
                    )}
                    onClick={() => {
                      setSelectedTaskId(task.task_id);
                      setLiveEvents([]);
                      setVerificationOutput("");
                    }}
                  >
                    <div className="flex items-start gap-2">
                      {task.status === "completed" ? (
                        <CheckCircle2Icon className="mt-0.5 size-4 shrink-0 text-emerald-400" />
                      ) : (
                        <CircleDotIcon className="mt-0.5 size-4 shrink-0 text-violet-400" />
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-zinc-200">
                          {task.title}
                        </p>
                        <Badge className={cn("mt-2", taskBadgeClass(task))}>
                          {task.status.replaceAll("_", " ")}
                        </Badge>
                        <p className="mt-2 truncate text-[11px] text-zinc-600">
                          {task.phase.replaceAll("_", " ")}
                        </p>
                      </div>
                    </div>
                  </button>
                ))}
                {!loading && tasks.length === 0 ? (
                  <p className="rounded-lg border border-dashed border-zinc-800 p-6 text-center text-xs text-zinc-500">
                    No project tasks yet.
                  </p>
                ) : null}
              </div>
            </aside>

            <main className="min-h-0 overflow-y-auto p-4 sm:p-5">
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
                <div className="flex h-full items-center justify-center text-sm text-zinc-500">
                  Create or select a project task.
                </div>
              )}
            </main>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
