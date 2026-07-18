"use client";

import { BlocksIcon, Loader2Icon } from "lucide-react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  createScaffold,
  listScaffolds,
  type ScaffoldDefinition,
} from "@/features/scaffolds/scaffold-api";

export function ScaffoldDialog({ disabled = false }: { disabled?: boolean }) {
  const [open, setOpen] = useState(false);
  const [scaffolds, setScaffolds] = useState<ScaffoldDefinition[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [targetDirectory, setTargetDirectory] = useState("");
  const [projectName, setProjectName] = useState("MyProject");
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const selected = useMemo(
    () => scaffolds.find((item) => item.scaffold_id === selectedId) ?? null,
    [scaffolds, selectedId],
  );

  useEffect(() => {
    if (!open) return;
    void listScaffolds()
      .then((items) => {
        setScaffolds(items);
        const first = items.find((item) => item.available) ?? items[0];
        if (first) {
          setSelectedId(first.scaffold_id);
          setTargetDirectory(first.default_directory);
        }
        setError(null);
      })
      .catch((requestError: unknown) => {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Scaffolds could not be loaded.",
        );
      })
      .finally(() => setLoading(false));
  }, [open]);

  function handleOpenChange(nextOpen: boolean) {
    if (nextOpen) {
      setLoading(true);
      setError(null);
      setSuccess(null);
    }
    setOpen(nextOpen);
  }

  function selectScaffold(scaffoldId: string) {
    setSelectedId(scaffoldId);
    const definition = scaffolds.find((item) => item.scaffold_id === scaffoldId);
    if (definition) setTargetDirectory(definition.default_directory);
    setError(null);
    setSuccess(null);
  }

  async function handleCreate() {
    if (!selected) return;
    setCreating(true);
    setError(null);
    setSuccess(null);
    try {
      const result = await createScaffold({
        scaffoldId: selected.scaffold_id,
        targetDirectory,
        projectName,
      });
      setSuccess(
        `${result.proposal_count} files are ready in the approval queue. Nothing has been written yet.`,
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The scaffold could not be prepared.",
      );
    } finally {
      setCreating(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" size="sm" disabled={disabled}>
          <BlocksIcon className="size-4" />
          Scaffold
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl">
        <DialogTitle>Safe project scaffolding</DialogTitle>
        <DialogDescription>
          Generate into temporary staging, then review every file through the existing approval queue.
        </DialogDescription>

        {loading ? (
          <div className="flex items-center gap-2 py-8 text-sm text-zinc-500">
            <Loader2Icon className="size-4 animate-spin" /> Loading scaffolds…
          </div>
        ) : (
          <div className="space-y-5">
            <div className="space-y-2">
              <Label>Starter</Label>
              <Select value={selectedId} onValueChange={selectScaffold}>
                <SelectTrigger><SelectValue placeholder="Choose a scaffold" /></SelectTrigger>
                <SelectContent>
                  {scaffolds.map((item) => (
                    <SelectItem key={item.scaffold_id} value={item.scaffold_id} disabled={!item.available}>
                      {item.name}{item.available ? "" : " (unavailable)"}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selected ? (
                <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3 text-xs text-zinc-400">
                  <p className="text-zinc-200">{selected.description}</p>
                  <p className="mt-1">Source: {selected.source}</p>
                  {selected.requires_network ? <p className="mt-1 text-amber-400">Requires internet during staging.</p> : null}
                  {selected.unavailable_reason ? <p className="mt-1 text-red-400">{selected.unavailable_reason}</p> : null}
                </div>
              ) : null}
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="scaffold-project-name">Project/feature name</Label>
                <Input id="scaffold-project-name" value={projectName} onChange={(event) => setProjectName(event.target.value)} placeholder="MyProject" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="scaffold-target">Workspace subdirectory</Label>
                <Input id="scaffold-target" value={targetDirectory} onChange={(event) => setTargetDirectory(event.target.value)} placeholder="apps/my-project" />
              </div>
            </div>

            <p className="text-xs text-zinc-500">
              The target must be missing or empty. Generated dependencies are not installed automatically.
            </p>
            {error ? <p className="rounded-lg border border-red-900 bg-red-950/40 p-3 text-sm text-red-300">{error}</p> : null}
            {success ? <p className="rounded-lg border border-emerald-900 bg-emerald-950/40 p-3 text-sm text-emerald-300">{success}</p> : null}

            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>Close</Button>
              <Button type="button" disabled={creating || !selected?.available || !targetDirectory.trim() || !projectName.trim()} onClick={() => void handleCreate()}>
                {creating ? <Loader2Icon className="size-4 animate-spin" /> : <BlocksIcon className="size-4" />}
                Prepare proposals
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
