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
        <section className="rounded-xl border border-border bg-surface-hover/60 p-3 text-xs shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 font-medium text-foreground">
                    {metrics.live ? (
                        <ActivityIcon className="size-3.5 animate-pulse text-pending" />
                    ) : (
                        <GaugeIcon className="size-3.5 text-accent" />
                    )}
                    <span>Model performance</span>
                </div>

                <span className="rounded-full bg-surface px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
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

            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t border-border pt-2 text-[11px] text-muted-foreground">
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
        <div className="rounded-lg bg-surface px-3 py-2">
            <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                {label}
            </p>
            <p className="mt-0.5 font-mono font-semibold tabular-nums text-foreground">
                {value}
            </p>
        </div>
    );
}
