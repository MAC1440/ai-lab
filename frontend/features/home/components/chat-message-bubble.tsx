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
                    : "bg-surface-hover/60",
            )}
        >
            <Avatar className="size-8 shrink-0">
                <AvatarFallback
                    className={cn(
                        isUser
                            ? "bg-pending/15 text-pending"
                            : "bg-accent/15 text-accent",
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
                    <p className="text-xs font-medium text-muted-foreground">
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

                <div className="space-y-2 text-sm leading-relaxed text-foreground">
                    {message.reasoning ? (
                        <details className="rounded-lg border border-accent/30 bg-accent/5 p-2 text-xs text-accent">
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
                            <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse rounded-sm bg-accent" />
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
