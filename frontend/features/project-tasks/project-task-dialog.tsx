"use client";

import {
  CheckCircle2Icon,
  CircleDotIcon,
  ListTodoIcon,
  Loader2Icon,
  PlayIcon,
  RefreshCwIcon,
  SquareIcon,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

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
import {
  cancelProjectTask,
  createProjectTask,
  listProjectTasks,
  resumeProjectTask,
} from "@/features/project-tasks/project-task-api";
import { getProjectTaskAction } from "@/features/project-tasks/project-task-actions.mjs";
import { requestProjectTaskRun } from "@/features/project-tasks/project-task-events";
import type { ProjectTask } from "@/features/project-tasks/project-task-types";
import { startRepairAttempt } from "@/features/repairs/repair-api";
import { VerificationDialog } from "@/features/verification";
import { getVerificationRun } from "@/features/verification/verification-api";
import { requestAgentFix } from "@/features/verification/verification-events";
import { cn } from "@/lib/utils";

const POLL_INTERVAL_MS = 2500;

function statusClass(task: ProjectTask) {
  return cn(
    "border text-[10px] uppercase tracking-wide",
    task.status === "completed" && "border-emerald-800 bg-emerald-950 text-emerald-300",
    (task.status === "running" || task.status === "verifying") && "border-sky-800 bg-sky-950 text-sky-300",
    task.status === "awaiting_approval" && "border-amber-800 bg-amber-950 text-amber-300",
    task.status === "needs_attention" && "border-red-800 bg-red-950 text-red-300",
    (task.status === "paused" || task.status === "cancelled") && "border-zinc-700 bg-zinc-900 text-zinc-300",
  );
}

export function ProjectTaskDialog({ disabled = false }: { disabled?: boolean }) {
  const [open, setOpen] = useState(false);
  const [tasks, setTasks] = useState<ProjectTask[]>([]);
  const [title, setTitle] = useState("");
  const [goal, setGoal] = useState("");
  const [agentId, setAgentId] = useState<"unity" | "coding" | "web">("unity");
  const [loading, setLoading] = useState(false);
  const [actionId, setActionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setTasks(await listProjectTasks());
      setError(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Project tasks could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    const interval = window.setInterval(() => void refresh(), POLL_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [open, refresh]);

  function handleOpenChange(nextOpen: boolean) {
    if (nextOpen) {
      setLoading(true);
      void refresh();
    }
    setOpen(nextOpen);
  }

  async function createAndRun() {
    if (!title.trim() || !goal.trim() || actionId) return;
    setActionId("create");
    try {
      const task = await createProjectTask({
        title: title.trim(),
        goal: goal.trim(),
        agent_id: agentId,
      });
      requestProjectTaskRun(task);
      setTitle("");
      setGoal("");
      setOpen(false);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Project task could not be created.");
    } finally {
      setActionId(null);
    }
  }

  async function continueTask(task: ProjectTask) {
    setActionId(task.task_id);
    try {
      if (task.repair_task_id && task.latest_verification_run_id) {
        await startRepairAttempt(task.repair_task_id);
        const run = await getVerificationRun(task.latest_verification_run_id);
        requestAgentFix(run, task.repair_task_id, task.task_id);
      } else {
        const resumed = task.status === "queued"
          ? task
          : await resumeProjectTask(task.task_id);
        requestProjectTaskRun(resumed);
      }
      setOpen(false);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Project task could not continue.");
    } finally {
      setActionId(null);
    }
  }

  async function cancelTask(task: ProjectTask) {
    setActionId(task.task_id);
    try {
      const updated = await cancelProjectTask(task.task_id);
      setTasks((current) => current.map((item) => item.task_id === updated.task_id ? updated : item));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Project task could not be cancelled.");
    } finally {
      setActionId(null);
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
      <DialogContent className="max-h-[92vh] max-w-5xl overflow-y-auto">
        <div className="flex items-start justify-between gap-4 pr-8">
          <div>
            <DialogTitle>Project tasks</DialogTitle>
            <DialogDescription>
              Persisted multi-file work: inspect, propose, approve, verify, and repair.
            </DialogDescription>
          </div>
          <Button type="button" size="sm" variant="outline" disabled={loading} onClick={() => void refresh()}>
            <RefreshCwIcon className={cn("size-4", loading && "animate-spin")} />
            Refresh
          </Button>
        </div>

        <section className="grid gap-3 rounded-xl border border-zinc-800 bg-zinc-950 p-4 md:grid-cols-[minmax(0,1fr)_180px]">
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="task-title">Task title</Label>
              <Input id="task-title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Add an inventory pickup system" maxLength={160} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="task-goal">Bounded goal</Label>
              <Textarea id="task-goal" value={goal} onChange={(event) => setGoal(event.target.value)} placeholder="Describe expected behavior, constraints, and acceptance criteria." rows={4} maxLength={12000} />
            </div>
          </div>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label>Agent</Label>
              <Select value={agentId} onValueChange={(value) => setAgentId(value as typeof agentId)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="unity">Unity</SelectItem>
                  <SelectItem value="coding">Coding</SelectItem>
                  <SelectItem value="web">Web</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <p className="text-xs leading-5 text-zinc-500">The agent can propose up to 20 related files. No filesystem write occurs until you approve the set.</p>
            <Button type="button" className="w-full" disabled={!title.trim() || !goal.trim() || actionId !== null} onClick={() => void createAndRun()}>
              {actionId === "create" ? <Loader2Icon className="size-4 animate-spin" /> : <PlayIcon className="size-4" />}
              Create and load into chat
            </Button>
          </div>
        </section>

        {error ? <p className="rounded-lg border border-red-900 bg-red-950/40 p-3 text-sm text-red-300">{error}</p> : null}

        <div className="space-y-3">
          {tasks.map((task) => (
            <article key={task.task_id} className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    {task.status === "completed" ? <CheckCircle2Icon className="size-4 text-emerald-400" /> : <CircleDotIcon className="size-4 text-violet-400" />}
                    <h3 className="text-sm font-semibold text-zinc-100">{task.title}</h3>
                    <Badge className={statusClass(task)}>{task.status.replaceAll("_", " ")}</Badge>
                  </div>
                  <p className="mt-2 line-clamp-2 text-xs leading-5 text-zinc-400">{task.goal}</p>
                  <p className="mt-2 text-xs text-zinc-500">
                    Phase: {task.phase.replaceAll("_", " ")} · Attempt {task.attempt_count}/{task.max_attempts} · {task.proposal_count} file proposal{task.proposal_count === 1 ? "" : "s"}
                  </p>
                  {task.last_error ? <p className="mt-2 text-xs text-amber-300">{task.last_error}</p> : null}
                  {task.events.length ? (
                    <details className="mt-2 text-xs text-zinc-500">
                      <summary className="cursor-pointer">Audit trail ({task.events.length})</summary>
                      <ol className="mt-2 space-y-1 border-l border-zinc-800 pl-3">
                        {task.events.map((event) => <li key={event.event_id}>{event.message} · {new Date(event.created_at).toLocaleString()}</li>)}
                      </ol>
                    </details>
                  ) : null}
                </div>
                <div className="flex flex-wrap gap-2">
                  {getProjectTaskAction(
                    task.status,
                    task.can_resume,
                    Boolean(task.repair_task_id),
                  ) === "verify" ? (
                    <VerificationDialog
                      relatedProposalId={task.proposals[0]?.proposal_id ?? null}
                      relatedRepairTaskId={task.repair_task_id}
                      relatedProjectTaskId={task.task_id}
                      triggerLabel="Run checks"
                    />
                  ) : null}
                  {getProjectTaskAction(
                    task.status,
                    task.can_resume,
                    Boolean(task.repair_task_id),
                  ) === "start" || getProjectTaskAction(
                    task.status,
                    task.can_resume,
                    Boolean(task.repair_task_id),
                  ) === "continue" || getProjectTaskAction(
                    task.status,
                    task.can_resume,
                    Boolean(task.repair_task_id),
                  ) === "repair" ? (
                    <Button type="button" size="sm" disabled={actionId !== null} onClick={() => void continueTask(task)}>
                      {actionId === task.task_id ? <Loader2Icon className="size-4 animate-spin" /> : <PlayIcon className="size-4" />}
                      {task.repair_task_id ? "Repair" : task.status === "queued" ? "Start" : "Continue"}
                    </Button>
                  ) : null}
                  {!(["completed", "cancelled"] as string[]).includes(task.status) ? (
                    <Button type="button" size="sm" variant="ghost" disabled={actionId !== null} onClick={() => void cancelTask(task)}>
                      <SquareIcon className="size-3.5" /> Cancel
                    </Button>
                  ) : null}
                </div>
              </div>
            </article>
          ))}
          {!loading && tasks.length === 0 ? <p className="rounded-xl border border-dashed border-zinc-800 p-8 text-center text-sm text-zinc-500">No project tasks yet.</p> : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
