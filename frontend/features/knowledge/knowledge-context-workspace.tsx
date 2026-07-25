"use client";

import {
  BookOpenIcon,
  BoxesIcon,
  CheckCircle2Icon,
  DatabaseIcon,
  FileCode2Icon,
  FolderIcon,
  HardDriveIcon,
  LibraryIcon,
  RefreshCwIcon,
  SearchIcon,
  ShieldAlertIcon,
  Trash2Icon,
  TriangleAlertIcon,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  getActiveWorkspace,
  getKnowledgeSourcesStatus,
  getProjectIndexStatus,
  getUnityKnowledgeStatus,
  queryProjectIndex,
  refreshProjectIndex,
  removeKnowledgeSource,
  type JsonRecord,
} from "@/features/knowledge/knowledge-workspace-api";
import { cn } from "@/lib/utils";

type NormalizedSource = {
  id: string;
  name: string;
  path: string | null;
  documentCount: number | null;
  chunkCount: number | null;
  updatedAt: string | null;
  raw: JsonRecord;
};

type RetrievalResult = {
  path: string;
  content: string;
  score: number | null;
  metadata: JsonRecord;
};

export function KnowledgeContextWorkspace() {
  const [workspace, setWorkspace] = useState<JsonRecord | null>(null);
  const [sourceStatus, setSourceStatus] = useState<JsonRecord | null>(null);
  const [unityStatus, setUnityStatus] = useState<JsonRecord | null>(null);
  const [indexStatus, setIndexStatus] = useState<JsonRecord | null>(null);
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(8);
  const [refreshBeforeQuery, setRefreshBeforeQuery] = useState(true);
  const [queryResponse, setQueryResponse] = useState<JsonRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadWorkspace = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [workspaceResult, sourcesResult, unityResult, indexResult] =
        await Promise.all([
          getActiveWorkspace(),
          getKnowledgeSourcesStatus(),
          getUnityKnowledgeStatus(),
          getProjectIndexStatus(),
        ]);

      setWorkspace(workspaceResult);
      setSourceStatus(sourcesResult);
      setUnityStatus(unityResult);
      setIndexStatus(indexResult);
    } catch (loadError) {
      setError(
        toMessage(loadError, "Knowledge workspace could not be loaded."),
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  const sources = useMemo(
    () => normalizeSources(sourceStatus),
    [sourceStatus],
  );

  const retrievalResults = useMemo(
    () => normalizeRetrievalResults(queryResponse),
    [queryResponse],
  );

  const activeWorkspacePath = firstString(
    workspace?.path,
    workspace?.workspace,
    workspace?.root,
    workspace?.workspace_root,
  );

  async function refreshIndex(rebuild: boolean) {
    const key = rebuild ? "index:rebuild" : "index:refresh";
    setBusyKey(key);
    setError(null);
    setNotice(null);

    try {
      const result = await refreshProjectIndex(rebuild);
      setIndexStatus(result);
      setNotice(
        rebuild
          ? "Project index rebuilt successfully."
          : "Project index refreshed successfully.",
      );
    } catch (refreshError) {
      setError(
        toMessage(refreshError, "Project index refresh failed."),
      );
    } finally {
      setBusyKey(null);
    }
  }

  async function runQuery() {
    if (!query.trim()) return;

    setBusyKey("query");
    setError(null);
    setNotice(null);

    try {
      const result = await queryProjectIndex({
        query: query.trim(),
        limit,
        project_root: activeWorkspacePath || null,
        refresh: refreshBeforeQuery,
      });
      setQueryResponse(result);
      setNotice(
        `Retrieved ${normalizeRetrievalResults(result).length} project result(s).`,
      );
      if (refreshBeforeQuery) {
        setIndexStatus(await getProjectIndexStatus());
      }
    } catch (queryError) {
      setError(toMessage(queryError, "Project retrieval query failed."));
    } finally {
      setBusyKey(null);
    }
  }

  async function removeSource(source: NormalizedSource) {
    if (
      !window.confirm(
        `Remove "${source.name}" from indexed knowledge sources?`,
      )
    ) {
      return;
    }

    setBusyKey(`source:${source.id}`);
    setError(null);
    setNotice(null);

    try {
      await removeKnowledgeSource(source.id);
      setSourceStatus(await getKnowledgeSourcesStatus());
      setNotice(`Removed ${source.name}.`);
    } catch (removeError) {
      setError(toMessage(removeError, "Knowledge source removal failed."));
    } finally {
      setBusyKey(null);
    }
  }

  const summary = buildSummary({
    sourceStatus,
    unityStatus,
    indexStatus,
    sources,
  });

  return (
    <section className="ai-lab-scrollbar flex min-h-0 flex-1 flex-col overflow-y-auto">
      <div className="mx-auto w-full max-w-7xl space-y-6 p-4 sm:p-6">
        <WorkspaceHeader
          loading={loading}
          busy={busyKey !== null}
          onRefresh={() => void loadWorkspace()}
        />

        {error ? (
          <Banner
            tone="error"
            title="Knowledge workspace error"
            message={error}
          />
        ) : null}

        {notice ? (
          <Banner
            tone="success"
            title="Knowledge workspace updated"
            message={notice}
          />
        ) : null}

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <OverviewCard
            icon={FolderIcon}
            label="Active workspace"
            value={activeWorkspacePath || "Not selected"}
            detail={workspace ? "Current project context root" : "Workspace unavailable"}
          />
          <OverviewCard
            icon={LibraryIcon}
            label="Knowledge sources"
            value={formatInteger(summary.sourceCount)}
            detail={`${formatInteger(summary.sourceChunks)} indexed chunks`}
          />
          <OverviewCard
            icon={FileCode2Icon}
            label="Project index"
            value={formatInteger(summary.projectFiles)}
            detail={`${formatInteger(summary.projectChunks)} searchable chunks`}
          />
          <OverviewCard
            icon={BookOpenIcon}
            label="Unity knowledge"
            value={summary.unityReady ? "Ready" : "Not indexed"}
            detail={`${formatInteger(summary.unityDocuments)} documents · ${formatInteger(summary.unityChunks)} chunks`}
          />
        </div>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
          <div className="min-w-0 space-y-6">
            <RetrievalDiagnostics
              query={query}
              limit={limit}
              refreshBeforeQuery={refreshBeforeQuery}
              response={queryResponse}
              results={retrievalResults}
              running={busyKey === "query"}
              onQueryChange={setQuery}
              onLimitChange={setLimit}
              onRefreshBeforeQueryChange={setRefreshBeforeQuery}
              onSubmit={() => void runQuery()}
            />

            <KnowledgeSources
              sources={sources}
              rawStatus={sourceStatus}
              busyKey={busyKey}
              loading={loading}
              onRemove={(source) => void removeSource(source)}
            />
          </div>

          <aside className="space-y-6">
            <ProjectIndexCard
              status={indexStatus}
              busyKey={busyKey}
              onRefresh={(rebuild) => void refreshIndex(rebuild)}
            />

            <ContextDiagnostics
              workspace={workspace}
              unityStatus={unityStatus}
              sourceStatus={sourceStatus}
            />
          </aside>
        </div>
      </div>
    </section>
  );
}

function WorkspaceHeader({
  loading,
  busy,
  onRefresh,
}: {
  loading: boolean;
  busy: boolean;
  onRefresh: () => void;
}) {
  return (
    <header className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-600 dark:text-emerald-400">
          Retrieval visibility
        </p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-950 dark:text-zinc-50">
          Knowledge and project context
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
          Inspect local knowledge sources, rebuild the project index, and test
          exactly which project files retrieval would return for an agent query.
        </p>
      </div>

      <button
        type="button"
        onClick={onRefresh}
        disabled={loading || busy}
        className="inline-flex w-fit items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs font-medium text-zinc-700 shadow-sm disabled:opacity-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200"
      >
        <RefreshCwIcon
          className={cn("size-3.5", loading && "animate-spin")}
        />
        Refresh workspace
      </button>
    </header>
  );
}

function RetrievalDiagnostics({
  query,
  limit,
  refreshBeforeQuery,
  response,
  results,
  running,
  onQueryChange,
  onLimitChange,
  onRefreshBeforeQueryChange,
  onSubmit,
}: {
  query: string;
  limit: number;
  refreshBeforeQuery: boolean;
  response: JsonRecord | null;
  results: RetrievalResult[];
  running: boolean;
  onQueryChange: (value: string) => void;
  onLimitChange: (value: number) => void;
  onRefreshBeforeQueryChange: (value: boolean) => void;
  onSubmit: () => void;
}) {
  return (
    <section className="rounded-2xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      <div className="border-b border-zinc-200 p-4 sm:p-5 dark:border-zinc-800">
        <div className="flex items-start gap-3">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
            <SearchIcon className="size-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              Project retrieval diagnostics
            </h3>
            <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
              Query the same persistent project index used to supply relevant
              workspace files to agents.
            </p>
          </div>
        </div>

        <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_7rem_auto]">
          <textarea
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="Example: Where is project-task cancellation handled?"
            rows={3}
            maxLength={12_000}
            className={cn(inputClass, "resize-y")}
          />

          <label className="block">
            <span className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">
              Result limit
            </span>
            <select
              value={limit}
              onChange={(event) => onLimitChange(Number(event.target.value))}
              className="mt-1.5 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs outline-none dark:border-zinc-800 dark:bg-zinc-900"
            >
              {[4, 8, 12, 20, 30, 50].map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>

          <div className="flex flex-col justify-end gap-2">
            <label className="flex items-center gap-2 text-[11px] text-zinc-500">
              <input
                type="checkbox"
                checked={refreshBeforeQuery}
                onChange={(event) =>
                  onRefreshBeforeQueryChange(event.target.checked)
                }
              />
              Refresh first
            </label>
            <button
              type="button"
              onClick={onSubmit}
              disabled={!query.trim() || running}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-zinc-900 px-4 py-2 text-xs font-medium text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
            >
              <SearchIcon className="size-3.5" />
              {running ? "Retrieving…" : "Test retrieval"}
            </button>
          </div>
        </div>
      </div>

      <div className="p-4 sm:p-5">
        {response ? (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs font-medium text-zinc-600 dark:text-zinc-300">
                {results.length} result{results.length === 1 ? "" : "s"}
              </p>
              <p className="text-[10px] text-zinc-400">
                {responseSummary(response)}
              </p>
            </div>

            <div className="mt-3 space-y-3">
              {results.map((result, index) => (
                <RetrievalResultCard
                  key={`${result.path}-${index}`}
                  result={result}
                  index={index}
                />
              ))}

              {results.length === 0 ? (
                <EmptyPanel message="The query returned no normalized project results. Expand the raw response below to inspect its shape." />
              ) : null}
            </div>

            <details className="mt-4">
              <summary className="cursor-pointer text-[10px] font-medium text-zinc-400">
                Raw retrieval response
              </summary>
              <pre className="ai-lab-scrollbar mt-2 max-h-96 overflow-auto rounded-lg bg-zinc-950 p-3 text-[11px] text-zinc-300">
                {JSON.stringify(response, null, 2)}
              </pre>
            </details>
          </>
        ) : (
          <EmptyPanel message="Run a natural-language query to see which project files and chunks would be retrieved." />
        )}
      </div>
    </section>
  );
}

function RetrievalResultCard({
  result,
  index,
}: {
  result: RetrievalResult;
  index: number;
}) {
  return (
    <article className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
      <div className="flex flex-wrap items-center justify-between gap-2 bg-zinc-50 px-4 py-3 dark:bg-zinc-900/50">
        <div className="flex min-w-0 items-center gap-2">
          <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-white text-[10px] font-semibold text-zinc-500 shadow-sm dark:bg-zinc-950">
            {index + 1}
          </span>
          <p className="break-all font-mono text-xs font-medium text-zinc-800 dark:text-zinc-200">
            {result.path}
          </p>
        </div>

        {result.score != null ? (
          <span className="rounded-full bg-emerald-500/10 px-2 py-1 text-[9px] font-medium text-emerald-700 dark:text-emerald-300">
            score {result.score.toFixed(4)}
          </span>
        ) : null}
      </div>

      <pre className="ai-lab-scrollbar max-h-72 overflow-auto whitespace-pre-wrap break-words bg-white p-4 font-mono text-[11px] leading-relaxed text-zinc-600 dark:bg-zinc-950 dark:text-zinc-300">
        {result.content || "No text preview was included."}
      </pre>
    </article>
  );
}

function KnowledgeSources({
  sources,
  rawStatus,
  busyKey,
  loading,
  onRemove,
}: {
  sources: NormalizedSource[];
  rawStatus: JsonRecord | null;
  busyKey: string | null;
  loading: boolean;
  onRemove: (source: NormalizedSource) => void;
}) {
  return (
    <section className="rounded-2xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      <div className="border-b border-zinc-200 p-4 sm:p-5 dark:border-zinc-800">
        <div className="flex items-start gap-3">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-zinc-100 text-zinc-600 dark:bg-zinc-900 dark:text-zinc-300">
            <LibraryIcon className="size-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              Indexed knowledge sources
            </h3>
            <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
              General local sources indexed outside the active project index.
            </p>
          </div>
        </div>
      </div>

      <div className="divide-y divide-zinc-100 dark:divide-zinc-900">
        {loading ? (
          <div className="p-8 text-center text-xs text-zinc-400">
            Loading knowledge sources…
          </div>
        ) : sources.length > 0 ? (
          sources.map((source) => (
            <div
              key={source.id}
              className="flex flex-col gap-3 p-4 sm:flex-row sm:items-start sm:justify-between sm:p-5"
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">
                    {source.name}
                  </p>
                  <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-[9px] font-medium text-zinc-500 dark:bg-zinc-800 dark:text-zinc-300">
                    {formatInteger(source.documentCount)} docs
                  </span>
                  <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-[9px] font-medium text-zinc-500 dark:bg-zinc-800 dark:text-zinc-300">
                    {formatInteger(source.chunkCount)} chunks
                  </span>
                </div>
                <p className="mt-2 break-all font-mono text-[10px] text-zinc-400">
                  {source.path || source.id}
                </p>
                {source.updatedAt ? (
                  <p className="mt-1 text-[10px] text-zinc-400">
                    Updated {formatTimestamp(source.updatedAt)}
                  </p>
                ) : null}
              </div>

              <button
                type="button"
                onClick={() => onRemove(source)}
                disabled={busyKey === `source:${source.id}`}
                className="inline-flex w-fit shrink-0 items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs font-medium text-red-700 disabled:opacity-50 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300"
              >
                <Trash2Icon className="size-3.5" />
                {busyKey === `source:${source.id}` ? "Removing…" : "Remove"}
              </button>
            </div>
          ))
        ) : (
          <div className="p-5">
            <EmptyPanel message="No normalized knowledge sources were found." />
            {rawStatus ? (
              <details className="mt-4">
                <summary className="cursor-pointer text-[10px] font-medium text-zinc-400">
                  Raw source status
                </summary>
                <pre className="ai-lab-scrollbar mt-2 max-h-96 overflow-auto rounded-lg bg-zinc-950 p-3 text-[11px] text-zinc-300">
                  {JSON.stringify(rawStatus, null, 2)}
                </pre>
              </details>
            ) : null}
          </div>
        )}
      </div>
    </section>
  );
}

function ProjectIndexCard({
  status,
  busyKey,
  onRefresh,
}: {
  status: JsonRecord | null;
  busyKey: string | null;
  onRefresh: (rebuild: boolean) => void;
}) {
  const root = firstString(
    status?.project_root,
    status?.workspace,
    status?.root,
  );
  const fileCount = firstNumber(
    status?.file_count,
    status?.files,
    status?.indexed_files,
  );
  const chunkCount = firstNumber(
    status?.chunk_count,
    status?.chunks,
    status?.indexed_chunks,
  );
  const updatedAt = firstString(
    status?.updated_at,
    status?.refreshed_at,
    status?.indexed_at,
  );

  return (
    <section className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            Project index
          </h3>
          <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
            Persistent searchable project-file context.
          </p>
        </div>
        <DatabaseIcon className="size-4 text-emerald-500" />
      </div>

      <dl className="mt-4 space-y-3 text-xs">
        <MetricRow label="Root" value={root || "Active workspace"} />
        <MetricRow label="Files" value={formatInteger(fileCount)} />
        <MetricRow label="Chunks" value={formatInteger(chunkCount)} />
        <MetricRow
          label="Updated"
          value={updatedAt ? formatTimestamp(updatedAt) : "Unknown"}
        />
      </dl>

      <div className="mt-4 grid gap-2">
        <button
          type="button"
          onClick={() => onRefresh(false)}
          disabled={busyKey !== null}
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-zinc-200 px-3 py-2 text-xs font-medium text-zinc-600 disabled:opacity-50 dark:border-zinc-800 dark:text-zinc-300"
        >
          <RefreshCwIcon
            className={cn(
              "size-3.5",
              busyKey === "index:refresh" && "animate-spin",
            )}
          />
          {busyKey === "index:refresh" ? "Refreshing…" : "Refresh changed files"}
        </button>

        <button
          type="button"
          onClick={() => {
            if (
              window.confirm(
                "Rebuild the complete project index from the active workspace?",
              )
            ) {
              onRefresh(true);
            }
          }}
          disabled={busyKey !== null}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-zinc-900 px-3 py-2 text-xs font-medium text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
        >
          <BoxesIcon className="size-3.5" />
          {busyKey === "index:rebuild" ? "Rebuilding…" : "Rebuild complete index"}
        </button>
      </div>

      {status ? (
        <details className="mt-4">
          <summary className="cursor-pointer text-[10px] font-medium text-zinc-400">
            Raw index status
          </summary>
          <pre className="ai-lab-scrollbar mt-2 max-h-80 overflow-auto rounded-lg bg-zinc-950 p-3 text-[11px] text-zinc-300">
            {JSON.stringify(status, null, 2)}
          </pre>
        </details>
      ) : null}
    </section>
  );
}

function ContextDiagnostics({
  workspace,
  unityStatus,
  sourceStatus,
}: {
  workspace: JsonRecord | null;
  unityStatus: JsonRecord | null;
  sourceStatus: JsonRecord | null;
}) {
  return (
    <section className="rounded-2xl border border-zinc-200 bg-zinc-950 p-4 text-zinc-100 shadow-sm dark:border-zinc-800">
      <div className="flex items-center gap-2">
        <HardDriveIcon className="size-4 text-emerald-400" />
        <h3 className="text-sm font-semibold">Context diagnostics</h3>
      </div>

      <p className="mt-2 text-xs leading-relaxed text-zinc-400">
        These snapshots expose what the backend currently knows. Expand them
        when retrieval behavior looks surprising.
      </p>

      <div className="mt-4 space-y-3">
        <RawSnapshot
          title="Active workspace"
          value={workspace}
        />
        <RawSnapshot
          title="Unity knowledge"
          value={unityStatus}
        />
        <RawSnapshot
          title="General sources"
          value={sourceStatus}
        />
      </div>
    </section>
  );
}

function RawSnapshot({
  title,
  value,
}: {
  title: string;
  value: JsonRecord | null;
}) {
  return (
    <details className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-3">
      <summary className="cursor-pointer text-xs font-medium text-zinc-300">
        {title}
      </summary>
      <pre className="ai-lab-scrollbar mt-3 max-h-72 overflow-auto whitespace-pre-wrap break-words text-[10px] leading-relaxed text-zinc-400">
        {value ? JSON.stringify(value, null, 2) : "Unavailable"}
      </pre>
    </details>
  );
}

function OverviewCard({
  icon: Icon,
  label,
  value,
  detail,
}: {
  icon: typeof FolderIcon;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="min-w-0 rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
          {label}
        </p>
        <div className="flex size-8 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
          <Icon className="size-4" />
        </div>
      </div>
      <p className="mt-4 truncate text-base font-semibold text-zinc-950 dark:text-zinc-50">
        {value}
      </p>
      <p className="mt-1 truncate text-[11px] text-zinc-400">{detail}</p>
    </div>
  );
}

function MetricRow({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="text-zinc-500">{label}</dt>
      <dd className="break-all text-right font-medium text-zinc-700 dark:text-zinc-200">
        {value}
      </dd>
    </div>
  );
}

function Banner({
  tone,
  title,
  message,
}: {
  tone: "error" | "success";
  title: string;
  message: string;
}) {
  const Icon = tone === "error" ? TriangleAlertIcon : CheckCircle2Icon;

  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded-xl border p-4 text-sm",
        tone === "error"
          ? "border-red-200 bg-red-50 text-red-800 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-200"
          : "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-200",
      )}
    >
      <Icon className="mt-0.5 size-4 shrink-0" />
      <div>
        <p className="font-medium">{title}</p>
        <p className="mt-1 text-xs opacity-85">{message}</p>
      </div>
    </div>
  );
}

function EmptyPanel({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-dashed border-zinc-200 p-6 text-center text-xs text-zinc-400 dark:border-zinc-800">
      {message}
    </div>
  );
}

function normalizeSources(status: JsonRecord | null): NormalizedSource[] {
  if (!status) return [];

  const candidates = firstArray(
    status.sources,
    status.items,
    status.knowledge_sources,
    status.indexes,
  );

  return candidates
    .filter(isRecord)
    .map((source, index) => ({
      id: firstString(
        source.source_id,
        source.id,
        source.name,
        `source-${index}`,
      ),
      name: firstString(
        source.name,
        source.title,
        source.source_id,
        `Knowledge source ${index + 1}`,
      ),
      path:
        firstString(
          source.path,
          source.root,
          source.source_directory,
          source.location,
        ) || null,
      documentCount: firstNumber(
        source.document_count,
        source.documents,
        source.file_count,
        source.files,
      ),
      chunkCount: firstNumber(
        source.chunk_count,
        source.chunks,
        source.indexed_chunks,
      ),
      updatedAt:
        firstString(
          source.updated_at,
          source.indexed_at,
          source.created_at,
        ) || null,
      raw: source,
    }));
}

function normalizeRetrievalResults(
  response: JsonRecord | null,
): RetrievalResult[] {
  if (!response) return [];

  const candidates = firstArray(
    response.results,
    response.matches,
    response.items,
    response.chunks,
    response.documents,
    response.context,
  );

  return candidates
    .filter(isRecord)
    .map((item, index) => {
      const metadata = isRecord(item.metadata) ? item.metadata : {};
      return {
        path: firstString(
          item.path,
          item.file_path,
          item.source,
          item.document,
          metadata.path,
          metadata.file_path,
          `Result ${index + 1}`,
        ),
        content: firstString(
          item.content,
          item.text,
          item.chunk,
          item.preview,
          item.snippet,
        ),
        score: firstNumber(
          item.score,
          item.similarity,
          item.relevance,
          item.distance,
        ),
        metadata,
      };
    });
}

function buildSummary({
  sourceStatus,
  unityStatus,
  indexStatus,
  sources,
}: {
  sourceStatus: JsonRecord | null;
  unityStatus: JsonRecord | null;
  indexStatus: JsonRecord | null;
  sources: NormalizedSource[];
}) {
  return {
    sourceCount:
      firstNumber(
        sourceStatus?.source_count,
        sourceStatus?.count,
      ) ?? sources.length,
    sourceChunks:
      firstNumber(
        sourceStatus?.chunk_count,
        sourceStatus?.chunks,
        sourceStatus?.indexed_chunks,
      )
      ?? sumNullable(sources.map((source) => source.chunkCount)),
    projectFiles: firstNumber(
      indexStatus?.file_count,
      indexStatus?.files,
      indexStatus?.indexed_files,
    ),
    projectChunks: firstNumber(
      indexStatus?.chunk_count,
      indexStatus?.chunks,
      indexStatus?.indexed_chunks,
    ),
    unityReady:
      firstBoolean(
        unityStatus?.ready,
        unityStatus?.indexed,
        unityStatus?.available,
      )
      ?? (firstNumber(
        unityStatus?.chunk_count,
        unityStatus?.chunks,
      ) ?? 0) > 0,
    unityDocuments: firstNumber(
      unityStatus?.document_count,
      unityStatus?.documents,
      unityStatus?.file_count,
      unityStatus?.files,
    ),
    unityChunks: firstNumber(
      unityStatus?.chunk_count,
      unityStatus?.chunks,
      unityStatus?.indexed_chunks,
    ),
  };
}

function responseSummary(response: JsonRecord): string {
  const root = firstString(
    response.project_root,
    response.root,
    response.workspace,
  );
  const refreshed = firstBoolean(
    response.refreshed,
    response.index_refreshed,
  );

  return [
    root ? `root: ${root}` : "",
    refreshed == null ? "" : refreshed ? "index refreshed" : "cached index",
  ]
    .filter(Boolean)
    .join(" · ");
}

function firstArray(...values: unknown[]): unknown[] {
  for (const value of values) {
    if (Array.isArray(value)) return value;
  }
  return [];
}

function firstString(...values: unknown[]): string {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) return value;
  }
  return "";
}

function firstNumber(...values: unknown[]): number | null {
  for (const value of values) {
    if (typeof value === "number" && Number.isFinite(value)) return value;
    if (
      typeof value === "string"
      && value.trim()
      && Number.isFinite(Number(value))
    ) {
      return Number(value);
    }
  }
  return null;
}

function firstBoolean(...values: unknown[]): boolean | null {
  for (const value of values) {
    if (typeof value === "boolean") return value;
  }
  return null;
}

function isRecord(value: unknown): value is JsonRecord {
  return (
    typeof value === "object"
    && value !== null
    && !Array.isArray(value)
  );
}

function sumNullable(values: Array<number | null>): number | null {
  const valid = values.filter((value): value is number => value != null);
  return valid.length > 0
    ? valid.reduce((total, value) => total + value, 0)
    : null;
}

function formatInteger(value: number | null | undefined): string {
  return value == null ? "—" : value.toLocaleString("en-US");
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function toMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

const inputClass =
  "w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-800 outline-none ring-emerald-500/20 placeholder:text-zinc-400 focus:border-emerald-500 focus:ring-4 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200";
