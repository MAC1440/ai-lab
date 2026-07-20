"use client";

import {
    BookOpenCheckIcon,
    EyeIcon,
    Loader2Icon,
    RefreshCwIcon,
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
    getUnityKnowledgeStatus,
    previewUnityDocument,
    streamUnityIndex,
    type UnityIndexEvent,
    type UnityKnowledgeStatus,
    type UnityPreview,
} from "./unity-knowledge-api";

export function UnityKnowledgeDialog({ disabled = false }: { disabled?: boolean }) {
    const [open, setOpen] = useState(false);
    const [sourceDirectory, setSourceDirectory] = useState("");
    const [relativeFile, setRelativeFile] = useState("");
    const [status, setStatus] = useState<UnityKnowledgeStatus | null>(null);
    const [preview, setPreview] = useState<UnityPreview | null>(null);
    const [progress, setProgress] = useState<UnityIndexEvent | null>(null);
    const [working, setWorking] = useState(false);
    const [error, setError] = useState<string | null>(null);

    async function refreshStatus() {
        try {
            setStatus(await getUnityKnowledgeStatus());
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Status failed.");
        }
    }

    async function runPreview() {
        if (!sourceDirectory.trim() || !relativeFile.trim()) return;
        setWorking(true);
        setError(null);
        try {
            setPreview(await previewUnityDocument(sourceDirectory, relativeFile));
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Preview failed.");
        } finally {
            setWorking(false);
        }
    }

    async function runIndex() {
        if (!sourceDirectory.trim()) return;
        setWorking(true);
        setError(null);
        setProgress(null);
        try {
            for await (const event of streamUnityIndex(sourceDirectory)) {
                setProgress(event);
                if (event.type === "error") throw new Error(event.message);
            }
            await refreshStatus();
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Indexing failed.");
        } finally {
            setWorking(false);
        }
    }

    const percentage = progress?.type === "progress" && progress.total > 0
        ? Math.round((progress.completed / progress.total) * 100)
        : null;

    return (
        <Dialog
            open={open}
            onOpenChange={(next) => {
                setOpen(next);
                if (next && !status) void refreshStatus();
            }}
        >
            <DialogTrigger asChild>
                <Button type="button" variant="outline" size="sm" disabled={disabled}>
                    <BookOpenCheckIcon className="mr-2 size-4" />
                    Unity docs
                </Button>
            </DialogTrigger>
            <DialogContent className="max-w-4xl">
                <DialogTitle>Unity documentation knowledge</DialogTitle>
                <DialogDescription>
                    Clean scraped Unity Markdown, preview semantic chunks, and rebuild the Unity agent&apos;s local RAG index.
                </DialogDescription>

                <div className="grid gap-4 md:grid-cols-[1fr_220px]">
                    <div className="space-y-2">
                        <Label htmlFor="unity-source">Scraped Markdown folder</Label>
                        <Input
                            id="unity-source"
                            value={sourceDirectory}
                            onChange={(event) => setSourceDirectory(event.target.value)}
                            placeholder="D:\UnityDocs\6000.1"
                            disabled={working}
                        />
                    </div>
                    <div className="rounded-lg border p-3 text-sm">
                        <p className="font-medium">Current index</p>
                        <p className="mt-1 text-zinc-500">
                            {status ? `${status.chunk_count.toLocaleString()} chunks` : "Loading…"}
                        </p>
                        <p className="truncate text-xs text-zinc-500" title={status?.embedding_model}>
                            {status?.embedding_model ?? ""}
                        </p>
                    </div>
                </div>

                <div className="grid gap-2 md:grid-cols-[1fr_auto]">
                    <div className="space-y-2">
                        <Label htmlFor="unity-preview">Preview file (relative path)</Label>
                        <Input
                            id="unity-preview"
                            value={relativeFile}
                            onChange={(event) => setRelativeFile(event.target.value)}
                            placeholder="ScriptReference\AccelerationEvent.md"
                            disabled={working}
                        />
                    </div>
                    <Button
                        type="button"
                        variant="outline"
                        className="self-end"
                        onClick={() => void runPreview()}
                        disabled={working || !sourceDirectory.trim() || !relativeFile.trim()}
                    >
                        <EyeIcon className="mr-2 size-4" /> Preview
                    </Button>
                </div>

                {error && (
                    <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">
                        {error}
                    </div>
                )}

                {progress && (
                    <div className="rounded-lg border p-3 text-sm">
                        {progress.type === "status" && <p>{progress.message}</p>}
                        {progress.type === "progress" && (
                            <>
                                <div className="flex justify-between">
                                    <span className="capitalize">{progress.stage}</span>
                                    <span>{progress.completed}/{progress.total} {percentage}%</span>
                                </div>
                                <div className="mt-2 h-2 overflow-hidden rounded bg-zinc-200 dark:bg-zinc-800">
                                    <div className="h-full bg-violet-600 transition-all" style={{ width: `${percentage}%` }} />
                                </div>
                            </>
                        )}
                        {progress.type === "done" && (
                            <p>Indexed {progress.result.document_count} documents into {progress.result.chunk_count} chunks. Skipped {progress.result.skipped_count}.</p>
                        )}
                    </div>
                )}

                {preview && (
                    <div className="space-y-2">
                        <div className="flex flex-wrap gap-3 text-xs text-zinc-500">
                            <span>{preview.chunk_count} chunks</span>
                            <span>{preview.original_characters.toLocaleString()} original characters</span>
                            <span>{preview.cleaned_characters.toLocaleString()} retained</span>
                        </div>
                        <ScrollArea className="h-[280px] rounded-lg border bg-zinc-50 p-4 dark:bg-zinc-950">
                            <pre className="whitespace-pre-wrap break-words text-xs leading-relaxed">
                                {preview.chunks.map((chunk, index) => `--- CHUNK ${index + 1} ---\n${chunk.text}`).join("\n\n")}
                            </pre>
                        </ScrollArea>
                    </div>
                )}

                <div className="flex justify-end gap-2 border-t pt-4">
                    <Button type="button" variant="outline" onClick={() => void refreshStatus()} disabled={working}>
                        <RefreshCwIcon className="mr-2 size-4" /> Refresh
                    </Button>
                    <Button type="button" onClick={() => void runIndex()} disabled={working || !sourceDirectory.trim()}>
                        {working ? <Loader2Icon className="mr-2 size-4 animate-spin" /> : <BookOpenCheckIcon className="mr-2 size-4" />}
                        Rebuild Unity index
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
}
