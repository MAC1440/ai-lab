"use client";

import { ActivityIcon, GaugeIcon } from "lucide-react";

import type { OllamaCompletionMetrics } from "@/features/home/types";

export function ModelRunMetrics({
    metrics,
}: {
    metrics: OllamaCompletionMetrics;
}) {
    const speedLabel = metrics.live
        ? "Estimated stream rate"
        : "Generation throughput";

    return (
        <section className="rounded-xl border border-zinc-200/80 bg-white/70 p-3 text-xs shadow-sm dark:border-zinc-800 dark:bg-zinc-950/40">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 font-medium text-zinc-700 dark:text-zinc-200">
                    {metrics.live ? (
                        <ActivityIcon className="size-3.5 animate-pulse text-emerald-500" />
                    ) : (
                        <GaugeIcon className="size-3.5 text-emerald-500" />
                    )}
                    <span>Model performance</span>
                </div>

                <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-[10px] font-medium text-zinc-500 dark:bg-zinc-900 dark:text-zinc-400">
                    {metrics.live ? "Live estimate" : "Completed run"}
                </span>
            </div>

            <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                <Metric
                    label={speedLabel}
                    value={
                        metrics.tokensPerSecond == null
                            ? "Unavailable"
                            : `${metrics.tokensPerSecond.toFixed(2)} tok/s`
                    }
                />
                <Metric
                    label="Elapsed"
                    value={
                        metrics.totalDurationMs == null
                            ? "Unavailable"
                            : `${(metrics.totalDurationMs / 1000).toFixed(1)}s`
                    }
                />
                <Metric
                    label="Input tokens"
                    value={
                        metrics.promptEvalCount == null
                            ? metrics.live
                                ? "After completion"
                                : "Unavailable"
                            : metrics.promptEvalCount.toLocaleString()
                    }
                />
                <Metric
                    label="Output tokens"
                    value={
                        metrics.evalCount == null
                            ? "Unavailable"
                            : metrics.evalCount.toLocaleString()
                    }
                />
            </div>

            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t border-zinc-200/70 pt-2 text-[11px] text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
                {metrics.contextWindow != null ? (
                    <span>
                        Context window: {metrics.contextWindow.toLocaleString()}
                    </span>
                ) : null}

                {metrics.contextUsedTokens != null ? (
                    <span>
                        Used: {metrics.contextUsedTokens.toLocaleString()}
                    </span>
                ) : metrics.live ? (
                    <span>Context use: available after completion</span>
                ) : null}

                {metrics.contextRemainingTokens != null ? (
                    <span>
                        Remaining:{" "}
                        {metrics.contextRemainingTokens.toLocaleString()}
                    </span>
                ) : null}

                {metrics.maxOutputTokens != null ? (
                    <span>
                        Max output:{" "}
                        {metrics.maxOutputTokens.toLocaleString()}
                    </span>
                ) : null}

                {metrics.temperature != null ? (
                    <span>Temperature: {metrics.temperature}</span>
                ) : null}
            </div>
        </section>
    );
}

function Metric({
    label,
    value,
}: {
    label: string;
    value: string;
}) {
    return (
        <div className="rounded-lg bg-zinc-100/70 px-3 py-2 dark:bg-zinc-900/70">
            <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-400">
                {label}
            </p>
            <p className="mt-0.5 font-semibold tabular-nums text-zinc-700 dark:text-zinc-200">
                {value}
            </p>
        </div>
    );
}
