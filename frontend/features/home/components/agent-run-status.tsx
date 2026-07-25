"use client";

import {
    AlertCircleIcon,
    CheckCircle2Icon,
    Loader2Icon,
} from "lucide-react";

import { cn } from "@/lib/utils";

export function AgentRunStatus({
    status,
    error,
    isStreaming,
}: {
    status?: string;
    error?: string;
    isStreaming: boolean;
}) {
    if (error) {
        return (
            <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">
                <AlertCircleIcon className="mt-0.5 size-3.5 shrink-0" />
                <div className="min-w-0">
                    <p className="font-medium">
                        Agent run failed
                    </p>
                    <p className="mt-0.5 break-words text-red-600/90 dark:text-red-300/90">
                        {error}
                    </p>
                </div>
            </div>
        );
    }

    if (isStreaming) {
        return (
            <div className="flex items-center gap-2 rounded-lg border border-zinc-200 bg-white/70 px-3 py-2 text-xs text-zinc-600 shadow-sm dark:border-zinc-800 dark:bg-zinc-950/40 dark:text-zinc-300">
                <Loader2Icon className="size-3.5 animate-spin text-emerald-500" />
                <span className="truncate">
                    {status || "Working…"}
                </span>
            </div>
        );
    }

    if (!status) {
        return null;
    }

    return (
        <div
            className={cn(
                "flex items-center gap-2 text-xs",
                "text-emerald-700 dark:text-emerald-300",
            )}
        >
            <CheckCircle2Icon className="size-3.5" />
            <span>{status}</span>
        </div>
    );
}
