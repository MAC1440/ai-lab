"use client";

import {
  CheckCircle2Icon,
  FlaskConicalIcon,
  Loader2Icon,
  RotateCcwIcon,
  ShieldAlertIcon,
  XCircleIcon,
} from "lucide-react";
import { useEffect, useReducer, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  getReliabilityRun,
  listReliabilityRuns,
  listReliabilityScenarios,
  type ReliabilityAgentOverride,
  type ReliabilityBenchmarkRun,
  type ReliabilityScenario,
  type ReliabilityScenarioResult,
  type ReliabilitySuite,
  streamReliabilityBenchmark,
} from "@/features/reliability/reliability-benchmark-api";
import {
  initialReliabilityState,
  reduceReliabilityEvent,
} from "@/features/reliability/reliability-benchmark-state.mjs";
import { cn } from "@/lib/utils";

export function ReliabilityBenchmarkDialog({
  disabled = false,
}: {
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [suite, setSuite] = useState<ReliabilitySuite>("quick");
  const [repetitions, setRepetitions] = useState("1");
  const [agentOverride, setAgentOverride] =
    useState<ReliabilityAgentOverride>("assigned");
  const [scenarios, setScenarios] = useState<ReliabilityScenario[]>([]);
  const [history, setHistory] = useState<ReliabilityBenchmarkRun[]>([]);
  const [state, dispatch] = useReducer(
    reduceReliabilityEvent,
    initialReliabilityState,
  );
  const [running, setRunning] = useState(false);
  const [loadingRunId, setLoadingRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!open) return;
    void Promise.all([listReliabilityScenarios(), listReliabilityRuns()])
      .then(([availableScenarios, runs]) => {
        setScenarios(availableScenarios);
        setHistory(runs);
      })
      .catch((reason: unknown) => setError(messageFrom(reason)));
  }, [open]);

  useEffect(
    () => () => {
      controllerRef.current?.abort();
    },
    [],
  );

  const selectedScenarios = scenarios.filter((scenario) =>
    scenario.suites.includes(suite),
  );
  const estimatedModelCalls =
    selectedScenarios.reduce(
      (total, scenario) => total + scenario.model_calls,
      0,
    ) * Number(repetitions);
  const progress =
    state.scenarioCount > 0
      ? (state.completedCount / state.scenarioCount) * 100
      : 0;

  async function runBenchmark() {
    if (running) return;
    const controller = new AbortController();
    controllerRef.current = controller;
    setRunning(true);
    setError(null);
    try {
      for await (const event of streamReliabilityBenchmark(
        {
          suite,
          repetitions: Number(repetitions),
          agent_override: agentOverride,
        },
        controller.signal,
      )) {
        dispatch(event);
      }
      setHistory(await listReliabilityRuns());
    } catch (reason) {
      const stopped =
        reason instanceof DOMException && reason.name === "AbortError";
      if (!stopped) setError(messageFrom(reason));
    } finally {
      controllerRef.current = null;
      setRunning(false);
    }
  }

  async function showRun(runId: string) {
    setLoadingRunId(runId);
    setError(null);
    try {
      const run = await getReliabilityRun(runId);
      dispatch({
        type: "reliability_done",
        run_id: run.run_id,
        run,
      });
    } catch (reason) {
      setError(messageFrom(reason));
    } finally {
      setLoadingRunId(null);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) controllerRef.current?.abort();
        if (nextOpen) setError(null);
        setOpen(nextOpen);
      }}
    >
      <DialogTrigger asChild>
        <Button type="button" variant="outline" size="sm" disabled={disabled}>
          <FlaskConicalIcon className="size-4" />
          Reliability
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[92vh] max-w-5xl overflow-y-auto">
        <DialogTitle>End-to-end reliability benchmark</DialogTitle>
        <DialogDescription>
          Run the real staged coding workflow in disposable Python, Next.js,
          and Unity fixtures. Your selected project is never read or modified.
        </DialogDescription>

        <Tabs defaultValue="run">
          <TabsList>
            <TabsTrigger value="run">Run suite</TabsTrigger>
            <TabsTrigger value="history">History</TabsTrigger>
          </TabsList>

          <TabsContent value="run" className="space-y-4">
            <section className="grid gap-3 rounded-xl border border-zinc-800 bg-zinc-950 p-4 md:grid-cols-4">
              <Field label="Suite">
                <Select
                  value={suite}
                  disabled={running}
                  onValueChange={(value) =>
                    setSuite(value as ReliabilitySuite)
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="quick">Quick</SelectItem>
                    <SelectItem value="full">Full</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
              <Field label="Repetitions">
                <Select
                  value={repetitions}
                  disabled={running}
                  onValueChange={setRepetitions}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1">1 run</SelectItem>
                    <SelectItem value="2">2 runs</SelectItem>
                    <SelectItem value="3">3 runs</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
              <Field label="Agent assignment">
                <Select
                  value={agentOverride}
                  disabled={running}
                  onValueChange={(value) =>
                    setAgentOverride(value as ReliabilityAgentOverride)
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="assigned">
                      Per scenario
                    </SelectItem>
                    <SelectItem value="coding">Coding only</SelectItem>
                    <SelectItem value="web">Web only</SelectItem>
                    <SelectItem value="unity">Unity only</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
              <div className="flex items-end">
                <Button
                  className="w-full"
                  disabled={running || selectedScenarios.length === 0}
                  onClick={() => void runBenchmark()}
                >
                  {running ? (
                    <Loader2Icon className="size-4 animate-spin" />
                  ) : (
                    <FlaskConicalIcon className="size-4" />
                  )}
                  {running ? "Running…" : "Run benchmark"}
                </Button>
              </div>
              <p className="text-xs text-zinc-500 md:col-span-4">
                {selectedScenarios.length * Number(repetitions)} scenario
                executions · approximately {estimatedModelCalls} model calls ·
                safety scenarios use no model calls
              </p>
            </section>

            {running || state.run ? (
              <section className="space-y-3 rounded-xl border border-zinc-800 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h3 className="text-sm font-semibold">
                      {running
                        ? state.currentScenario?.name ?? "Preparing fixtures"
                        : resultTitle(state.run)}
                    </h3>
                    <p className="mt-1 text-xs text-zinc-500">
                      {state.runId ?? state.run?.run_id}
                    </p>
                  </div>
                  {state.run ? (
                    <RunBadge run={state.run} />
                  ) : (
                    <Badge variant="outline">
                      {state.completedCount}/{state.scenarioCount}
                    </Badge>
                  )}
                </div>
                <Progress value={state.run ? state.run.pass_rate * 100 : progress} />
                <ResultGrid results={state.results} scenarios={scenarios} />
              </section>
            ) : null}

            {error ? <ErrorMessage message={error} /> : null}

            <section className="grid gap-2 md:grid-cols-2">
              {selectedScenarios.map((scenario) => (
                <article
                  key={scenario.scenario_id}
                  className="rounded-lg border border-zinc-800 p-3"
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-medium">{scenario.name}</p>
                    <Badge variant="outline">{scenario.category}</Badge>
                  </div>
                  <p className="mt-1 text-xs text-zinc-500">
                    {scenario.description}
                  </p>
                </article>
              ))}
            </section>
          </TabsContent>

          <TabsContent value="history" className="space-y-3">
            {error ? <ErrorMessage message={error} /> : null}
            {history.length ? (
              history.map((run) => (
                <article
                  key={run.run_id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-zinc-800 p-4"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <RunBadge run={run} />
                      <span className="text-sm font-medium capitalize">
                        {run.suite} · {run.repetitions}×
                      </span>
                    </div>
                    <p className="mt-2 text-xs text-zinc-500">
                      {new Date(run.started_at).toLocaleString()} ·{" "}
                      {run.passed_count}/{run.scenario_count} passed
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={loadingRunId === run.run_id}
                    onClick={() => void showRun(run.run_id)}
                  >
                    {loadingRunId === run.run_id ? (
                      <Loader2Icon className="size-4 animate-spin" />
                    ) : (
                      <RotateCcwIcon className="size-4" />
                    )}
                    View evidence
                  </Button>
                </article>
              ))
            ) : (
              <p className="rounded-xl border border-dashed border-zinc-800 p-8 text-center text-sm text-zinc-500">
                No reliability runs have been recorded.
              </p>
            )}
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
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
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {children}
    </div>
  );
}

function ResultGrid({
  results,
  scenarios,
}: {
  results: ReliabilityScenarioResult[];
  scenarios: ReliabilityScenario[];
}) {
  return (
    <div className="grid gap-2 md:grid-cols-2">
      {results.map((result) => {
        const scenario = scenarios.find(
          (item) => item.scenario_id === result.scenario_id,
        );
        const passed = result.status === "passed";
        return (
          <article
            key={`${result.scenario_id}-${result.repetition}`}
            className={cn(
              "rounded-lg border p-3",
              passed
                ? "border-emerald-900 bg-emerald-950/20"
                : "border-red-900 bg-red-950/20",
            )}
          >
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-medium">
                {scenario?.name ?? result.scenario_id}
                {result.repetition > 1 ? ` #${result.repetition}` : ""}
              </p>
              {passed ? (
                <CheckCircle2Icon className="size-4 text-emerald-400" />
              ) : (
                <XCircleIcon className="size-4 text-red-400" />
              )}
            </div>
            <p className="mt-1 text-xs text-zinc-500">
              {Math.round(result.score * 100)}% ·{" "}
              {(result.duration_ms / 1000).toFixed(1)}s
            </p>
            {result.error ? (
              <p className="mt-2 text-xs text-red-300">{result.error}</p>
            ) : null}
            <ul className="mt-2 space-y-1 text-xs">
              {result.assertions
                .filter((assertion) => !assertion.passed)
                .map((assertion) => (
                  <li key={assertion.name} className="text-red-300">
                    {assertion.name.replaceAll("_", " ")}: {assertion.detail}
                  </li>
                ))}
            </ul>
          </article>
        );
      })}
    </div>
  );
}

function RunBadge({ run }: { run: ReliabilityBenchmarkRun }) {
  const passed = run.status === "passed";
  return (
    <Badge
      variant="outline"
      className={cn(
        passed
          ? "border-emerald-800 text-emerald-300"
          : "border-red-800 text-red-300",
      )}
    >
      {passed ? (
        <CheckCircle2Icon className="size-3" />
      ) : (
        <ShieldAlertIcon className="size-3" />
      )}
      {run.status}
    </Badge>
  );
}

function ErrorMessage({ message }: { message: string }) {
  return (
    <p className="rounded-lg border border-red-900 bg-red-950/30 p-3 text-sm text-red-300">
      {message}
    </p>
  );
}

function resultTitle(run: ReliabilityBenchmarkRun | null) {
  if (!run) return "Reliability results";
  return `${run.passed_count}/${run.scenario_count} scenarios passed`;
}

function messageFrom(reason: unknown) {
  return reason instanceof Error ? reason.message : "The request failed.";
}
