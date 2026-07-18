"use client";

import {
  CheckCircle2Icon,
  CircleDotIcon,
  Loader2Icon,
  RefreshCwIcon,
  RotateCcwIcon,
  WrenchIcon,
  XIcon,
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
import {
  dismissRepairTask,
  listRepairTasks,
  reopenRepairTask,
  startRepairAttempt,
} from "@/features/repairs/repair-api";
import type { RepairTask } from "@/features/repairs/repair-types";
import { getVerificationRun } from "@/features/verification/verification-api";
import { requestAgentFix } from "@/features/verification/verification-events";
import { VerificationDialog } from "@/features/verification/verification-dialog";
import { cn } from "@/lib/utils";

const POLL_INTERVAL_MS = 2500;

function statusClass(status: RepairTask["status"]) {
  return cn(
    "border text-[10px] uppercase tracking-wide",
    status === "passed" && "border-emerald-800 bg-emerald-950 text-emerald-300",
    status === "failed" && "border-red-800 bg-red-950 text-red-300",
    status === "awaiting_review" && "border-amber-800 bg-amber-950 text-amber-300",
    status === "ready_to_verify" && "border-sky-800 bg-sky-950 text-sky-300",
    status === "open" && "border-zinc-700 bg-zinc-900 text-zinc-300",
  );
}

export function RepairDialog({ disabled = false }: { disabled?: boolean }) {
  const [open, setOpen] = useState(false);
  const [tasks, setTasks] = useState<RepairTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionId, setActionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setTasks(await listRepairTasks());
      setError(null);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Repair tasks could not be loaded.",
      );
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

  async function continueRepair(task: RepairTask) {
    setActionId(task.task_id);
    try {
      const updated = await startRepairAttempt(task.task_id);
      setTasks((current) => current.map((item) =>
        item.task_id === updated.task_id ? updated : item,
      ));
      const run = await getVerificationRun(task.latest_run_id ?? task.source_run_id);
      requestAgentFix(run, task.task_id);
      setOpen(false);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Repair could not start.");
    } finally {
      setActionId(null);
    }
  }

  async function changeResolution(task: RepairTask) {
    setActionId(task.task_id);
    try {
      const updated = task.status === "passed"
        ? await reopenRepairTask(task.task_id)
        : await dismissRepairTask(task.task_id);
      setTasks((current) => current.map((item) => item.task_id === updated.task_id ? updated : item));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Task could not be updated.");
    } finally {
      setActionId(null);
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" size="sm" disabled={disabled}>
          <WrenchIcon className="size-4" />
          Repairs
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto">
        <div className="flex items-start justify-between gap-4 pr-8">
          <div>
            <DialogTitle>Safe repair tasks</DialogTitle>
            <DialogDescription>
              Failed checks remain connected to their proposed changes and follow-up verification.
            </DialogDescription>
          </div>
          <Button type="button" size="sm" variant="outline" disabled={loading} onClick={() => void refresh()}>
            <RefreshCwIcon className={cn("size-4", loading && "animate-spin")} />
            Refresh
          </Button>
        </div>

        {error ? <p className="rounded-lg border border-red-900 bg-red-950/40 p-3 text-sm text-red-300">{error}</p> : null}
        <div className="space-y-3">
          {tasks.map((task) => (
            <article key={task.task_id} className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    {task.status === "passed" ? <CheckCircle2Icon className="size-4 text-emerald-400" /> : <CircleDotIcon className="size-4 text-amber-400" />}
                    <h3 className="truncate text-sm font-semibold text-zinc-100">{task.title}</h3>
                    <Badge className={statusClass(task.status)}>{task.status.replaceAll("_", " ")}</Badge>
                  </div>
                  <code className="mt-2 block truncate text-xs text-zinc-500" title={task.display_command}>{task.display_command}</code>
                  <p className="mt-2 text-xs text-zinc-400">
                    {task.proposal_count} linked proposal{task.proposal_count === 1 ? "" : "s"} · Updated {new Date(task.updated_at).toLocaleString()}
                  </p>
                  <p className="mt-1 text-xs text-zinc-500">
                    Agent attempts: {task.agent_attempt_count}/{task.max_agent_attempts}
                    {task.attempt_count > task.agent_attempt_count
                      ? ` · ${task.attempt_count - task.agent_attempt_count} follow-up check${task.attempt_count - task.agent_attempt_count === 1 ? "" : "s"}`
                      : ""}
                  </p>
                  {task.attempts.length > 0 ? (
                    <details className="mt-2 text-xs text-zinc-500">
                      <summary className="cursor-pointer">Attempt history</summary>
                      <ol className="mt-2 space-y-1 border-l border-zinc-800 pl-3">
                        {task.attempts.map((attempt) => (
                          <li key={attempt.attempt_id}>
                            #{attempt.sequence} {attempt.kind === "agent" ? "Agent requested" : "Verification"}
                            {attempt.kind === "verification" ? `: ${attempt.status}` : ""}
                            {" · "}{new Date(attempt.created_at).toLocaleString()}
                          </li>
                        ))}
                      </ol>
                    </details>
                  ) : null}
                </div>
                <div className="flex flex-wrap gap-2">
                  {task.status === "ready_to_verify" || task.status === "failed" ? (
                    <VerificationDialog relatedRepairTaskId={task.task_id} triggerLabel="Run checks" />
                  ) : null}
                  {task.status !== "passed" && task.status !== "awaiting_review" ? (
                    <Button type="button" size="sm" onClick={() => void continueRepair(task)} disabled={actionId !== null || !task.can_start_agent_attempt}>
                      {actionId === task.task_id ? <Loader2Icon className="size-4 animate-spin" /> : <WrenchIcon className="size-4" />}
                      Ask coding agent
                    </Button>
                  ) : null}
                  <Button type="button" size="sm" variant="ghost" onClick={() => void changeResolution(task)} disabled={actionId !== null}>
                    {task.status === "passed" ? <RotateCcwIcon className="size-4" /> : <XIcon className="size-4" />}
                    {task.status === "passed" ? "Reopen" : "Dismiss"}
                  </Button>
                </div>
              </div>
            </article>
          ))}
          {!loading && tasks.length === 0 ? (
            <p className="rounded-xl border border-dashed border-zinc-800 p-8 text-center text-sm text-zinc-500">No active repair tasks for this workspace.</p>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
