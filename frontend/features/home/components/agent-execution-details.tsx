"use client";

import type { AgentChatResponse } from "@/features/agents/agent-api";

function formatDistance(distance: number | null | undefined) {
    return typeof distance === "number" ? distance.toFixed(4) : "unknown";
}

export function AgentExecutionDetails({
    result,
}: {
    result: AgentChatResponse;
}) {
    const hasTools = result.tools_used.length > 0;
    const hasRagDetails = result.rag.enabled;

    return (
        <details className="group rounded-lg border border-zinc-200 bg-white/70 text-xs dark:border-zinc-800 dark:bg-zinc-950/50">
            <summary className="flex cursor-pointer list-none flex-wrap items-center gap-2 px-3 py-2 text-zinc-600 marker:hidden dark:text-zinc-300">
                <span className="font-medium">Execution details</span>

                <span className="rounded-full bg-zinc-100 px-2 py-0.5 dark:bg-zinc-800">
                    {result.model}
                </span>

                <span className="rounded-full bg-zinc-100 px-2 py-0.5 dark:bg-zinc-800">
                    {result.steps} {result.steps === 1 ? "step" : "steps"}
                </span>

                {hasRagDetails ? (
                    <span
                        className={
                            result.rag.context_found
                                ? "rounded-full bg-emerald-100 px-2 py-0.5 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300"
                                : "rounded-full bg-amber-100 px-2 py-0.5 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300"
                        }
                    >
                        {result.rag.context_found ? "RAG context found" : "No RAG context"}
                    </span>
                ) : (
                    <span className="rounded-full bg-zinc-100 px-2 py-0.5 dark:bg-zinc-800">
                        RAG disabled
                    </span>
                )}

                {hasTools ? (
                    <span className="rounded-full bg-violet-100 px-2 py-0.5 text-violet-700 dark:bg-violet-950/50 dark:text-violet-300">
                        {result.tools_used.length} tool call
                        {result.tools_used.length === 1 ? "" : "s"}
                    </span>
                ) : null}

                <span className="ml-auto text-[10px] uppercase tracking-wide text-zinc-400 group-open:hidden">
                    Show
                </span>
                <span className="ml-auto hidden text-[10px] uppercase tracking-wide text-zinc-400 group-open:inline">
                    Hide
                </span>
            </summary>

            <div className="space-y-4 border-t border-zinc-200 px-3 py-3 dark:border-zinc-800">
                <section>
                    <h4 className="font-semibold text-zinc-800 dark:text-zinc-200">
                        Agent
                    </h4>
                    <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-zinc-600 dark:text-zinc-400">
                        <dt>Agent ID</dt>
                        <dd className="font-mono">{result.agent_id}</dd>

                        <dt>Model</dt>
                        <dd className="font-mono">{result.model}</dd>

                        <dt>Loop steps</dt>
                        <dd>{result.steps}</dd>
                    </dl>
                </section>

                <section>
                    <h4 className="font-semibold text-zinc-800 dark:text-zinc-200">
                        Retrieval
                    </h4>

                    {!result.rag.enabled ? (
                        <p className="mt-2 text-zinc-500">
                            Retrieval was disabled for this agent.
                        </p>
                    ) : (
                        <div className="mt-2 space-y-2">
                            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-zinc-600 dark:text-zinc-400">
                                <dt>Context found</dt>
                                <dd>{result.rag.context_found ? "Yes" : "No"}</dd>

                                <dt>Retrieved</dt>
                                <dd>{result.rag.retrieved_count}</dd>

                                <dt>Included</dt>
                                <dd>{result.rag.included_count}</dd>

                                <dt>Threshold</dt>
                                <dd>
                                    {result.rag.distance_threshold == null
                                        ? "Disabled"
                                        : result.rag.distance_threshold}
                                </dd>
                            </dl>

                            {result.rag.sources.length > 0 ? (
                                <div className="space-y-2">
                                    {result.rag.sources.map((source, index) => (
                                        <div
                                            key={`${String(source.source ?? "source")}-${String(
                                                source.chunk_index ?? index,
                                            )}-${index}`}
                                            className="rounded-md border border-zinc-200 bg-zinc-50 p-2 dark:border-zinc-800 dark:bg-zinc-900"
                                        >
                                            <div className="flex flex-wrap gap-x-3 gap-y-1">
                                                <span>
                                                    Source:{" "}
                                                    <strong>{String(source.source ?? "unknown")}</strong>
                                                </span>
                                                <span>
                                                    Chunk:{" "}
                                                    <strong>
                                                        {String(source.chunk_index ?? "unknown")}
                                                    </strong>
                                                </span>
                                                <span>
                                                    Distance:{" "}
                                                    <strong>
                                                        {formatDistance(result.rag.distances[index])}
                                                    </strong>
                                                </span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-zinc-500">
                                    No document chunks were included in the model context.
                                </p>
                            )}
                        </div>
                    )}
                </section>

                <section>
                    <h4 className="font-semibold text-zinc-800 dark:text-zinc-200">
                        Tools
                    </h4>

                    {!hasTools ? (
                        <p className="mt-2 text-zinc-500">
                            The model produced the answer without calling a tool.
                        </p>
                    ) : (
                        <div className="mt-2 space-y-2">
                            {result.tools_used.map((tool, index) => (
                                <div
                                    key={`${tool.name}-${index}`}
                                    className="rounded-md border border-zinc-200 bg-zinc-50 p-2 dark:border-zinc-800 dark:bg-zinc-900"
                                >
                                    <div className="flex items-center justify-between gap-3">
                                        <code className="font-semibold">{tool.name}</code>
                                        <span
                                            className={
                                                tool.status === "success"
                                                    ? "text-emerald-600 dark:text-emerald-400"
                                                    : "text-red-600 dark:text-red-400"
                                            }
                                        >
                                            {tool.status}
                                        </span>
                                    </div>

                                    <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words rounded bg-zinc-100 p-2 text-[11px] dark:bg-zinc-950">
                                        {JSON.stringify(tool.arguments, null, 2)}
                                    </pre>

                                    {tool.error ? (
                                        <p className="mt-2 text-red-600 dark:text-red-400">
                                            {tool.error}
                                        </p>
                                    ) : null}
                                </div>
                            ))}
                        </div>
                    )}
                </section>
            </div>
        </details>
    );
}