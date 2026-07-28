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
            <div className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger">
                <AlertCircleIcon className="mt-0.5 size-3.5 shrink-0" />
                <div className="min-w-0">
                    <p className="font-medium">
                        Agent run failed
                    </p>
                    <p className="mt-0.5 break-words text-danger/90">
                        {error}
                    </p>
                </div>
            </div>
        );
    }

    if (isStreaming) {
        return (
            <div className="flex items-center gap-2 rounded-lg border border-pending/30 bg-pending/10 px-3 py-2 text-xs text-pending">
                <Loader2Icon className="size-3.5 animate-spin" />
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
                "text-success",
            )}
        >
            <CheckCircle2Icon className="size-3.5" />
            <span>{status}</span>
        </div>
    );
}
