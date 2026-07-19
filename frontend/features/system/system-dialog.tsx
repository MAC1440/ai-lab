"use client";

import {
    AlertTriangleIcon,
    CheckCircle2Icon,
    DownloadIcon,
    HeartPulseIcon,
    Loader2Icon,
    RefreshCwIcon,
    XCircleIcon,
} from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
    downloadSystemBackup,
    getSystemDiagnostics,
    type SystemCheck,
    type SystemDiagnostics,
} from "./system-api";

const styles = {
    pass: "border-emerald-200 bg-emerald-50 dark:border-emerald-900 dark:bg-emerald-950/30",
    warning: "border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/30",
    fail: "border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950/30",
};

function CheckIcon({ status }: { status: SystemCheck["status"] }) {
    if (status === "pass") return <CheckCircle2Icon className="size-5 shrink-0 text-emerald-600" />;
    if (status === "warning") return <AlertTriangleIcon className="size-5 shrink-0 text-amber-600" />;
    return <XCircleIcon className="size-5 shrink-0 text-red-600" />;
}

export function SystemDialog({ disabled = false }: { disabled?: boolean }) {
    const [open, setOpen] = useState(false);
    const [data, setData] = useState<SystemDiagnostics | null>(null);
    const [loading, setLoading] = useState(false);
    const [backingUp, setBackingUp] = useState(false);
    const [error, setError] = useState<string | null>(null);

    async function refresh() {
        setLoading(true);
        setError(null);
        try {
            setData(await getSystemDiagnostics());
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Diagnostics failed.");
        } finally {
            setLoading(false);
        }
    }

    async function backup() {
        setBackingUp(true);
        setError(null);
        try {
            await downloadSystemBackup();
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Backup failed.");
        } finally {
            setBackingUp(false);
        }
    }

    return (
        <Dialog
            open={open}
            onOpenChange={(nextOpen) => {
                setOpen(nextOpen);
                if (nextOpen && !data) void refresh();
            }}
        >
            <DialogTrigger asChild>
                <Button type="button" variant="outline" size="sm" disabled={disabled}>
                    <HeartPulseIcon className="mr-2 size-4" />
                    System
                </Button>
            </DialogTrigger>
            <DialogContent className="max-w-3xl">
                <DialogTitle>System readiness</DialogTitle>
                <DialogDescription>
                    Check the local services AI Lab needs and download a safe backup of its settings and history.
                </DialogDescription>

                {error && (
                    <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">
                        {error}
                    </div>
                )}

                {loading && !data ? (
                    <div className="flex h-48 items-center justify-center text-sm text-zinc-500">
                        <Loader2Icon className="mr-2 size-4 animate-spin" /> Running checks…
                    </div>
                ) : data ? (
                    <>
                        <div className="grid grid-cols-3 gap-3 text-center">
                            <div className="rounded-lg border p-3"><div className="text-2xl font-semibold text-emerald-600">{data.summary.passed}</div><div className="text-xs text-zinc-500">Passed</div></div>
                            <div className="rounded-lg border p-3"><div className="text-2xl font-semibold text-amber-600">{data.summary.warnings}</div><div className="text-xs text-zinc-500">Warnings</div></div>
                            <div className="rounded-lg border p-3"><div className="text-2xl font-semibold text-red-600">{data.summary.failed}</div><div className="text-xs text-zinc-500">Failed</div></div>
                        </div>
                        <ScrollArea className="h-[390px] pr-4">
                            <div className="space-y-2">
                                {data.checks.map((check) => (
                                    <div key={check.id} className={`flex gap-3 rounded-lg border p-3 ${styles[check.status]}`}>
                                        <CheckIcon status={check.status} />
                                        <div className="min-w-0">
                                            <p className="text-sm font-medium">{check.name}</p>
                                            <p className="break-words text-xs text-zinc-600 dark:text-zinc-300">{check.message}</p>
                                            {check.action && <p className="mt-1 text-xs font-medium">Next: {check.action}</p>}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </ScrollArea>
                    </>
                ) : null}

                <div className="flex flex-wrap justify-between gap-2 border-t pt-4">
                    <p className="max-w-md text-xs text-zinc-500">
                        Backups contain AI Lab settings and SQLite state only. They never include workspace files, .env, or API keys.
                    </p>
                    <div className="flex gap-2">
                        <Button type="button" variant="outline" onClick={() => void refresh()} disabled={loading}>
                            {loading ? <Loader2Icon className="mr-2 size-4 animate-spin" /> : <RefreshCwIcon className="mr-2 size-4" />} Refresh
                        </Button>
                        <Button type="button" onClick={() => void backup()} disabled={backingUp}>
                            {backingUp ? <Loader2Icon className="mr-2 size-4 animate-spin" /> : <DownloadIcon className="mr-2 size-4" />} Backup
                        </Button>
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
}
