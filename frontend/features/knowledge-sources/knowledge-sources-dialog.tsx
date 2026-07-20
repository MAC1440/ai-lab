"use client";

import { DatabaseIcon, Loader2Icon, PlusIcon, Trash2Icon } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getKnowledgeStatus, removeKnowledgeSource, streamKnowledgeIndex, type KnowledgeIndexEvent, type KnowledgeStatus } from "./knowledge-sources-api";

export function KnowledgeSourcesDialog({ disabled = false }: { disabled?: boolean }) {
    const [open, setOpen] = useState(false);
    const [status, setStatus] = useState<KnowledgeStatus | null>(null);
    const [sourceId, setSourceId] = useState("");
    const [name, setName] = useState("");
    const [directory, setDirectory] = useState("");
    const [progress, setProgress] = useState<KnowledgeIndexEvent | null>(null);
    const [working, setWorking] = useState(false);
    const [error, setError] = useState<string | null>(null);

    async function refresh() {
        try { setStatus(await getKnowledgeStatus()); }
        catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load knowledge sources."); }
    }

    async function index() {
        if (!sourceId.trim() || !name.trim() || !directory.trim()) return;
        setWorking(true); setError(null); setProgress(null);
        try {
            for await (const event of streamKnowledgeIndex({ sourceId, name, sourceDirectory: directory })) {
                setProgress(event);
                if (event.type === "error") throw new Error(event.message);
            }
            await refresh();
        } catch (reason) { setError(reason instanceof Error ? reason.message : "Indexing failed."); }
        finally { setWorking(false); }
    }

    const percentage = progress?.type === "progress" && progress.total > 0
        ? Math.round(progress.completed / progress.total * 100) : null;

    return <Dialog open={open} onOpenChange={(next) => { setOpen(next); if (next) void refresh(); }}>
        <DialogTrigger asChild><Button type="button" variant="outline" size="sm" disabled={disabled}><DatabaseIcon className="mr-2 size-4" />Knowledge</Button></DialogTrigger>
        <DialogContent className="max-w-3xl">
            <DialogTitle>Knowledge sources</DialogTitle>
            <DialogDescription>Add documentation or source-code folders without replacing the existing Unity index. Reusing an ID updates only that source.</DialogDescription>
            <div className="rounded-xl border p-3 text-sm"><b>{status?.total_chunk_count.toLocaleString() ?? "…"} total chunks</b><span className="ml-2 text-zinc-500">{status?.embedding_model}</span><p className="mt-1 text-xs text-zinc-500">Your existing Unity chunks are included in this total even though they predate the source catalog.</p></div>
            <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-2"><Label htmlFor="knowledge-name">Display name</Label><Input id="knowledge-name" value={name} onChange={(event) => { setName(event.target.value); if (!sourceId) setSourceId(event.target.value.toLowerCase().replace(/[^a-z0-9]+/g, "-")); }} placeholder="React reference project" /></div>
                <div className="space-y-2"><Label htmlFor="knowledge-id">Stable source ID</Label><Input id="knowledge-id" value={sourceId} onChange={(event) => setSourceId(event.target.value)} placeholder="react-reference" /></div>
                <div className="space-y-2 sm:col-span-2"><Label htmlFor="knowledge-directory">Local folder</Label><Input id="knowledge-directory" value={directory} onChange={(event) => setDirectory(event.target.value)} placeholder="D:\Projects\reference-repo" /></div>
            </div>
            {progress ? <div className="rounded-lg border p-3 text-sm">{progress.type === "status" ? progress.message : progress.type === "progress" ? <><div className="flex justify-between"><span className="capitalize">{progress.stage}</span><span>{progress.completed}/{progress.total} ({percentage}%)</span></div><div className="mt-2 h-2 rounded bg-zinc-200"><div className="h-full rounded bg-violet-600" style={{ width: `${percentage}%` }} /></div></> : progress.type === "done" ? `Indexed ${progress.result.document_count} files into ${progress.result.chunk_count} chunks.` : progress.message}</div> : null}
            {error ? <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
            <div className="max-h-52 space-y-2 overflow-y-auto">{status?.sources.map((source) => <div key={source.id} className="flex items-center justify-between gap-3 rounded-lg border p-3"><div className="min-w-0"><p className="font-medium">{source.name}</p><p className="truncate text-xs text-zinc-500">{source.id} · {source.document_count} files · {source.chunk_count} chunks</p></div><Button type="button" size="icon" variant="ghost" disabled={working} aria-label={`Remove ${source.name}`} onClick={async () => { if (!confirm(`Remove indexed chunks for ${source.name}? Source files are not deleted.`)) return; setWorking(true); try { await removeKnowledgeSource(source.id); await refresh(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Remove failed."); } finally { setWorking(false); } }}><Trash2Icon className="size-4" /></Button></div>)}</div>
            <div className="flex justify-end"><Button type="button" onClick={() => void index()} disabled={working || !sourceId.trim() || !name.trim() || !directory.trim()}>{working ? <Loader2Icon className="mr-2 size-4 animate-spin" /> : <PlusIcon className="mr-2 size-4" />}Add or update source</Button></div>
        </DialogContent>
    </Dialog>;
}
