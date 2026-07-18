"use client";

import { Loader2Icon } from "lucide-react";

import type {
    AgentChatResponse,
    AgentToolExecution,
} from "@/features/agents/agent-api";

function formatDistance(distance: number | null | undefined) {
    return typeof distance === "number" ? distance.toFixed(4) : "unknown";
}

function ToolStatus({ tool }: { tool: AgentToolExecution }) {
    if (tool.status === "running") {
        return (
            <span className="flex items-center gap-1 text-amber-600 dark:text-amber-400">
                <Loader2Icon className="size-3 animate-spin" />
                running
            </span>
        );
    }

    return (
        <span
            className={
                tool.status === "success"
                    ? "text-emerald-600 dark:text-emerald-400"
                    : "text-red-600 dark:text-red-400"
            }
        >
            {tool.status}
        </span>
    );
}

export function AgentExecutionDetails({
    result,
}: {
    result: AgentChatResponse;
}) {
    const hasTools = result.tools_used.length > 0;
    const hasRagDetails = result.rag.enabled;
    const projectContext = result.context;
    const hasProjectContext = projectContext?.enabled === true;

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

                {hasProjectContext ? (
                    <span className="rounded-full bg-sky-100 px-2 py-0.5 text-sky-700 dark:bg-sky-950/50 dark:text-sky-300">
                        {projectContext.file_count} context file
                        {projectContext.file_count === 1 ? "" : "s"}
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
                        Project context
                    </h4>

                    {!hasProjectContext ? (
                        <p className="mt-2 text-zinc-500">
                            Deterministic project context was disabled for this agent.
                        </p>
                    ) : (
                        <div className="mt-2 space-y-2">
                            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-zinc-600 dark:text-zinc-400">
                                <dt>Project types</dt>
                                <dd>{projectContext.project_types.join(", ") || "unknown"}</dd>

                                <dt>Selected root</dt>
                                <dd className="font-mono">
                                    {projectContext.selected_project_root ?? "."}
                                </dd>

                                <dt>Tree entries</dt>
                                <dd>
                                    {projectContext.tree_entries}
                                    {projectContext.tree_truncated ? " (truncated)" : ""}
                                </dd>

                                <dt>Context size</dt>
                                <dd>
                                    {projectContext.characters.toLocaleString()} /{" "}
                                    {projectContext.max_characters.toLocaleString()} characters
                                </dd>
                            </dl>

                            {projectContext.files_included.length > 0 ? (
                                <div className="rounded-md border border-zinc-200 bg-zinc-50 p-2 dark:border-zinc-800 dark:bg-zinc-900">
                                    <p className="font-medium text-zinc-700 dark:text-zinc-300">
                                        Preloaded files
                                    </p>
                                    <ul className="mt-1 space-y-1 font-mono text-[11px] text-zinc-600 dark:text-zinc-400">
                                        {projectContext.files_included.map((path) => (
                                            <li key={path} className="break-all">
                                                {path}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            ) : (
                                <p className="text-zinc-500">
                                    No files were preloaded; the project tree is still available.
                                </p>
                            )}
                        </div>
                    )}
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
                                                    Source: <strong>{String(source.source ?? "unknown")}</strong>
                                                </span>
                                                <span>
                                                    Chunk:{" "}
                                                    <strong>{String(source.chunk_index ?? "unknown")}</strong>
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
                            The model has not called a tool for this response.
                        </p>
                    ) : (
                        <div className="mt-2 space-y-2">
                            {result.tools_used.map((tool, index) => (
                                <div
                                    key={tool.id ?? `${tool.name}-${index}`}
                                    className="rounded-md border border-zinc-200 bg-zinc-50 p-2 dark:border-zinc-800 dark:bg-zinc-900"
                                >
                                    <div className="flex items-center justify-between gap-3">
                                        <code className="font-semibold">{tool.name}</code>
                                        <ToolStatus tool={tool} />
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
