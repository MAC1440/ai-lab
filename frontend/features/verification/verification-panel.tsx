"use client";

import {
  AlertTriangleIcon,
  CheckCircle2Icon,
  CircleXIcon,
  Clock3Icon,
  FolderSearchIcon,
  HistoryIcon,
  Loader2Icon,
  PlayIcon,
  RefreshCwIcon,
  SquareIcon,
  TerminalIcon,
  WrenchIcon,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { createRepairTask } from "@/features/repairs/repair-api";
import {
  cancelVerificationRun,
  getVerificationOverview,
  getVerificationRun,
  listVerificationRuns,
  streamVerificationRun,
} from "@/features/verification/verification-api";
import { requestAgentFix } from "@/features/verification/verification-events";
import type {
  VerificationOverview,
  VerificationProfile,
  VerificationRun,
  VerificationStatus,
} from "@/features/verification/verification-types";
import { cn } from "@/lib/utils";


const MAX_LIVE_OUTPUT_CHARS = 100_000;

type VerificationPanelProps = {
  relatedProposalId?: string | null;
  relatedRepairTaskId?: string | null;
  relatedProjectTaskId?: string | null;
  onRequestAgentFix?: () => void;
};

function statusClasses(status: VerificationStatus) {
  return cn(
    "border",
    status === "passed" &&
      "border-success/30 bg-success/10 text-success",
    status === "running" &&
      "border-pending/30 bg-pending/10 text-pending",
    status === "failed" &&
      "border-danger/30 bg-danger/10 text-danger",
    status === "error" &&
      "border-danger/30 bg-danger/10 text-danger",
    status === "timed_out" &&
      "border-pending/30 bg-pending/10 text-pending",
    status === "cancelled" &&
      "border-border bg-surface-raised text-muted-foreground",
  );
}

function formatDuration(durationMs: number | null): string {
  if (durationMs === null) {
    return "—";
  }
  if (durationMs < 1000) {
    return `${durationMs} ms`;
  }
  return `${(durationMs / 1000).toFixed(1)} s`;
}

function canRequestFix(run: VerificationRun): boolean {
  return run.status === "failed";
}

function verificationOutput(run: VerificationRun): string {
  const output = (run.output ?? run.output_excerpt).trim();
  const sections = [
    output || null,
    run.error ? `Verification runner error:\n${run.error}` : null,
  ].filter((section): section is string => Boolean(section));

  return sections.join("\n\n") || "No command output was captured.";
}

export function VerificationPanel({
  relatedProposalId = null,
  relatedRepairTaskId = null,
  relatedProjectTaskId = null,
  onRequestAgentFix,
}: VerificationPanelProps) {
  const [overview, setOverview] = useState<VerificationOverview | null>(null);
  const [runs, setRuns] = useState<VerificationRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [running, setRunning] = useState(false);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [activeProfile, setActiveProfile] =
    useState<VerificationProfile | null>(null);
  const [liveOutput, setLiveOutput] = useState("");
  const [liveStatus, setLiveStatus] = useState("Ready");
  const [selectedRun, setSelectedRun] = useState<VerificationRun | null>(null);
  const [fixRequestRunId, setFixRequestRunId] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const outputRef = useRef<HTMLPreElement>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [nextOverview, nextRuns] = await Promise.all([
        getVerificationOverview(),
        listVerificationRuns(),
      ]);
      setOverview(nextOverview);
      setRuns(nextRuns);
      setError(null);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Verification information could not be loaded.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const initialLoadId = window.setTimeout(() => {
      void refresh();
    }, 0);

    return () => {
      window.clearTimeout(initialLoadId);
      abortControllerRef.current?.abort();
    };
  }, [refresh]);

  useEffect(() => {
    outputRef.current?.scrollTo({
      top: outputRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [liveOutput]);

  async function startRun(profile: VerificationProfile) {
    if (running || !profile.available) {
      return;
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;
    setRunning(true);
    setActiveRunId(null);
    setActiveProfile(profile);
    setSelectedRun(null);
    setLiveOutput("");
    setLiveStatus("Preparing verification");
    setError(null);

    let receivedTerminalEvent = false;

    try {
      for await (const event of streamVerificationRun(
        {
          profile_id: profile.profile_id,
          proposal_id: relatedProposalId,
          repair_task_id: relatedRepairTaskId,
          project_task_id: relatedProjectTaskId,
        },
        controller.signal,
      )) {
        switch (event.type) {
          case "verification_started":
            setActiveRunId(event.run_id);
            setLiveStatus("Verification started");
            break;

          case "command_started":
            setLiveStatus(`Running ${event.command}`);
            break;

          case "output":
            setLiveOutput((current) =>
              (current + event.content).slice(-MAX_LIVE_OUTPUT_CHARS),
            );
            break;

          case "command_finished":
            setLiveStatus(
              `Command finished with exit code ${event.exit_code ?? "unknown"}`,
            );
            break;

          case "verification_done":
            receivedTerminalEvent = true;
            setSelectedRun(event.result);
            setLiveStatus(event.result.status.replace("_", " "));
            setRuns((current) => [
              event.result,
              ...current.filter(
                (run) => run.run_id !== event.result.run_id,
              ),
            ]);
            break;

          case "error":
            throw new Error(event.message);
        }
      }

      if (!receivedTerminalEvent) {
        throw new Error(
          "The verification stream ended without a final result.",
        );
      }
    } catch (requestError) {
      if (controller.signal.aborted) {
        setLiveStatus("Verification stream closed");
      } else {
        const message =
          requestError instanceof Error
            ? requestError.message
            : "Verification could not be completed.";
        setError(message);
        setLiveStatus("Verification error");
      }
    } finally {
      abortControllerRef.current = null;
      setRunning(false);
      setActiveRunId(null);
      void refresh();
    }
  }

  async function cancelActiveRun() {
    if (!activeRunId) {
      return;
    }

    setLiveStatus("Requesting cancellation");
    try {
      await cancelVerificationRun(activeRunId);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The verification run could not be cancelled.",
      );
    }
  }

  async function handleRequestFix(run: VerificationRun) {
    if (!canRequestFix(run) || fixRequestRunId) {
      return;
    }

    setFixRequestRunId(run.run_id);
    setError(null);

    try {
      const completeRun = run.output === undefined
        ? await getVerificationRun(run.run_id)
        : run;

      const repairTask = await createRepairTask(completeRun.run_id);
      requestAgentFix(
        completeRun,
        repairTask.task_id,
        relatedProjectTaskId,
      );
      onRequestAgentFix?.();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The complete verification output could not be loaded.",
      );
    } finally {
      setFixRequestRunId(null);
    }
  }

  if (loading && !overview) {
    return (
      <div className="flex min-h-72 items-center justify-center text-sm text-muted-foreground">
        <Loader2Icon className="mr-2 size-4 animate-spin" />
        Detecting workspace projects…
      </div>
    );
  }

  return (
    <div className="grid min-h-0 gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
      <section className="min-w-0 space-y-4">
        <div className="rounded-xl border border-border bg-surface-raised p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <FolderSearchIcon className="size-4 text-pending" />
                Detected workspace
              </div>
              <p
                className="mt-1 max-w-2xl truncate font-mono text-xs text-muted-foreground"
                title={overview?.workspace}
              >
                {overview?.workspace ?? "No workspace selected"}
              </p>
            </div>

            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={running || loading}
              onClick={() => void refresh()}
            >
              <RefreshCwIcon
                className={cn("size-4", loading && "animate-spin")}
              />
              Refresh
            </Button>
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            {overview?.projects.length ? (
              overview.projects.map((project) => (
                <Badge
                  key={`${project.type}:${project.root}`}
                  variant="outline"
                  className="border-border bg-surface-raised text-muted-foreground"
                >
                  {project.name}
                  {project.version ? ` ${project.version}` : ""}
                  <span className="ml-1 text-muted-foreground">· {project.root}</span>
                </Badge>
              ))
            ) : (
              <p className="text-xs text-muted-foreground">
                No supported project markers were detected.
              </p>
            )}
          </div>
        </div>

        {error ? (
          <div className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger">
            <AlertTriangleIcon className="mt-0.5 size-4 shrink-0" />
            <span>{error}</span>
          </div>
        ) : null}

        <div className="space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            Available checks
          </h3>

          {overview?.profiles.length ? (
            overview.profiles.map((profile) => (
              <article
                key={profile.profile_id}
                className="rounded-xl border border-border bg-surface-raised p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <TerminalIcon className="size-4 shrink-0 text-pending" />
                      <h4 className="text-sm font-semibold text-foreground">
                        {profile.name}
                      </h4>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">
                      {profile.description}
                    </p>
                    <code className="mt-2 block overflow-x-auto rounded bg-surface-raised px-2.5 py-2 text-xs text-muted-foreground">
                      {profile.command}
                    </code>
                    {!profile.available ? (
                      <p className="mt-2 text-xs text-pending">
                        {profile.unavailable_reason}
                      </p>
                    ) : null}
                  </div>

                  <Button
                    type="button"
                    size="sm"
                    disabled={running || !profile.available}
                    onClick={() => void startRun(profile)}
                  >
                    {running &&
                    activeProfile?.profile_id === profile.profile_id ? (
                      <Loader2Icon className="size-4 animate-spin" />
                    ) : (
                      <PlayIcon className="size-4" />
                    )}
                    Run
                  </Button>
                </div>
              </article>
            ))
          ) : (
            <div className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
              No verification commands are available for this workspace yet.
            </div>
          )}
        </div>
      </section>

      <section className="min-w-0 space-y-4">
        <div className="overflow-hidden rounded-xl border border-border bg-foreground">
          <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-surface-raised px-3 py-2.5">
            <div className="flex min-w-0 items-center gap-2 text-xs text-muted-foreground">
              {running ? (
                <Loader2Icon className="size-4 shrink-0 animate-spin text-pending" />
              ) : selectedRun?.status === "passed" ? (
                <CheckCircle2Icon className="size-4 shrink-0 text-success" />
              ) : selectedRun ? (
                <CircleXIcon className="size-4 shrink-0 text-danger" />
              ) : (
                <TerminalIcon className="size-4 shrink-0 text-muted-foreground" />
              )}
              <span className="truncate">{liveStatus}</span>
            </div>

            {running ? (
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={!activeRunId}
                onClick={() => void cancelActiveRun()}
              >
                <SquareIcon className="size-3.5" />
                Cancel
              </Button>
            ) : null}
          </header>

          <pre
            ref={outputRef}
            className="h-72 overflow-auto whitespace-pre-wrap break-words p-3 font-mono text-xs leading-5 text-muted-foreground bg-surface"
          >
            {liveOutput ||
              (selectedRun
                ? verificationOutput(selectedRun)
                : "Command output will appear here.")}
          </pre>

          {selectedRun ? (
            <footer className="flex flex-wrap items-center gap-2 border-t border-border bg-surface-raised px-3 py-2.5 text-xs text-muted-foreground">
              <Badge className={statusClasses(selectedRun.status)}>
                {selectedRun.status.replace("_", " ")}
              </Badge>
              <span>Exit {selectedRun.exit_code ?? "—"}</span>
              <span>·</span>
              <span>{formatDuration(selectedRun.duration_ms)}</span>

              {canRequestFix(selectedRun) ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="ml-auto"
                  disabled={fixRequestRunId !== null}
                  onClick={() => void handleRequestFix(selectedRun)}
                >
                  {fixRequestRunId === selectedRun.run_id ? (
                    <Loader2Icon className="size-4 animate-spin" />
                  ) : (
                    <WrenchIcon className="size-4" />
                  )}
                  {fixRequestRunId === selectedRun.run_id
                    ? "Loading output"
                    : "Ask agent to fix"}
                </Button>
              ) : null}
            </footer>
          ) : null}
        </div>

        <div>
          <div className="mb-2 flex items-center gap-2">
            <HistoryIcon className="size-4 text-muted-foreground" />
            <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              Recent runs
            </h3>
          </div>

          <div className="max-h-72 space-y-2 overflow-y-auto pr-1">
            {runs.length ? (
              runs.map((run) => (
                <button
                  key={run.run_id}
                  type="button"
                  className="w-full rounded-lg border border-border bg-surface-raised p-3 text-left transition hover:border-border"
                  onClick={() => {
                    setSelectedRun(run);
                    setLiveOutput(run.output_excerpt);
                    setLiveStatus(run.status.replace("_", " "));
                  }}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="truncate text-xs font-medium text-foreground">
                      {run.profile_name}
                    </span>
                    <Badge className={statusClasses(run.status)}>
                      {run.status.replace("_", " ")}
                    </Badge>
                  </div>
                  <div className="mt-1.5 flex items-center gap-2 text-[11px] text-muted-foreground">
                    <Clock3Icon className="size-3" />
                    <span>{new Date(run.started_at).toLocaleString()}</span>
                    <span>·</span>
                    <span>{formatDuration(run.duration_ms)}</span>
                  </div>
                </button>
              ))
            ) : (
              <p className="rounded-lg border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
                No verification runs have been recorded for this workspace.
              </p>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
