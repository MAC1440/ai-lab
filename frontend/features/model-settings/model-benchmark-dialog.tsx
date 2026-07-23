"use client";

import {
  ActivityIcon,
  CheckCircle2Icon,
  GaugeIcon,
  Loader2Icon,
  PlayIcon,
  XCircleIcon,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { AgentProfile } from "@/features/agents/agent-api";
import {
  type BenchmarkStage,
  type BenchmarkStageResult,
  getModelRecommendations,
  type ModelRecommendations,
  streamModelBenchmark,
} from "@/features/model-settings/model-benchmark-api";
import { cn } from "@/lib/utils";

const STAGES: BenchmarkStage[] = ["planning", "generation", "repair"];

export function ModelBenchmarkDialog({
  agents,
  disabled = false,
}: {
  agents: AgentProfile[];
  disabled?: boolean;
}) {
  const availableAgents = agents.filter((agent) =>
    ["coding", "unity", "web"].includes(agent.id),
  );
  const [open, setOpen] = useState(false);
  const [agentId, setAgentId] = useState<"coding" | "unity" | "web">("coding");
  const [running, setRunning] = useState(false);
  const [currentStage, setCurrentStage] = useState<BenchmarkStage | null>(null);
  const [results, setResults] = useState<BenchmarkStageResult[]>([]);
  const [recommendations, setRecommendations] =
    useState<ModelRecommendations | null>(null);
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!open) return;
    void getModelRecommendations()
      .then(setRecommendations)
      .catch((reason: unknown) =>
        setError(
          reason instanceof Error
            ? reason.message
            : "Recommendations could not be loaded.",
        ),
      );
  }, [open]);

  useEffect(
    () => () => {
      controllerRef.current?.abort();
    },
    [],
  );

  async function runBenchmark() {
    if (running) return;
    const controller = new AbortController();
    controllerRef.current = controller;
    setRunning(true);
    setResults([]);
    setCurrentStage(null);
    setError(null);
    try {
      for await (const event of streamModelBenchmark(
        agentId,
        controller.signal,
      )) {
        if (event.type === "benchmark_stage_started" && event.stage) {
          setCurrentStage(event.stage);
        } else if (
          event.type === "benchmark_stage_done" &&
          event.result
        ) {
          setResults((current) => [
            ...current.filter(
              (item) => item.stage !== event.result?.stage,
            ),
            event.result as BenchmarkStageResult,
          ]);
        } else if (event.type === "benchmark_done") {
          if (event.results) setResults(event.results);
          if (event.recommendations) {
            setRecommendations(event.recommendations);
          }
          setCurrentStage(null);
        }
      }
    } catch (reason) {
      const stopped =
        reason instanceof DOMException && reason.name === "AbortError";
      if (!stopped) {
        setError(
          reason instanceof Error ? reason.message : "Benchmark failed.",
        );
      }
    } finally {
      controllerRef.current = null;
      setRunning(false);
      setCurrentStage(null);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) controllerRef.current?.abort();
        setOpen(nextOpen);
      }}
    >
      <DialogTrigger asChild>
        <Button type="button" variant="outline" size="sm" disabled={disabled}>
          <GaugeIcon className="size-4" />
          Benchmarks
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto">
        <DialogTitle>Local model coding benchmark</DialogTitle>
        <DialogDescription>
          Measure structured planning, complete-file generation, and bounded
          repair. Results update capability scores but never change model
          assignments automatically.
        </DialogDescription>

        <section className="flex flex-wrap items-end gap-3 rounded-xl border border-zinc-800 bg-zinc-950 p-4">
          <div className="min-w-48 flex-1 space-y-1.5">
            <Label>Agent assignment to test</Label>
            <Select
              value={agentId}
              disabled={running}
              onValueChange={(value) =>
                setAgentId(value as typeof agentId)
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {availableAgents.map((agent) => (
                  <SelectItem key={agent.id} value={agent.id}>
                    {agent.name}
                  </SelectItem>
                ))}
                {!availableAgents.length ? (
                  <>
                    <SelectItem value="coding">Coding</SelectItem>
                    <SelectItem value="unity">Unity</SelectItem>
                    <SelectItem value="web">Web</SelectItem>
                  </>
                ) : null}
              </SelectContent>
            </Select>
          </div>
          <Button disabled={running} onClick={() => void runBenchmark()}>
            {running ? (
              <Loader2Icon className="size-4 animate-spin" />
            ) : (
              <PlayIcon className="size-4" />
            )}
            {running
              ? `Running ${currentStage ?? "benchmark"}…`
              : "Run all three stages"}
          </Button>
        </section>

        {error ? (
          <p className="rounded-lg border border-red-900 bg-red-950/30 p-3 text-sm text-red-300">
            {error}
          </p>
        ) : null}

        <section className="grid gap-3 md:grid-cols-3">
          {STAGES.map((stage) => {
            const result = results.find((item) => item.stage === stage);
            const isCurrent = running && currentStage === stage;
            return (
              <article
                key={stage}
                className={cn(
                  "rounded-xl border border-zinc-800 bg-zinc-950 p-4",
                  isCurrent && "border-sky-800",
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold capitalize">{stage}</h3>
                  {isCurrent ? (
                    <Loader2Icon className="size-4 animate-spin text-sky-400" />
                  ) : result?.status === "passed" ? (
                    <CheckCircle2Icon className="size-4 text-emerald-400" />
                  ) : result ? (
                    <XCircleIcon className="size-4 text-red-400" />
                  ) : (
                    <ActivityIcon className="size-4 text-zinc-600" />
                  )}
                </div>
                {result ? (
                  <div className="mt-3 space-y-2 text-xs text-zinc-400">
                    <p className="flex items-center gap-2">
                      <Badge variant="outline">
                        {Math.round(result.score * 100)}%
                      </Badge>
                      {(result.duration_ms / 1000).toFixed(1)}s
                    </p>
                    <p className="truncate" title={result.model}>
                      {result.provider_id}/{result.model}
                    </p>
                    <p>
                      {result.tokens_per_second
                        ? `${result.tokens_per_second.toFixed(1)} tokens/s`
                        : "Speed unavailable"}
                    </p>
                    {result.error ? (
                      <p className="text-red-300">{result.error}</p>
                    ) : null}
                    <ul className="space-y-1">
                      {result.assertions.map((assertion) => (
                        <li
                          key={assertion.name}
                          className={
                            assertion.passed
                              ? "text-emerald-400"
                              : "text-red-400"
                          }
                        >
                          {assertion.passed ? "✓" : "✕"}{" "}
                          {assertion.name.replaceAll("_", " ")}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <p className="mt-3 text-xs text-zinc-600">
                    Not measured in this session.
                  </p>
                )}
              </article>
            );
          })}
        </section>

        <section className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
          <h3 className="text-sm font-semibold">
            Measured assignment recommendations
          </h3>
          <p className="mt-1 text-xs text-zinc-500">
            Based on {recommendations?.benchmarked_model_count ?? 0} benchmarked
            model profile(s). Recommendations remain advisory.
          </p>
          <div className="mt-3 grid gap-3 md:grid-cols-3">
            {STAGES.map((stage) => {
              const recommendation =
                recommendations?.recommendations[stage] ?? null;
              return (
                <div
                  key={stage}
                  className="rounded-lg border border-zinc-800 p-3"
                >
                  <p className="text-xs font-medium capitalize text-zinc-300">
                    {stage}
                  </p>
                  {recommendation ? (
                    <>
                      <p
                        className="mt-2 truncate text-sm text-zinc-100"
                        title={recommendation.model}
                      >
                        {recommendation.model}
                      </p>
                      <p className="mt-1 text-xs text-zinc-500">
                        {Math.round(recommendation.score * 100)}% ·{" "}
                        {recommendation.measured_tokens_per_second
                          ? `${recommendation.measured_tokens_per_second.toFixed(1)} tok/s`
                          : "speed unavailable"}
                      </p>
                    </>
                  ) : (
                    <p className="mt-2 text-xs text-zinc-600">
                      Run a benchmark first.
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      </DialogContent>
    </Dialog>
  );
}
