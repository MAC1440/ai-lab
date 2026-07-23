"use client";

import {
  AlertTriangleIcon,
  CheckCircle2Icon,
  CircleDotIcon,
  FileCode2Icon,
  Loader2Icon,
  PlayIcon,
  RotateCcwIcon,
  ShieldCheckIcon,
  SquareIcon,
  XIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChangeApprovalPanel } from "@/features/changes/change-approval-panel";
import { getProjectTaskAction } from "@/features/project-tasks/project-task-actions.mjs";
import type {
  ImplementationPlan,
  ProjectTask,
  ProjectTaskStreamEvent,
} from "@/features/project-tasks/project-task-types";
import { cn } from "@/lib/utils";

type Props = {
  task: ProjectTask;
  liveEvents: ProjectTaskStreamEvent[];
  verificationOutput: string;
  action: string | null;
  onRun: (task: ProjectTask) => void;
  onApproveAndVerify: (task: ProjectTask) => void;
  onReject: (task: ProjectTask) => void;
  onRepair: (task: ProjectTask) => void;
  onCancel: (task: ProjectTask) => void;
};

function latestArtifact<T>(task: ProjectTask, type: string): T | null {
  for (let index = task.artifacts.length - 1; index >= 0; index -= 1) {
    if (task.artifacts[index]?.artifact_type === type) {
      return task.artifacts[index].payload as T;
    }
  }
  return null;
}

function statusClass(task: ProjectTask) {
  return cn(
    "border text-[10px] uppercase tracking-wide",
    task.status === "completed" &&
      "border-emerald-800 bg-emerald-950 text-emerald-300",
    (task.status === "running" || task.status === "verifying") &&
      "border-sky-800 bg-sky-950 text-sky-300",
    task.status === "awaiting_approval" &&
      "border-amber-800 bg-amber-950 text-amber-300",
    task.status === "needs_attention" &&
      "border-red-800 bg-red-950 text-red-300",
    (task.status === "paused" || task.status === "cancelled") &&
      "border-zinc-700 bg-zinc-900 text-zinc-300",
  );
}

function readableBytes(value?: number) {
  if (!value) return "0 B";
  if (value < 1024) return `${value} B`;
  return `${(value / 1024).toFixed(1)} KB`;
}

export function ProjectTaskDetails({
  task,
  liveEvents,
  verificationOutput,
  action,
  onRun,
  onApproveAndVerify,
  onReject,
  onRepair,
  onCancel,
}: Props) {
  const plan = latestArtifact<ImplementationPlan>(task, "implementation_plan");
  const context = latestArtifact<{
    files?: Array<{ path: string; sha256: string; bytes: number }>;
    bytes?: number;
    complete?: boolean;
    omitted?: string[];
  }>(task, "context_pack");
  const validation = latestArtifact<{
    valid?: boolean;
    checked_files?: number;
    diagnostics?: Array<{
      path?: string;
      severity?: string;
      message?: string;
      line?: number;
    }>;
  }>(task, "source_validation");
  const storedVerification = latestArtifact<{
    status?: string;
    profile_name?: string;
    display_command?: string;
    duration_ms?: number;
    exit_code?: number | null;
    output?: string;
    output_truncated?: boolean;
    error?: string | null;
  }>(task, "verification_result");
  const displayedVerificationOutput =
    verificationOutput || storedVerification?.output || "";
  const primaryAction = getProjectTaskAction(
    task.status,
    task.phase,
    task.can_resume,
    Boolean(task.repair_task_id),
  );
  const busy = action !== null;

  return (
    <section className="space-y-4">
      <header className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              {task.status === "completed" ? (
                <CheckCircle2Icon className="size-5 text-emerald-400" />
              ) : (
                <CircleDotIcon className="size-5 text-violet-400" />
              )}
              <h2 className="text-base font-semibold text-zinc-100">
                {task.title}
              </h2>
              <Badge className={statusClass(task)}>
                {task.status.replaceAll("_", " ")}
              </Badge>
            </div>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-zinc-400">
              {task.goal}
            </p>
            <p className="mt-2 text-xs text-zinc-500">
              Phase: {task.phase.replaceAll("_", " ")} · Attempt{" "}
              {task.attempt_count}/{task.max_attempts} · {task.agent_id} agent
            </p>
            {task.last_error ? (
              <p className="mt-3 rounded-lg border border-amber-900/70 bg-amber-950/30 p-3 text-xs leading-5 text-amber-200">
                {task.last_error}
              </p>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-2">
            {primaryAction === "start" || primaryAction === "continue" ? (
              <Button disabled={busy} onClick={() => onRun(task)}>
                {action === "run" ? (
                  <Loader2Icon className="size-4 animate-spin" />
                ) : primaryAction === "continue" ? (
                  <RotateCcwIcon className="size-4" />
                ) : (
                  <PlayIcon className="size-4" />
                )}
                {primaryAction === "continue" ? "Continue" : "Run task"}
              </Button>
            ) : null}
            {primaryAction === "repair" ? (
              <Button disabled={busy} onClick={() => onRepair(task)}>
                {action === "repair" ? (
                  <Loader2Icon className="size-4 animate-spin" />
                ) : (
                  <RotateCcwIcon className="size-4" />
                )}
                Generate bounded repair
              </Button>
            ) : null}
            {primaryAction === "verify" ? (
              <Button
                disabled={busy}
                onClick={() => onApproveAndVerify(task)}
              >
                {action === "verify" ? (
                  <Loader2Icon className="size-4 animate-spin" />
                ) : (
                  <ShieldCheckIcon className="size-4" />
                )}
                Retry checks
              </Button>
            ) : null}
            {primaryAction === "cancel" ? (
              <Button
                variant="outline"
                disabled={busy}
                onClick={() => onCancel(task)}
              >
                <SquareIcon className="size-4" />
                Stop
              </Button>
            ) : null}
            {!["completed", "cancelled"].includes(task.status) &&
            primaryAction !== "cancel" ? (
              <Button
                variant="ghost"
                disabled={busy}
                onClick={() => onCancel(task)}
              >
                <SquareIcon className="size-4" />
                Cancel task
              </Button>
            ) : null}
          </div>
        </div>
      </header>

      {liveEvents.length ? (
        <section className="rounded-xl border border-sky-900/70 bg-sky-950/20 p-4">
          <h3 className="text-sm font-semibold text-sky-200">Live workflow</h3>
          <ol className="mt-3 space-y-2">
            {liveEvents.slice(-8).map((event, index) => (
              <li
                key={`${event.type}-${index}`}
                className="flex gap-2 text-xs leading-5 text-sky-100/80"
              >
                {index === liveEvents.slice(-8).length - 1 && busy ? (
                  <Loader2Icon className="mt-0.5 size-3.5 shrink-0 animate-spin" />
                ) : (
                  <CheckCircle2Icon className="mt-0.5 size-3.5 shrink-0" />
                )}
                <span>
                  {event.message ||
                    event.stage?.replaceAll("_", " ") ||
                    event.type.replaceAll("_", " ")}
                </span>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <FileCode2Icon className="size-4 text-violet-400" />
            Structured plan
          </h3>
          {plan ? (
            <div className="mt-3 space-y-3">
              <p className="text-xs leading-5 text-zinc-400">{plan.summary}</p>
              <ul className="space-y-2">
                {plan.files.map((file) => (
                  <li
                    key={`${file.operation}:${file.path}`}
                    className="rounded-lg border border-zinc-800 p-2.5"
                  >
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">{file.operation}</Badge>
                      <code className="min-w-0 truncate text-xs text-zinc-200">
                        {file.path}
                      </code>
                    </div>
                    <p className="mt-1.5 text-xs text-zinc-500">{file.reason}</p>
                  </li>
                ))}
              </ul>
              {plan.risks.length ? (
                <p className="text-xs text-amber-300">
                  Risks: {plan.risks.join(" · ")}
                </p>
              ) : null}
            </div>
          ) : (
            <p className="mt-3 text-xs text-zinc-500">
              The planning model has not produced a typed plan yet.
            </p>
          )}
        </section>

        <section className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <ShieldCheckIcon className="size-4 text-emerald-400" />
            Frozen context and validation
          </h3>
          {context ? (
            <div className="mt-3 space-y-2 text-xs text-zinc-400">
              <p>
                {context.files?.length ?? 0} exact file(s) ·{" "}
                {readableBytes(context.bytes)} ·{" "}
                {context.complete ? "complete" : "incomplete"}
              </p>
              <ul className="max-h-40 space-y-1 overflow-y-auto">
                {context.files?.map((file) => (
                  <li
                    key={file.path}
                    className="flex items-center justify-between gap-3"
                  >
                    <code className="truncate">{file.path}</code>
                    <span className="shrink-0 text-zinc-600">
                      {readableBytes(file.bytes)}
                    </span>
                  </li>
                ))}
              </ul>
              {context.omitted?.length ? (
                <p className="text-amber-300">
                  Omitted: {context.omitted.join(", ")}
                </p>
              ) : null}
            </div>
          ) : (
            <p className="mt-3 text-xs text-zinc-500">
              Context will be frozen after planning.
            </p>
          )}
          {validation ? (
            <div
              className={cn(
                "mt-4 rounded-lg border p-3 text-xs",
                validation.valid !== false
                  ? "border-emerald-900 bg-emerald-950/30 text-emerald-200"
                  : "border-red-900 bg-red-950/30 text-red-200",
              )}
            >
              <p className="flex items-center gap-2 font-medium">
                {validation.valid !== false ? (
                  <CheckCircle2Icon className="size-4" />
                ) : (
                  <AlertTriangleIcon className="size-4" />
                )}
                Source validation{" "}
                {validation.valid !== false ? "passed" : "failed"}
              </p>
              {validation.diagnostics?.map((diagnostic, index) => (
                <p key={index} className="mt-2">
                  {diagnostic.path}: {diagnostic.message}
                </p>
              ))}
            </div>
          ) : null}
        </section>
      </div>

      {task.proposals.length ? (
        <section className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold">
                Atomic change set ({task.proposals.length} file
                {task.proposals.length === 1 ? "" : "s"})
              </h3>
              <p className="mt-1 text-xs text-zinc-500">
                Review every operation. Application and verification are one
                controlled workflow.
              </p>
            </div>
            {primaryAction === "review" ? (
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  disabled={busy}
                  className="border-red-900 text-red-300"
                  onClick={() => onReject(task)}
                >
                  <XIcon className="size-4" />
                  Reject set
                </Button>
                <Button
                  disabled={busy}
                  className="bg-emerald-600 hover:bg-emerald-500"
                  onClick={() => onApproveAndVerify(task)}
                >
                  {action === "verify" ? (
                    <Loader2Icon className="size-4 animate-spin" />
                  ) : (
                    <ShieldCheckIcon className="size-4" />
                  )}
                  Apply set and run checks
                </Button>
              </div>
            ) : null}
          </div>
          {task.proposals.map((proposal) => (
            <ChangeApprovalPanel
              key={proposal.proposal_id}
              proposal={proposal}
              reviewOnly
            />
          ))}
        </section>
      ) : null}

      {storedVerification || displayedVerificationOutput ? (
        <section className="overflow-hidden rounded-xl border border-zinc-800 bg-black">
          <header className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800 px-4 py-2 text-xs text-zinc-300">
            <span className="font-medium">Verification output</span>
            {storedVerification ? (
              <span className="text-zinc-500">
                {storedVerification.status ?? "unknown"}
                {typeof storedVerification.exit_code === "number"
                  ? ` · exit ${storedVerification.exit_code}`
                  : ""}
                {typeof storedVerification.duration_ms === "number"
                  ? ` · ${(storedVerification.duration_ms / 1000).toFixed(1)}s`
                  : ""}
                {storedVerification.output_truncated ? " · truncated" : ""}
              </span>
            ) : null}
          </header>
          {displayedVerificationOutput ? (
            <pre className="max-h-80 overflow-auto whitespace-pre-wrap p-4 text-xs leading-5 text-zinc-300">
              {displayedVerificationOutput}
            </pre>
          ) : null}
          {storedVerification?.error ? (
            <p className="border-t border-red-900/60 bg-red-950/30 px-4 py-3 text-xs text-red-300">
              {storedVerification.error}
            </p>
          ) : null}
        </section>
      ) : null}

      {task.events.length ? (
        <details className="rounded-xl border border-zinc-800 bg-zinc-950 p-4 text-xs text-zinc-500">
          <summary className="cursor-pointer font-medium text-zinc-300">
            Durable audit trail ({task.events.length})
          </summary>
          <ol className="mt-3 space-y-2 border-l border-zinc-800 pl-3">
            {task.events.map((event) => (
              <li key={event.event_id}>
                {event.message} · {new Date(event.created_at).toLocaleString()}
              </li>
            ))}
          </ol>
        </details>
      ) : null}
    </section>
  );
}
