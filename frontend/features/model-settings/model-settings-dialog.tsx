"use client";

import {
    AlertTriangleIcon,
    CheckCircle2Icon,
    Loader2Icon,
    PlusIcon,
    ServerCogIcon,
    Trash2Icon,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

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
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import type { AgentProfile } from "@/features/agents/agent-api";
import {
    deleteProvider,
    discoverModels,
    type DiscoveredModel,
    getModelSettings,
    type ModelSettingsSnapshot,
    type ProviderKind,
    saveAgentModel,
    saveProvider,
    testProvider,
} from "@/features/model-settings/model-settings-api";

type Props = {
    agents: AgentProfile[];
    disabled?: boolean;
    onSaved: () => void | Promise<void>;
};

function readableBytes(value: number | null): string {
    if (!value) return "Size unavailable";
    return `${(value / 1024 ** 3).toFixed(1)} GB`;
}

export function ModelSettingsDialog({ agents, disabled, onSaved }: Props) {
    const [open, setOpen] = useState(false);
    const [snapshot, setSnapshot] = useState<ModelSettingsSnapshot | null>(null);
    const [selectedAgentId, setSelectedAgentId] = useState(agents[0]?.id ?? "general");
    const [models, setModels] = useState<DiscoveredModel[]>([]);
    const [loading, setLoading] = useState(false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);
    const [newProvider, setNewProvider] = useState(false);
    const [editingProviderId, setEditingProviderId] = useState<string | null>(null);
    const [providerId, setProviderId] = useState("");
    const [providerName, setProviderName] = useState("");
    const [providerKind, setProviderKind] = useState<ProviderKind>("openai_compatible");
    const [providerUrl, setProviderUrl] = useState("");
    const [providerKey, setProviderKey] = useState("");
    const [portalContainer, setPortalContainer] = useState<HTMLDivElement | null>(null);

    const agentSettings = snapshot?.agents[selectedAgentId];
    const selectedModel = models.find((item) => item.name === agentSettings?.model);
    const selectedAgentName = useMemo(
        () => agents.find((item) => item.id === selectedAgentId)?.name ?? selectedAgentId,
        [agents, selectedAgentId],
    );

    useEffect(() => {
        if (!open) return;
        void getModelSettings()
            .then((value) => {
                setSnapshot(value);
                const first = agents.find((agent) => value.agents[agent.id]);
                if (first) setSelectedAgentId(first.id);
            })
            .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Could not load settings"))
            .finally(() => setLoading(false));
    }, [open, agents]);

    useEffect(() => {
        if (!open || !agentSettings?.provider_id) return;
        void discoverModels(agentSettings.provider_id)
            .then((value) => setModels(value.models))
            .catch(() => setModels([]));
    }, [open, agentSettings?.provider_id]);

    async function refresh() {
        const value = await getModelSettings();
        setSnapshot(value);
        return value;
    }

    async function run(action: () => Promise<void>) {
        setBusy(true);
        setError(null);
        setNotice(null);
        try {
            await action();
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "The request failed");
        } finally {
            setBusy(false);
        }
    }

    async function updateAgent(patch: Partial<NonNullable<typeof agentSettings>>) {
        if (!agentSettings) return;
        const next = { ...agentSettings, ...patch };
        await run(async () => {
            await saveAgentModel(selectedAgentId, {
                provider_id: next.provider_id,
                model: next.model,
                generation: next.generation,
            });
            await refresh();
            await onSaved();
            setNotice(`${selectedAgentName} settings saved.`);
        });
    }

    async function addProvider() {
        await run(async () => {
            await saveProvider(providerId.trim(), {
                name: providerName.trim(),
                kind: providerKind,
                base_url: providerUrl.trim(),
                api_key: providerKey || null,
            });
            await refresh();
            setNewProvider(false);
            setEditingProviderId(null);
            setProviderId(""); setProviderName(""); setProviderUrl(""); setProviderKey("");
            setNotice("Provider saved. Test it before assigning an agent.");
        });
    }

    return (
        <Dialog
            open={open}
            onOpenChange={(nextOpen) => {
                setOpen(nextOpen);
                if (nextOpen) {
                    setLoading(true);
                    setError(null);
                    setNotice(null);
                }
            }}
        >
            <DialogTrigger asChild>
                <Button type="button" variant="outline" size="sm" disabled={disabled}>
                    <ServerCogIcon className="mr-2 size-4" />
                    Models
                </Button>
            </DialogTrigger>
            <DialogContent className="max-w-4xl">
                <DialogTitle>Models and providers</DialogTitle>
                <DialogDescription>
                    Configure the runtime used by each agent. API keys go to your operating-system credential store, never the settings JSON.
                </DialogDescription>
                {loading ? (
                    <div className="flex h-60 items-center justify-center text-sm text-zinc-500"><Loader2Icon className="mr-2 size-5 animate-spin" />Loading settings…</div>
                ) : snapshot ? (
                    <div ref={setPortalContainer}>
                    <ScrollArea className="max-h-[70vh] pr-4">
                        <div className="grid gap-6 py-3 lg:grid-cols-[280px_1fr]">
                            <section className="space-y-3">
                                <div className="flex items-center justify-between">
                                    <h3 className="text-sm font-semibold">Providers</h3>
                                    <Button size="sm" variant="outline" onClick={() => { setNewProvider(true); setEditingProviderId(null); setProviderId(""); setProviderName(""); setProviderKind("openai_compatible"); setProviderUrl(""); setProviderKey(""); }}><PlusIcon className="mr-1 size-3" />Add</Button>
                                </div>
                                {snapshot.providers.map((provider) => (
                                    <div key={provider.id} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
                                        <div className="flex items-start justify-between gap-2">
                                            <div><p className="text-sm font-medium">{provider.name}</p><p className="text-xs text-zinc-500">{provider.kind.replace("_", " ")}</p></div>
                                            {!provider.built_in ? <Button variant="ghost" size="icon" disabled={busy} onClick={() => void run(async () => { await deleteProvider(provider.id); await refresh(); })}><Trash2Icon className="size-4" /></Button> : null}
                                        </div>
                                        <p className="mt-2 break-all text-[11px] text-zinc-500">{provider.base_url}</p>
                                        <div className="mt-3 flex gap-2">
                                            <Button size="sm" variant="outline" disabled={busy} onClick={() => void run(async () => { const result = await testProvider(provider.id); setNotice(result.message); setModels(result.models); })}>Test</Button>
                                            <Button size="sm" variant="outline" disabled={busy} onClick={() => void run(async () => { const result = await discoverModels(provider.id); setModels(result.models); setNotice(`Found ${result.models.length} model(s).`); })}>Models</Button>
                                            <Button size="sm" variant="outline" disabled={busy} onClick={() => { setNewProvider(true); setEditingProviderId(provider.id); setProviderId(provider.id); setProviderName(provider.name); setProviderKind(provider.kind); setProviderUrl(provider.base_url); setProviderKey(""); }}>Edit</Button>
                                        </div>
                                    </div>
                                ))}
                                {newProvider ? (
                                    <div className="space-y-3 rounded-lg border border-violet-200 p-3 dark:border-violet-900">
                                        <div><Label htmlFor="provider-id">ID</Label><Input id="provider-id" disabled={editingProviderId !== null} placeholder="lm-studio" value={providerId} onChange={(event) => setProviderId(event.target.value.toLowerCase().replace(/[^a-z0-9-_]/g, ""))} /></div>
                                        <div><Label htmlFor="provider-name">Display name</Label><Input id="provider-name" placeholder="LM Studio" value={providerName} onChange={(event) => setProviderName(event.target.value)} /></div>
                                        <div><Label>Type</Label><Select value={providerKind} onValueChange={(value) => setProviderKind(value as ProviderKind)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent portalContainer={portalContainer}><SelectItem value="openai_compatible">OpenAI compatible</SelectItem><SelectItem value="ollama">Ollama</SelectItem></SelectContent></Select></div>
                                        <div><Label htmlFor="provider-url">Base URL</Label><Input id="provider-url" placeholder="http://localhost:1234/v1" value={providerUrl} onChange={(event) => setProviderUrl(event.target.value)} /></div>
                                        <div><Label htmlFor="provider-key">API key (optional)</Label><Input id="provider-key" type="password" autoComplete="off" placeholder={editingProviderId ? "Leave blank to keep existing key" : "Not required for most local servers"} value={providerKey} onChange={(event) => setProviderKey(event.target.value)} /></div>
                                        <div className="flex gap-2"><Button className="flex-1" disabled={busy || !providerId || !providerName || !providerUrl} onClick={() => void addProvider()}>Save provider</Button><Button variant="outline" onClick={() => { setNewProvider(false); setEditingProviderId(null); }}>Cancel</Button></div>
                                    </div>
                                ) : null}
                            </section>
                            <section className="space-y-4">
                                <div><Label>Agent</Label><Select value={selectedAgentId} onValueChange={setSelectedAgentId}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent portalContainer={portalContainer}>{agents.map((agent) => <SelectItem key={agent.id} value={agent.id}>{agent.name}</SelectItem>)}</SelectContent></Select></div>
                                {agentSettings ? <>
                                    <div><Label>Provider</Label><Select value={agentSettings.provider_id} disabled={busy} onValueChange={(provider_id) => void updateAgent({ provider_id })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent portalContainer={portalContainer}>{snapshot.providers.map((provider) => <SelectItem key={provider.id} value={provider.id}>{provider.name}</SelectItem>)}</SelectContent></Select></div>
                                    <div><Label>Model</Label><Select value={agentSettings.model} disabled={busy || models.length === 0} onValueChange={(model) => void updateAgent({ model })}><SelectTrigger><SelectValue placeholder={models.length ? "Select an installed model" : "No discovered models"} /></SelectTrigger><SelectContent portalContainer={portalContainer}>{models.map((model) => <SelectItem key={model.name} value={model.name}>{model.name} · {readableBytes(model.size)}</SelectItem>)}</SelectContent></Select><p className="mt-1 text-xs text-zinc-500">{models.length ? `${models.length} installed model(s) found. Selection saves immediately.` : "Test the provider or confirm Ollama is running."}</p></div>
                                    {selectedModel?.warnings.map((warning) => <div key={warning} className="flex gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200"><AlertTriangleIcon className="size-4 shrink-0" />{warning}</div>)}
                                    {selectedModel ? <p className="text-xs text-zinc-500">Installed size: {readableBytes(selectedModel.size)}</p> : null}
                                    <div className="grid gap-4 sm:grid-cols-3">
                                        <div><Label>Temperature</Label><Input type="number" min={0} max={2} step={0.05} value={agentSettings.generation.temperature} onChange={(event) => setSnapshot((current) => current ? { ...current, agents: { ...current.agents, [selectedAgentId]: { ...agentSettings, generation: { ...agentSettings.generation, temperature: Number(event.target.value) } } } } : current)} /></div>
                                        <div><Label>Max output</Label><Input type="number" min={128} max={32768} step={128} value={agentSettings.generation.max_tokens} onChange={(event) => setSnapshot((current) => current ? { ...current, agents: { ...current.agents, [selectedAgentId]: { ...agentSettings, generation: { ...agentSettings.generation, max_tokens: Number(event.target.value) } } } } : current)} /></div>
                                        <div><Label>Context budget</Label><Input type="number" min={1024} max={131072} step={1024} value={agentSettings.generation.context_window} onChange={(event) => setSnapshot((current) => current ? { ...current, agents: { ...current.agents, [selectedAgentId]: { ...agentSettings, generation: { ...agentSettings.generation, context_window: Number(event.target.value) } } } } : current)} /></div>
                                    </div>
                                    <Button disabled={busy} onClick={() => void updateAgent({ generation: agentSettings.generation })}>{busy ? <Loader2Icon className="mr-2 size-4 animate-spin" /> : null}Save generation settings</Button>
                                </> : null}
                            </section>
                        </div>
                    </ScrollArea>
                    </div>
                ) : null}
                {error ? <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">{error}</div> : null}
                {notice ? <div className="flex gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-300"><CheckCircle2Icon className="size-4" />{notice}</div> : null}
            </DialogContent>
        </Dialog>
    );
}
