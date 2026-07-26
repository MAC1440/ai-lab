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
    pass: "border-success/30 bg-success/10 dark:border-success/30 dark:bg-success/10",
    warning: "border-pending/30 bg-pending/10 dark:border-pending/30 dark:bg-pending/10",
    fail: "border-danger/30 bg-danger/10 dark:border-danger/30 dark:bg-danger/10",
};

function CheckIcon({ status }: { status: SystemCheck["status"] }) {
    if (status === "pass") return <CheckCircle2Icon className="size-5 shrink-0 text-success" />;
    if (status === "warning") return <AlertTriangleIcon className="size-5 shrink-0 text-pending" />;
    return <XCircleIcon className="size-5 shrink-0 text-danger" />;
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
                    <div className="rounded-md border border-danger/30 bg-danger/10 p-3 text-sm text-danger dark:border-danger/30 dark:bg-danger/10 dark:text-danger">
                        {error}
                    </div>
                )}

                {loading && !data ? (
                    <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">
                        <Loader2Icon className="mr-2 size-4 animate-spin" /> Running checks…
                    </div>
                ) : data ? (
                    <>
                        <div className="grid grid-cols-3 gap-3 text-center">
                            <div className="rounded-lg border p-3"><div className="text-2xl font-semibold text-success">{data.summary.passed}</div><div className="text-xs text-muted-foreground">Passed</div></div>
                            <div className="rounded-lg border p-3"><div className="text-2xl font-semibold text-pending">{data.summary.warnings}</div><div className="text-xs text-muted-foreground">Warnings</div></div>
                            <div className="rounded-lg border p-3"><div className="text-2xl font-semibold text-danger">{data.summary.failed}</div><div className="text-xs text-muted-foreground">Failed</div></div>
                        </div>
                        <ScrollArea className="h-[390px] pr-4">
                            <div className="space-y-2">
                                {data.checks.map((check) => (
                                    <div key={check.id} className={`flex gap-3 rounded-lg border p-3 ${styles[check.status]}`}>
                                        <CheckIcon status={check.status} />
                                        <div className="min-w-0">
                                            <p className="text-sm font-medium">{check.name}</p>
                                            <p className="break-words text-xs text-muted-foreground dark:text-muted-foreground">{check.message}</p>
                                            {check.action && <p className="mt-1 text-xs font-medium">Next: {check.action}</p>}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </ScrollArea>
                    </>
                ) : null}

                <div className="flex flex-wrap justify-between gap-2 border-t pt-4">
                    <p className="max-w-md text-xs text-muted-foreground">
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
