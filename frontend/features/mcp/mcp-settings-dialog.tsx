"use client";

import {
    AlertTriangleIcon,
    CheckCircle2Icon,
    Loader2Icon,
    NetworkIcon,
    PlusIcon,
    Trash2Icon,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import { Switch } from "@/components/ui/switch";
import type { AgentProfile } from "@/features/agents/agent-api";
import {
    deleteMCPServer,
    discoverMCPTools,
    listMCPServers,
    type MCPServer,
    type MCPTool,
    saveMCPServer,
    testMCPServer,
} from "@/features/mcp/mcp-api";

type Props = { agents: AgentProfile[]; disabled?: boolean };

const emptyServer: MCPServer = {
    id: "",
    name: "",
    url: "http://127.0.0.1:8001/mcp",
    enabled: false,
    tool_prefix: "",
    allowed_tools: [],
    agent_ids: [],
};

export function MCPSettingsDialog({ agents, disabled }: Props) {
    const [open, setOpen] = useState(false);
    const [servers, setServers] = useState<MCPServer[]>([]);
    const [draft, setDraft] = useState<MCPServer | null>(null);
    const [tools, setTools] = useState<MCPTool[]>([]);
    const [loading, setLoading] = useState(false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);

    const isNew = useMemo(
        () => draft !== null && !servers.some((item) => item.id === draft.id),
        [draft, servers],
    );

    useEffect(() => {
        if (!open) return;
        void listMCPServers()
            .then(setServers)
            .catch((reason: unknown) =>
                setError(reason instanceof Error ? reason.message : "Could not load MCP settings"),
            )
            .finally(() => setLoading(false));
    }, [open]);

    async function refresh() {
        const result = await listMCPServers();
        setServers(result);
        return result;
    }

    async function run(action: () => Promise<void>) {
        setBusy(true); setError(null); setNotice(null);
        try { await action(); }
        catch (reason) { setError(reason instanceof Error ? reason.message : "The MCP request failed"); }
        finally { setBusy(false); }
    }

    async function saveDraft(message = "MCP server saved.") {
        if (!draft) return;
        await run(async () => {
            const saved = await saveMCPServer(draft);
            await refresh();
            setDraft(saved);
            setNotice(message);
        });
    }

    function editServer(server: MCPServer) {
        setDraft({ ...server }); setTools([]); setError(null); setNotice(null);
        void run(async () => {
            const result = await discoverMCPTools(server.id);
            setTools(result.tools);
        });
    }

    function toggleAgent(agentId: string, checked: boolean) {
        if (!draft) return;
        setDraft({
            ...draft,
            agent_ids: checked
                ? [...new Set([...draft.agent_ids, agentId])]
                : draft.agent_ids.filter((item) => item !== agentId),
        });
    }

    function toggleTool(name: string, checked: boolean) {
        if (!draft) return;
        setDraft({
            ...draft,
            allowed_tools: checked
                ? [...new Set([...draft.allowed_tools, name])]
                : draft.allowed_tools.filter((item) => item !== name),
        });
    }

    return (
        <Dialog open={open} onOpenChange={(value) => { setOpen(value); if (value) { setLoading(true); setError(null); setNotice(null); } }}>
            <DialogTrigger asChild><Button type="button" variant="outline" size="sm" disabled={disabled}><NetworkIcon className="mr-2 size-4" />MCP</Button></DialogTrigger>
            <DialogContent className="max-w-5xl">
                <DialogTitle>MCP connections</DialogTitle>
                <DialogDescription>
                    Connect only trusted Streamable HTTP servers. Servers start disabled, expose no tools by default, and are never used during enforced repairs.
                </DialogDescription>
                {loading ? <div className="flex h-60 items-center justify-center text-sm text-zinc-500"><Loader2Icon className="mr-2 size-5 animate-spin" />Loading MCP settings…</div> : (
                    <ScrollArea className="max-h-[72vh] pr-4">
                        <div className="grid gap-6 py-3 lg:grid-cols-[300px_1fr]">
                            <section className="space-y-3">
                                <div className="flex items-center justify-between"><h3 className="text-sm font-semibold">Allowlisted servers</h3><Button size="sm" variant="outline" onClick={() => { setDraft({ ...emptyServer }); setTools([]); }}><PlusIcon className="mr-1 size-3" />Add</Button></div>
                                {servers.length === 0 ? <p className="rounded-lg border border-dashed p-4 text-xs text-zinc-500">No MCP servers configured. AI Lab continues normally without MCP.</p> : null}
                                {servers.map((server) => <button key={server.id} type="button" onClick={() => editServer(server)} className="w-full rounded-lg border border-zinc-200 p-3 text-left hover:border-violet-400 dark:border-zinc-800">
                                    <div className="flex items-center justify-between gap-2"><span className="text-sm font-medium">{server.name}</span><span className={`rounded-full px-2 py-0.5 text-[10px] ${server.enabled ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950" : "bg-zinc-100 text-zinc-500 dark:bg-zinc-900"}`}>{server.enabled ? "Enabled" : "Disabled"}</span></div>
                                    <p className="mt-1 truncate text-[11px] text-zinc-500">{server.url}</p><p className="mt-2 text-[11px] text-zinc-500">{server.allowed_tools.length} tool(s) · {server.agent_ids.length} agent(s)</p>
                                </button>)}
                            </section>
                            <section>
                                {draft ? <div className="space-y-5">
                                    <div className="flex items-center justify-between gap-4"><div><h3 className="text-sm font-semibold">{isNew ? "New MCP server" : draft.name}</h3><p className="text-xs text-zinc-500">Only explicitly checked tools reach the model.</p></div><div className="flex items-center gap-2"><Label htmlFor="mcp-enabled">Enabled</Label><Switch id="mcp-enabled" checked={draft.enabled} onCheckedChange={(enabled) => setDraft({ ...draft, enabled })} /></div></div>
                                    <div className="grid gap-4 sm:grid-cols-2">
                                        <div><Label htmlFor="mcp-id">Server ID</Label><Input id="mcp-id" disabled={!isNew && draft.id !== ""} value={draft.id} placeholder="docs-server" onChange={(event) => setDraft({ ...draft, id: event.target.value.toLowerCase().replace(/[^a-z0-9-_]/g, "") })} /></div>
                                        <div><Label htmlFor="mcp-name">Display name</Label><Input id="mcp-name" value={draft.name} placeholder="Documentation tools" onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></div>
                                        <div className="sm:col-span-2"><Label htmlFor="mcp-url">Streamable HTTP URL</Label><Input id="mcp-url" value={draft.url} onChange={(event) => setDraft({ ...draft, url: event.target.value })} /><p className="mt-1 text-xs text-zinc-500">Local HTTP is allowed. Remote servers must use HTTPS. Stdio commands are intentionally excluded.</p></div>
                                        <div><Label htmlFor="mcp-prefix">Tool prefix</Label><Input id="mcp-prefix" value={draft.tool_prefix} placeholder={draft.id || "docs"} onChange={(event) => setDraft({ ...draft, tool_prefix: event.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "") })} /></div>
                                    </div>
                                    <div className="flex flex-wrap gap-2"><Button disabled={busy || !draft.id || !draft.name || !draft.url} onClick={() => void saveDraft()}>{busy ? <Loader2Icon className="mr-2 size-4 animate-spin" /> : null}Save</Button>{!isNew ? <><Button variant="outline" disabled={busy} onClick={() => void run(async () => { const result = await testMCPServer(draft.id); setTools(result.tools); setNotice(result.message); })}>Test and discover</Button><Button variant="outline" className="text-red-600" disabled={busy} onClick={() => void run(async () => { await deleteMCPServer(draft.id); await refresh(); setDraft(null); setTools([]); })}><Trash2Icon className="mr-2 size-4" />Delete</Button></> : null}</div>
                                    <div className="space-y-2"><h4 className="text-sm font-medium">Agents</h4><div className="grid gap-2 sm:grid-cols-2">{agents.map((agent) => <label key={agent.id} className="flex items-center gap-2 rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-800"><Checkbox checked={draft.agent_ids.includes(agent.id)} onCheckedChange={(value) => toggleAgent(agent.id, value === true)} />{agent.name}</label>)}</div></div>
                                    <div className="space-y-2"><div className="flex items-center justify-between"><h4 className="text-sm font-medium">Allowed tools</h4><span className="text-xs text-zinc-500">{draft.allowed_tools.length} selected</span></div>{tools.length === 0 ? <div className="rounded-lg border border-dashed p-4 text-xs text-zinc-500">Save the server, then use Test and discover. No MCP tools are allowed until you explicitly select and save them.</div> : <div className="space-y-2">{tools.map((tool) => <label key={tool.name} className={`flex items-start gap-3 rounded-lg border p-3 ${tool.safe_to_enable ? "border-zinc-200 dark:border-zinc-800" : "border-amber-200 bg-amber-50/50 opacity-75 dark:border-amber-900 dark:bg-amber-950/20"}`}><Checkbox className="mt-0.5" disabled={!tool.safe_to_enable} checked={tool.safe_to_enable && draft.allowed_tools.includes(tool.name)} onCheckedChange={(value) => toggleTool(tool.name, value === true)} /><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><span className="text-sm font-medium">{tool.name}</span>{tool.safe_to_enable ? <span className="text-[10px] text-emerald-600">read-only allowed</span> : <span className="flex items-center gap-1 text-[10px] text-amber-600"><AlertTriangleIcon className="size-3" />blocked</span>}</div><p className="mt-1 text-xs text-zinc-500">{tool.description || "No description supplied by server."}</p><p className="mt-1 text-[10px] text-zinc-500">{tool.safety_reason}</p></div></label>)}</div>}<Button variant="outline" disabled={busy || isNew} onClick={() => void saveDraft("MCP permissions saved. They apply on the next message.")}>Save permissions</Button></div>
                                    <div className="flex gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200"><AlertTriangleIcon className="size-4 shrink-0" />MCP annotations are supplied by the server and are not a security boundary. Only enable servers and tools you trust. Workspace file changes must still use AI Lab proposals.</div>
                                </div> : <div className="flex h-64 items-center justify-center text-sm text-zinc-500">Select a server or add a new one.</div>}
                            </section>
                        </div>
                    </ScrollArea>
                )}
                {error ? <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">{error}</div> : null}
                {notice ? <div className="flex gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-300"><CheckCircle2Icon className="size-4" />{notice}</div> : null}
            </DialogContent>
        </Dialog>
    );
}
