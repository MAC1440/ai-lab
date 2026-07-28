"use client";

import {
  DatabaseIcon,
  FileSearchIcon,
  Loader2Icon,
  RefreshCwIcon,
  RotateCcwIcon,
} from "lucide-react";
import { FormEvent, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  getProjectIndexStatus,
  type ProjectIndexQuery,
  type ProjectIndexStatus,
  queryProjectIndex,
  refreshProjectIndex,
} from "@/features/project-index/project-index-api";

function formatDate(value: string | null) {
  if (!value) return "Never";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function ProjectIndexDialog({
  disabled = false,
}: {
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<ProjectIndexStatus | null>(null);
  const [query, setQuery] = useState("");
  const [queryResult, setQueryResult] = useState<ProjectIndexQuery | null>(null);
  const [busy, setBusy] = useState<"status" | "refresh" | "rebuild" | "query" | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  async function loadStatus() {
    setBusy("status");
    setError(null);
    try {
      setStatus(await getProjectIndexStatus());
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Project index status could not be loaded.",
      );
    } finally {
      setBusy(null);
    }
  }

  function handleOpenChange(nextOpen: boolean) {
    setOpen(nextOpen);
    if (nextOpen) void loadStatus();
  }

  async function handleRefresh(rebuild: boolean) {
    setBusy(rebuild ? "rebuild" : "refresh");
    setError(null);
    try {
      const next = await refreshProjectIndex(rebuild);
      setStatus(next);
      setQueryResult(null);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Project index refresh failed.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function handleQuery(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim() || busy) return;
    setBusy("query");
    setError(null);
    try {
      const result = await queryProjectIndex(query.trim());
      setQueryResult(result);
      setStatus(result.index);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Relevant files could not be found.",
      );
    } finally {
      setBusy(null);
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" size="sm" disabled={disabled}>
          <DatabaseIcon className="size-4" />
          Index
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[88vh] max-w-3xl overflow-y-auto">
        <DialogTitle>Project index</DialogTitle>
        <DialogDescription>
          Incremental symbols and dependency metadata used to select relevant
          files before task planning. Full source content is not stored here.
        </DialogDescription>

        {error ? (
          <p className="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger">
            {error}
          </p>
        ) : null}

        <section className="rounded-xl border border-border bg-surface-raised p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <Badge variant="outline">
                  {status?.status.replaceAll("_", " ") ?? "loading"}
                </Badge>
                {status?.scan_truncated ? (
                  <Badge className="border-pending/30 bg-pending/10 text-pending">
                    scan limit reached
                  </Badge>
                ) : null}
              </div>
              <p className="mt-2 max-w-xl truncate text-xs text-muted-foreground">
                {status?.workspace ?? "Reading selected workspace…"}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                Last indexed: {formatDate(status?.indexed_at ?? null)}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={Boolean(busy)}
                onClick={() => void handleRefresh(false)}
              >
                {busy === "refresh" ? (
                  <Loader2Icon className="size-4 animate-spin" />
                ) : (
                  <RefreshCwIcon className="size-4" />
                )}
                Refresh changed
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={Boolean(busy)}
                onClick={() => void handleRefresh(true)}
              >
                {busy === "rebuild" ? (
                  <Loader2Icon className="size-4 animate-spin" />
                ) : (
                  <RotateCcwIcon className="size-4" />
                )}
                Rebuild
              </Button>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-3 gap-3">
            {[
              ["Files", status?.file_count ?? 0],
              ["Symbols", status?.symbol_count ?? 0],
              ["References", status?.reference_count ?? 0],
            ].map(([label, value]) => (
              <div
                key={label}
                className="rounded-lg border border-border bg-surface-raised/40 p-3"
              >
                <p className="text-lg font-semibold text-foreground">{value}</p>
                <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
                  {label}
                </p>
              </div>
            ))}
          </div>

          {status?.refresh ? (
            <p className="mt-3 text-xs text-muted-foreground">
              Last refresh: {status.refresh.changed_files} changed,{" "}
              {status.refresh.unchanged_files} unchanged,{" "}
              {status.refresh.removed_files} removed.
            </p>
          ) : null}
          {status?.last_error ? (
            <p className="mt-3 text-xs text-pending">{status.last_error}</p>
          ) : null}
        </section>

        <section className="rounded-xl border border-border bg-surface-raised p-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <FileSearchIcon className="size-4 text-pending" />
            Test relevant-file selection
          </h3>
          <form className="mt-3 flex gap-2" onSubmit={handleQuery}>
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="e.g. add validation to InventoryService"
              maxLength={12_000}
            />
            <Button type="submit" disabled={!query.trim() || Boolean(busy)}>
              {busy === "query" ? (
                <Loader2Icon className="size-4 animate-spin" />
              ) : (
                <FileSearchIcon className="size-4" />
              )}
              Find
            </Button>
          </form>

          {queryResult ? (
            <div className="mt-4 space-y-2">
              <p className="text-xs text-muted-foreground">
                Tokens: {queryResult.tokens.join(", ") || "none"}
              </p>
              {queryResult.results.map((result) => (
                <article
                  key={result.path}
                  className="rounded-lg border border-border p-3"
                >
                  <div className="flex items-center justify-between gap-3">
                    <code className="min-w-0 truncate text-xs text-foreground">
                      {result.path}
                    </code>
                    <Badge variant="outline">score {result.score}</Badge>
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">
                    {result.reasons.join(" · ") || result.language}
                  </p>
                </article>
              ))}
              {!queryResult.results.length ? (
                <p className="rounded-lg border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
                  No indexed files matched this task description.
                </p>
              ) : null}
            </div>
          ) : null}
        </section>
      </DialogContent>
    </Dialog>
  );
}
