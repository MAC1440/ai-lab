import type { AgentRuntimeMetric } from "@/features/agents/agent-api";
import type { OllamaCompletionMetrics } from "@/features/home/types";

export function mapRuntimeMetric(
    metric: AgentRuntimeMetric,
    current?: OllamaCompletionMetrics,
): OllamaCompletionMetrics {
    return {
        ...current,
        totalDurationMs: metric.duration_seconds * 1000,
        promptEvalCount:
            metric.input_tokens ?? current?.promptEvalCount,
        evalCount: metric.output_tokens,
        tokensPerSecond:
            metric.tokens_per_second ?? undefined,
        contextWindow: metric.context_window,
        contextUsedTokens:
            metric.context_used_tokens
            ?? current?.contextUsedTokens,
        contextRemainingTokens:
            metric.context_remaining_tokens
            ?? current?.contextRemainingTokens,
        maxOutputTokens: metric.max_tokens,
        safeInputTokens:
            metric.safe_input_tokens
            ?? current?.safeInputTokens,
        temperature: metric.temperature,
        live: !metric.final,
        metricKind: metric.metric_kind,
    };
}
