"use client";

import { Settings2Icon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { type AgentChatSettings, defaultAgentSettings } from "./agent-chat-state";

export function AgentRuntimeDialog({
    open,
    onOpenChange,
    settings,
    onSettingsChange,
}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    settings: AgentChatSettings;
    onSettingsChange: (settings: AgentChatSettings) => void;
}) {
    return <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogTrigger asChild><Button type="button" variant="outline" size="sm"><Settings2Icon className="mr-2 size-4" />Runtime</Button></DialogTrigger>
        <DialogContent className="max-w-lg">
            <DialogTitle>Agent runtime controls</DialogTitle>
            <DialogDescription>Overrides apply to subsequent messages. Profile default preserves the selected agent&apos;s normal behavior.</DialogDescription>
            <div className="grid gap-4 py-2 sm:grid-cols-2">
                <div className="space-y-2">
                    <Label>RAG</Label>
                    <Select value={settings.ragMode} onValueChange={(value) => onSettingsChange({ ...settings, ragMode: value as AgentChatSettings["ragMode"] })}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent><SelectItem value="default">Profile default</SelectItem><SelectItem value="enabled">Force enabled</SelectItem><SelectItem value="disabled">Force disabled</SelectItem></SelectContent>
                    </Select>
                </div>
                <div className="space-y-2">
                    <Label>Workspace tools</Label>
                    <Select value={settings.toolsMode} onValueChange={(value) => onSettingsChange({ ...settings, toolsMode: value as AgentChatSettings["toolsMode"] })}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent><SelectItem value="default">Profile default</SelectItem><SelectItem value="enabled">Force enabled</SelectItem><SelectItem value="disabled">Force disabled</SelectItem></SelectContent>
                    </Select>
                    <p className="text-xs text-zinc-500">Cannot grant tools outside the profile allow-list.</p>
                </div>
                <div className="space-y-2">
                    <Label htmlFor="rag-top-k">Retrieved chunks</Label>
                    <Input id="rag-top-k" type="number" min={1} max={10} value={settings.ragTopK} onChange={(event) => onSettingsChange({ ...settings, ragTopK: Math.min(10, Math.max(1, Math.trunc(Number(event.target.value) || 3))) })} />
                </div>
                <div className="space-y-2">
                    <Label htmlFor="rag-threshold">Distance threshold</Label>
                    <Input id="rag-threshold" type="number" min={0} step={0.05} placeholder="Empty disables filtering" value={settings.ragDistanceThreshold} onChange={(event) => onSettingsChange({ ...settings, ragDistanceThreshold: event.target.value === "" ? "" : Math.max(0, Number(event.target.value)) })} />
                </div>
            </div>
            <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => onSettingsChange(defaultAgentSettings)}>Reset</Button><Button type="button" onClick={() => onOpenChange(false)}>Done</Button></div>
        </DialogContent>
    </Dialog>;
}
