"use client";

import {
  ChevronLeftIcon,
  DatabaseIcon,
  FileIcon,
  FolderIcon,
  HardDriveIcon,
  Loader2Icon,
  PlusIcon,
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
import {
  browseKnowledgeFiles,
  getKnowledgeStatus,
  previewKnowledgeSelection,
  removeKnowledgeSource,
  streamKnowledgeIndex,
  getKnowledgeBrowseRoots,
  type BrowseResult,
  type KnowledgeIndexEvent,
  type KnowledgeStatus,
  type SelectionPreview,
  type KnowledgeBrowseRoot,
} from "./knowledge-sources-api";

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

async function loadKnowledgeOverview(path?: string) {
  const [status, browser, roots] = await Promise.all([
    getKnowledgeStatus(),
    browseKnowledgeFiles(path),
    getKnowledgeBrowseRoots(),
  ]);

  return { status, browser, roots: roots.roots };
}

export function KnowledgeSourcesDialog({
  disabled = false,
}: {
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<KnowledgeStatus | null>(null);
  const [browser, setBrowser] = useState<BrowseResult | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [preview, setPreview] = useState<SelectionPreview | null>(null);
  const [sourceId, setSourceId] = useState("");
  const [name, setName] = useState("");
  const [progress, setProgress] = useState<KnowledgeIndexEvent | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [roots, setRoots] = useState<KnowledgeBrowseRoot[]>([]);

  useEffect(() => {
    if (!open) return;

    let cancelled = false;
    const timer = window.setTimeout(() => {
      setWorking(true);
      loadKnowledgeOverview()
        .then((result) => {
          if (cancelled) return;
          setStatus(result.status);
          setBrowser(result.browser);
          setRoots(result.roots);
        })
        .catch((reason) => {
          if (!cancelled) {
            setError(
              reason instanceof Error
                ? reason.message
                : "Could not load knowledge sources.",
            );
          }
        })
        .finally(() => {
          if (!cancelled) setWorking(false);
        });
    }, 0);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [open]);

  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(() => {
      if (!selected.length) {
        setPreview(null);
        return;
      }

      previewKnowledgeSelection(selected)
        .then((result) => {
          if (!cancelled) setPreview(result);
        })
        .catch((reason) => {
          if (!cancelled) {
            setError(
              reason instanceof Error ? reason.message : "Preview failed.",
            );
          }
        });
    }, selected.length ? 250 : 0);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [selected]);

  async function navigate(path: string) {
    setWorking(true);
    try {
      setBrowser(await browseKnowledgeFiles(path));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Browse failed.");
    } finally {
      setWorking(false);
    }
  }

  function toggle(path: string) {
    setSelected((current) =>
      current.includes(path)
        ? current.filter((item) => item !== path)
        : [...current, path],
    );
  }

  async function index() {
    if (!sourceId.trim() || !name.trim() || !selected.length) return;
    setWorking(true);
    setError(null);
    setProgress(null);
    try {
      for await (const event of streamKnowledgeIndex({
        sourceId,
        name,
        selections: selected,
      })) {
        setProgress(event);
        if (event.type === "error") throw new Error(event.message);
      }
      setStatus(await getKnowledgeStatus());
      setSelected([]);
      setPreview(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Indexing failed.");
    } finally {
      setWorking(false);
    }
  }

  const percentage =
    progress?.type === "progress" && progress.total > 0
      ? Math.round((progress.completed / progress.total) * 100)
      : null;

  const extensionSummary = useMemo(
    () =>
      preview
        ? Object.entries(preview.extensions)
          .sort((a, b) => b[1] - a[1])
          .slice(0, 8)
        : [],
    [preview],
  );

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" size="sm" disabled={disabled}>
          <DatabaseIcon className="mr-2 size-4" />
          Knowledge
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[92vh] max-w-6xl overflow-y-auto">
        <DialogTitle>Knowledge sources</DialogTitle>
        <DialogDescription>
          Browse local folders, select only useful files or directories and
          preview exactly what AI Lab can embed.
        </DialogDescription>

        <div className="rounded-xl border p-3 text-sm">
          <b>{status?.total_chunk_count.toLocaleString() ?? "…"} total chunks</b>
          <span className="ml-2 text-muted-foreground">
            {status?.embedding_model}
          </span>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
          <section className="rounded-xl border">
            <div className="flex items-center gap-2 border-b p-3">
              <Button
                type="button"
                size="icon"
                variant="ghost"
                disabled={!browser?.parent || working}
                onClick={() =>
                  browser?.parent ? void navigate(browser.parent) : undefined
                }
              >
                <ChevronLeftIcon className="size-4" />
              </Button>
              <div className="flex shrink-0 gap-1">
                {roots.map((root) => (
                  <Button
                    key={root.path}
                    type="button"
                    size="sm"
                    variant={browser?.path === root.path ? "secondary" : "ghost"}
                    disabled={working}
                    onClick={() => void navigate(root.path)}
                    title={`Open ${root.path}`}
                  >
                    <HardDriveIcon className="mr-1 size-3.5" />
                    {root.name}
                  </Button>
                ))}
              </div>
              <p className="min-w-0 flex-1 truncate text-sm">
                {browser?.path ?? "Loading…"}
              </p>
            </div>
            <div className="max-h-[420px] overflow-y-auto p-2">
              {browser?.entries.map((entry) => {
                const checked = selected.includes(entry.path);
                return (
                  <div
                    key={entry.path}
                    className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-muted"
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={!entry.supported}
                      onChange={() => toggle(entry.path)}
                      aria-label={`Select ${entry.name}`}
                    />
                    {entry.kind === "directory" ? (
                      <FolderIcon className="size-4 shrink-0" />
                    ) : (
                      <FileIcon className="size-4 shrink-0" />
                    )}
                    <button
                      type="button"
                      className="min-w-0 flex-1 truncate text-left text-sm"
                      disabled={entry.kind !== "directory"}
                      onDoubleClick={() =>
                        entry.kind === "directory"
                          ? void navigate(entry.path)
                          : undefined
                      }
                    >
                      {entry.name}
                    </button>
                    {!entry.supported ? (
                      <span className="text-xs text-muted-foreground">
                        unsupported
                      </span>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </section>

          <section className="space-y-3">
            <div className="rounded-xl border p-4">
              <p className="font-medium">Embedding preview</p>
              {preview ? (
                <>
                  <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <p className="text-muted-foreground">Files</p>
                      <p className="font-semibold">
                        {preview.document_count.toLocaleString()}
                      </p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Estimated chunks</p>
                      <p className="font-semibold">
                        {preview.estimated_chunks.toLocaleString()}
                      </p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Text size</p>
                      <p className="font-semibold">
                        {formatBytes(preview.total_bytes)}
                      </p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Skipped</p>
                      <p className="font-semibold">{preview.skipped.length}</p>
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-1">
                    {extensionSummary.map(([extension, count]) => (
                      <span
                        key={extension}
                        className="rounded bg-muted px-2 py-1 text-xs"
                      >
                        {extension || "none"}: {count}
                      </span>
                    ))}
                  </div>
                </>
              ) : (
                <p className="mt-2 text-sm text-muted-foreground">
                  Select a folder or file to see what can be embedded.
                </p>
              )}
            </div>

            <div className="space-y-3 rounded-xl border p-4">
              <div className="space-y-1">
                <Label htmlFor="knowledge-name">Display name</Label>
                <Input
                  id="knowledge-name"
                  value={name}
                  onChange={(event) => {
                    setName(event.target.value);
                    if (!sourceId) {
                      setSourceId(
                        event.target.value
                          .toLowerCase()
                          .replace(/[^a-z0-9]+/g, "-"),
                      );
                    }
                  }}
                  placeholder="Next.js reference project"
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="knowledge-id">Stable source ID</Label>
                <Input
                  id="knowledge-id"
                  value={sourceId}
                  onChange={(event) => setSourceId(event.target.value)}
                  placeholder="nextjs-reference"
                />
              </div>
            </div>
          </section>
        </div>

        {progress ? (
          <div className="rounded-lg border p-3 text-sm">
            {progress.type === "status"
              ? progress.message
              : progress.type === "progress"
                ? (
                  <>
                    <div className="flex justify-between">
                      <span className="capitalize">{progress.stage}</span>
                      <span>
                        {progress.completed}/{progress.total} ({percentage}%)
                      </span>
                    </div>
                    <div className="mt-2 h-2 rounded bg-muted">
                      <div
                        className="h-full rounded bg-primary"
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </>
                )
                : progress.type === "done"
                  ? `Indexed ${progress.result.document_count} files into ${progress.result.chunk_count} chunks.`
                  : progress.message}
          </div>
        ) : null}

        {error ? (
          <div className="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger">
            {error}
          </div>
        ) : null}

        <div className="max-h-44 space-y-2 overflow-y-auto">
          {status?.sources.map((source) => (
            <div
              key={source.id}
              className="flex items-center justify-between gap-3 rounded-lg border p-3"
            >
              <div className="min-w-0">
                <p className="font-medium">{source.name}</p>
                <p className="truncate text-xs text-muted-foreground">
                  {source.id} · {source.document_count} files ·{" "}
                  {source.chunk_count} chunks
                </p>
              </div>
              <Button
                type="button"
                size="icon"
                variant="ghost"
                disabled={working}
                aria-label={`Remove ${source.name}`}
                onClick={async () => {
                  if (
                    !confirm(
                      `Remove indexed chunks for ${source.name}? Source files are not deleted.`,
                    )
                  ) {
                    return;
                  }
                  setWorking(true);
                  try {
                    await removeKnowledgeSource(source.id);
                    setStatus(await getKnowledgeStatus());
                  } catch (reason) {
                    setError(
                      reason instanceof Error
                        ? reason.message
                        : "Remove failed.",
                    );
                  } finally {
                    setWorking(false);
                  }
                }}
              >
                <Trash2Icon className="size-4" />
              </Button>
            </div>
          ))}
        </div>

        <div className="flex justify-end">
          <Button
            type="button"
            onClick={() => void index()}
            disabled={
              working ||
              !sourceId.trim() ||
              !name.trim() ||
              !selected.length
            }
          >
            {working ? (
              <Loader2Icon className="mr-2 size-4 animate-spin" />
            ) : (
              <PlusIcon className="mr-2 size-4" />
            )}
            Add or update source
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
