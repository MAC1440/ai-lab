"use client";

import {
    BotIcon,
    UserIcon,
} from "lucide-react";
import ReactMarkdown from "react-markdown";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { AgentExecutionDetails } from "@/features/home/components/agent-execution-details";
import { AgentRunStatus } from "@/features/home/components/agent-run-status";
import { ModelRunMetrics } from "@/features/home/components/model-run-metrics";
import type { HomeChatMessage } from "@/features/home/types";
import { cn } from "@/lib/utils";

export function ChatMessageBubble({
    message,
    isStreaming = false,
}: {
    message: HomeChatMessage;
    isStreaming?: boolean;
}) {
    const isUser = message.role === "user";

    return (
        <article
            className={cn(
                "flex gap-3 px-4 py-4",
                isUser
                    ? "bg-transparent"
                    : "bg-zinc-50/80 dark:bg-zinc-900/50",
            )}
        >
            <Avatar className="size-8 shrink-0">
                <AvatarFallback
                    className={cn(
                        isUser
                            ? "bg-violet-100 text-violet-700 dark:bg-violet-900/50 dark:text-violet-300"
                            : "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300",
                    )}
                >
                    {isUser ? (
                        <UserIcon className="size-4" />
                    ) : (
                        <BotIcon className="size-4" />
                    )}
                </AvatarFallback>
            </Avatar>

            <div className="min-w-0 flex-1 space-y-3">
                <header className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
                        {isUser
                            ? "You"
                            : message.agentResult
                                ? `${message.agentResult.agent_id} agent`
                                : "Assistant"}
                    </p>
                </header>

                {!isUser ? (
                    <AgentRunStatus
                        status={message.streamingStatus}
                        error={message.streamError}
                        isStreaming={isStreaming}
                    />
                ) : null}

                <div className="space-y-2 text-sm leading-relaxed text-zinc-800 dark:text-zinc-200">
                    {message.reasoning ? (
                        <details className="rounded-lg border border-amber-200 bg-amber-50/80 p-2 text-xs text-amber-700 dark:border-amber-900/50 dark:bg-amber-950/20 dark:text-amber-300">
                            <summary className="cursor-pointer select-none font-semibold">
                                Reasoning
                            </summary>
                            <p className="mt-2 whitespace-pre-wrap italic">
                                {message.reasoning}
                            </p>
                        </details>
                    ) : null}

                    <div className="prose prose-sm max-w-none dark:prose-invert">
                        <ReactMarkdown>
                            {message.content || (isStreaming ? "…" : "")}
                        </ReactMarkdown>

                        {isStreaming && message.content ? (
                            <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse rounded-sm bg-emerald-500" />
                        ) : null}
                    </div>
                </div>

                {!isUser && message.agentResult ? (
                    <AgentExecutionDetails
                        result={message.agentResult}
                    />
                ) : null}

                {!isUser && message.metrics ? (
                    <ModelRunMetrics metrics={message.metrics} />
                ) : null}
            </div>
        </article>
    );
}
