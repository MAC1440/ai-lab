"use client";

import {
    AlertCircleIcon,
    BotIcon,
    Loader2Icon,
    UserIcon,
} from "lucide-react";
import ReactMarkdown from "react-markdown";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { AgentExecutionDetails } from "@/features/home/components/agent-execution-details";
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
        <div
            className={cn(
                "flex gap-3 px-4 py-3",
                isUser ? "bg-transparent" : "bg-zinc-50/80 dark:bg-zinc-900/50",
            )}
        >
            <Avatar className="size-8">
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

            <div className="min-w-0 flex-1 space-y-2">
                <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
                    {isUser
                        ? "You"
                        : message.agentResult
                            ? `${message.agentResult.agent_id} agent`
                            : "Assistant"}
                </p>

                {!isUser && message.streamingStatus ? (
                    <div className="flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">
                        <Loader2Icon className="size-3.5 animate-spin" />
                        <span>{message.streamingStatus}</span>
                    </div>
                ) : null}

                <div className="space-y-2 text-sm leading-relaxed text-zinc-800 dark:text-zinc-200">
                    {message.reasoning ? (
                        <div className="rounded-lg border border-amber-200 bg-amber-50/80 p-2 text-xs italic text-amber-700 dark:border-amber-900/50 dark:bg-amber-950/20 dark:text-amber-300">
                            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide opacity-80">
                                Thinking
                            </p>
                            <p className="whitespace-pre-wrap">{message.reasoning}</p>
                        </div>
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

                {!isUser && message.streamError ? (
                    <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-2 text-xs text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">
                        <AlertCircleIcon className="mt-0.5 size-3.5 shrink-0" />
                        <span>{message.streamError}</span>
                    </div>
                ) : null}

                {!isUser && message.agentResult ? (
                    <AgentExecutionDetails result={message.agentResult} />
                ) : null}

                {!isUser && message.metrics ? (
                    <div className="rounded-md border border-zinc-200 bg-zinc-100/80 p-2 text-[11px] text-zinc-600 dark:border-zinc-800 dark:bg-zinc-800/70 dark:text-zinc-300">
                        <div className="flex flex-wrap gap-3">
                            {message.metrics.tokensPerSecond != null ? (
                                <span>
                                    Throughput: {message.metrics.tokensPerSecond} tok/s
                                </span>
                            ) : null}

                            {message.metrics.totalDurationMs != null ? (
                                <span>
                                    Total: {(message.metrics.totalDurationMs / 1000).toFixed(1)}s
                                </span>
                            ) : null}

                            {message.metrics.promptEvalCount != null ? (
                                <span>Input tokens: {message.metrics.promptEvalCount}</span>
                            ) : null}

                            {message.metrics.evalCount != null ? (
                                <span>Output tokens: {message.metrics.evalCount}</span>
                            ) : null}

                            {message.metrics.doneReason ? (
                                <span>Done: {message.metrics.doneReason}</span>
                            ) : null}
                        </div>
                    </div>
                ) : null}
            </div>
        </div>
    );
}