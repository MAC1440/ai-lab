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
            <span className="flex items-center gap-1 text-pending dark:text-pending">
                <Loader2Icon className="size-3 animate-spin" />
                running
            </span>
        );
    }

    return (
        <span
            className={
                tool.status === "success"
                    ? "text-success dark:text-success"
                    : "text-danger dark:text-danger"
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
        <details className="group rounded-lg border border-border bg-surface/70 text-xs dark:border-border dark:bg-surface-raised/50">
            <summary className="flex cursor-pointer list-none flex-wrap items-center gap-2 px-3 py-2 text-muted-foreground marker:hidden dark:text-muted-foreground">
                <span className="font-medium">Execution details</span>

                <span className="rounded-full bg-surface-hover px-2 py-0.5 dark:bg-surface-hover">
                    {result.model}
                </span>

                <span className="rounded-full bg-surface-hover px-2 py-0.5 dark:bg-surface-hover">
                    {result.steps} {result.steps === 1 ? "step" : "steps"}
                </span>

                {hasRagDetails ? (
                    <span
                        className={
                            result.rag.context_found
                                ? "rounded-full bg-success/10 px-2 py-0.5 text-success dark:bg-success/10 dark:text-success"
                                : "rounded-full bg-pending/10 px-2 py-0.5 text-pending dark:bg-pending/10 dark:text-pending"
                        }
                    >
                        {result.rag.context_found ? "RAG context found" : "No RAG context"}
                    </span>
                ) : (
                    <span className="rounded-full bg-surface-hover px-2 py-0.5 dark:bg-surface-hover">
                        RAG disabled
                    </span>
                )}

                {hasTools ? (
                    <span className="rounded-full bg-pending/15 px-2 py-0.5 text-pending dark:bg-pending/15 dark:text-pending">
                        {result.tools_used.length} tool call
                        {result.tools_used.length === 1 ? "" : "s"}
                    </span>
                ) : null}

                {hasProjectContext ? (
                    <span className="rounded-full bg-pending/10 px-2 py-0.5 text-pending dark:bg-pending/10 dark:text-pending">
                        {projectContext.file_count} context file
                        {projectContext.file_count === 1 ? "" : "s"}
                    </span>
                ) : null}

                <span className="ml-auto text-[10px] uppercase tracking-wide text-muted-foreground group-open:hidden">
                    Show
                </span>
                <span className="ml-auto hidden text-[10px] uppercase tracking-wide text-muted-foreground group-open:inline">
                    Hide
                </span>
            </summary>

            <div className="space-y-4 border-t border-border px-3 py-3 dark:border-border">
                <section>
                    <h4 className="font-semibold text-foreground dark:text-foreground">
                        Agent
                    </h4>
                    <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-muted-foreground dark:text-muted-foreground">
                        <dt>Agent ID</dt>
                        <dd className="font-mono">{result.agent_id}</dd>

                        <dt>Model</dt>
                        <dd className="font-mono">{result.model}</dd>

                        <dt>Loop steps</dt>
                        <dd>{result.steps}</dd>
                    </dl>
                </section>

                <section>
                    <h4 className="font-semibold text-foreground dark:text-foreground">
                        Project context
                    </h4>

                    {!hasProjectContext ? (
                        <p className="mt-2 text-muted-foreground">
                            Deterministic project context was disabled for this agent.
                        </p>
                    ) : (
                        <div className="mt-2 space-y-2">
                            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-muted-foreground dark:text-muted-foreground">
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
                                <div className="rounded-md border border-border bg-surface-hover p-2 dark:border-border dark:bg-surface-raised">
                                    <p className="font-medium text-foreground dark:text-muted-foreground">
                                        Preloaded files
                                    </p>
                                    <ul className="mt-1 space-y-1 font-mono text-[11px] text-muted-foreground dark:text-muted-foreground">
                                        {projectContext.files_included.map((path) => (
                                            <li key={path} className="break-all">
                                                {path}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            ) : (
                                <p className="text-muted-foreground">
                                    No files were preloaded; the project tree is still available.
                                </p>
                            )}
                        </div>
                    )}
                </section>

                <section>
                    <h4 className="font-semibold text-foreground dark:text-foreground">
                        Retrieval
                    </h4>

                    {!result.rag.enabled ? (
                        <p className="mt-2 text-muted-foreground">
                            Retrieval was disabled for this agent.
                        </p>
                    ) : (
                        <div className="mt-2 space-y-2">
                            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-muted-foreground dark:text-muted-foreground">
                                <dt>Context found</dt>
                                <dd>{result.rag.context_found ? "Yes" : "No"}</dd>

                                <dt>Configuration</dt>
                                <dd>
                                    {result.rag.resolved_from === "request"
                                        ? "Frontend override"
                                        : result.rag.resolved_from === "legacy_request"
                                            ? "Legacy override"
                                            : "Agent profile"}
                                </dd>

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
                                            className="rounded-md border border-border bg-surface-hover p-2 dark:border-border dark:bg-surface-raised"
                                        >
                                            <div className="flex flex-wrap gap-x-3 gap-y-1">
                                                <span>
                                                    Source: <strong>{String(source.source ?? "unknown")}</strong>
                                                </span>
                                                {source.title ? (
                                                    <span>
                                                        Page: <strong>{source.title}</strong>
                                                    </span>
                                                ) : null}
                                                {source.heading ? (
                                                    <span>
                                                        Section: <strong>{source.heading}</strong>
                                                    </span>
                                                ) : null}
                                                {source.unity_version ? (
                                                    <span>
                                                        Version: <strong>{source.unity_version}</strong>
                                                    </span>
                                                ) : null}
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
                                            {source.source_url ? (
                                                <a
                                                    href={source.source_url}
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className="mt-1 inline-block text-pending underline underline-offset-2 dark:text-pending"
                                                >
                                                    Open official Unity documentation
                                                </a>
                                            ) : null}
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-muted-foreground">
                                    No document chunks were included in the model context.
                                </p>
                            )}
                        </div>
                    )}
                </section>

                <section>
                    <h4 className="font-semibold text-foreground dark:text-foreground">
                        Tools
                    </h4>

                    {!hasTools ? (
                        <p className="mt-2 text-muted-foreground">
                            The model has not called a tool for this response.
                        </p>
                    ) : (
                        <div className="mt-2 space-y-2">
                            {result.tools_used.map((tool, index) => (
                                <div
                                    key={tool.id ?? `${tool.name}-${index}`}
                                    className="rounded-md border border-border bg-surface-hover p-2 dark:border-border dark:bg-surface-raised"
                                >
                                    <div className="flex items-center justify-between gap-3">
                                        <code className="font-semibold">{tool.name}</code>
                                        <ToolStatus tool={tool} />
                                    </div>

                                    <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words rounded bg-surface-hover p-2 text-[11px] dark:bg-surface-raised">
                                        {JSON.stringify(tool.arguments, null, 2)}
                                    </pre>

                                    {tool.error ? (
                                        <p className="mt-2 text-danger dark:text-danger">
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
