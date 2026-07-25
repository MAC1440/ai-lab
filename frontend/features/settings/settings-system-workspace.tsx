"use client";

import Link from "next/link";
import {
  ActivityIcon, BotIcon, CheckCircle2Icon, DatabaseIcon,
  FolderIcon, GaugeIcon, HardDriveIcon, LibraryIcon,
  RefreshCwIcon, ServerIcon, SettingsIcon, ShieldCheckIcon,
  TriangleAlertIcon,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { getModelSettings, type ModelSettingsSnapshot } from "@/features/model-settings/model-settings-api";
import {
  getHardwareSnapshot, getRuntimeSettings,
  type HardwareSnapshot, type RuntimeSettings,
} from "@/features/runtime/runtime-api";
import {
  getActiveWorkspace, getBackendHealth, getKnowledgeStatus,
  getProjectIndexStatus, getUnityKnowledgeStatus,
  type JsonRecord,
} from "@/features/settings/settings-system-api";
import { cn } from "@/lib/utils";

type Key = "health" | "workspace" | "models" | "runtime" | "hardware" | "projectIndex" | "knowledge" | "unity";
type Snapshots = Partial<Record<Key, unknown>>;

export function SettingsSystemWorkspace() {
  const [snapshots, setSnapshots] = useState<Snapshots>({});
  const [failures, setFailures] = useState<Partial<Record<Key, string>>>({});
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const calls: Array<[Key, Promise<unknown>]> = [
      ["health", getBackendHealth()],
      ["workspace", getActiveWorkspace()],
      ["models", getModelSettings()],
      ["runtime", getRuntimeSettings()],
      ["hardware", getHardwareSnapshot()],
      ["projectIndex", getProjectIndexStatus()],
      ["knowledge", getKnowledgeStatus()],
      ["unity", getUnityKnowledgeStatus()],
    ];
    const results = await Promise.allSettled(calls.map(([, promise]) => promise));
    const next: Snapshots = {};
    const errors: Partial<Record<Key, string>> = {};
    results.forEach((result, index) => {
      const key = calls[index][0];
      if (result.status === "fulfilled") next[key] = result.value;
      else errors[key] = result.reason instanceof Error ? result.reason.message : "Request failed.";
    });
    setSnapshots(next);
    setFailures(errors);
    setLoading(false);
  }, []);

  useEffect(() => { void load(); }, [load]);

  const models = snapshots.models as ModelSettingsSnapshot | undefined;
  const runtime = snapshots.runtime as RuntimeSettings | undefined;
  const hardware = snapshots.hardware as HardwareSnapshot | undefined;
  const health = snapshots.health as JsonRecord | undefined;
  const workspace = snapshots.workspace as JsonRecord | undefined;
  const workspacePath = firstString(workspace?.path, workspace?.workspace, workspace?.root, workspace?.workspace_root);
  const healthStatus = firstString(health?.status) || "unknown";
  const failedCount = Object.keys(failures).length;
  const paths = useMemo(() => collectPaths(snapshots), [snapshots]);

  return (
    <section className="ai-lab-scrollbar flex min-h-0 flex-1 flex-col overflow-y-auto">
      <div className="mx-auto w-full max-w-7xl space-y-6 p-4 sm:p-6">
        <header className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-600 dark:text-emerald-400">Application control plane</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-950 dark:text-zinc-50">Settings and system</h2>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
              Review backend health, workspace selection, model/runtime configuration, storage locations, and subsystem diagnostics.
            </p>
          </div>
          <button type="button" onClick={() => void load()} disabled={loading}
            className="inline-flex w-fit items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs font-medium text-zinc-700 shadow-sm disabled:opacity-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200">
            <RefreshCwIcon className={cn("size-3.5", loading && "animate-spin")} />
            Refresh diagnostics
          </button>
        </header>

        {failedCount > 0 ? (
          <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
            <TriangleAlertIcon className="mt-0.5 size-4 shrink-0" />
            <div>
              <p className="font-medium">{failedCount} subsystem snapshot{failedCount === 1 ? "" : "s"} unavailable</p>
              <p className="mt-1 text-xs opacity-85">Available sections still loaded independently.</p>
            </div>
          </div>
        ) : null}

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Card icon={ServerIcon} label="Backend" value={healthStatus} detail={`${Object.keys(snapshots).length} snapshots loaded`} success={healthStatus === "ok"} />
          <Card icon={FolderIcon} label="Active workspace" value={workspacePath || "Not selected"} detail="Current project root" />
          <Card icon={BotIcon} label="Providers" value={models ? String(models.providers.length) : "—"} detail="Configured model endpoints" />
          <Card icon={GaugeIcon} label="Chat context" value={runtime ? runtime.chat.num_ctx.toLocaleString("en-US") : "—"} detail="Global runtime default" />
        </div>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
          <div className="min-w-0 space-y-6">
            <Section icon={SettingsIcon} title="Configuration overview" description="Open the dedicated workspace for each configurable subsystem.">
              <div className="grid gap-3 md:grid-cols-2">
                <LinkCard href="/models" icon={BotIcon} title="Models and runtime" text="Providers, assignments, capabilities, and token limits." />
                <LinkCard href="/knowledge" icon={LibraryIcon} title="Knowledge and context" text="Project index, sources, Unity docs, and retrieval testing." />
                <LinkCard href="/performance" icon={ActivityIcon} title="Runtime history" text="Persisted speed, duration, stage, and token metrics." />
                <LinkCard href="/verification" icon={ShieldCheckIcon} title="Verification" text="Check results, failures, artifacts, and repair readiness." />
              </div>
            </Section>

            <Section icon={HardDriveIcon} title="Detected storage and paths" description="Path-like values exposed by safe status endpoints.">
              {paths.length ? (
                <div className="space-y-2">
                  {paths.map((item) => (
                    <div key={`${item.label}:${item.value}`} className="rounded-xl border border-zinc-200 bg-zinc-50/60 p-3 dark:border-zinc-800 dark:bg-zinc-900/40">
                      <p className="text-[9px] font-medium uppercase tracking-wide text-zinc-400">{item.label}</p>
                      <p className="mt-2 break-all font-mono text-[11px] text-zinc-700 dark:text-zinc-200">{item.value}</p>
                    </div>
                  ))}
                </div>
              ) : <Empty text="No path-like values were exposed." />}
            </Section>

            <Section icon={DatabaseIcon} title="Advanced subsystem snapshots" description="Raw read-only payloads for troubleshooting.">
              <div className="space-y-3">
                {([
                  ["health", "Backend health"], ["workspace", "Active workspace"],
                  ["models", "Provider and model settings"], ["runtime", "Runtime settings"],
                  ["hardware", "Hardware profile"], ["projectIndex", "Project index"],
                  ["knowledge", "Knowledge sources"], ["unity", "Unity knowledge"],
                ] as Array<[Key, string]>).map(([key, label]) => (
                  <details key={key} className="rounded-xl border border-zinc-200 bg-zinc-50/60 p-3 dark:border-zinc-800 dark:bg-zinc-900/40">
                    <summary className="cursor-pointer text-xs font-medium text-zinc-700 dark:text-zinc-200">
                      {label}{failures[key] ? <span className="ml-2 text-[10px] text-red-500">unavailable</span> : null}
                    </summary>
                    <pre className="ai-lab-scrollbar mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-zinc-950 p-3 text-[10px] leading-relaxed text-zinc-300">
                      {failures[key] ?? JSON.stringify(snapshots[key] ?? "No snapshot loaded.", null, 2)}
                    </pre>
                  </details>
                ))}
              </div>
            </Section>
          </div>

          <aside className="space-y-6">
            <section className="rounded-2xl border border-zinc-200 bg-zinc-950 p-4 text-zinc-100 shadow-sm dark:border-zinc-800">
              <div className="flex items-center gap-2"><ShieldCheckIcon className="size-4 text-emerald-400" /><h3 className="text-sm font-semibold">System readiness</h3></div>
              <div className="mt-4 space-y-3">
                <Ready label="Backend responding" passed={healthStatus === "ok"} detail={healthStatus} />
                <Ready label="Workspace selected" passed={Boolean(workspacePath)} detail={workspacePath || "No active workspace"} />
                <Ready label="Provider configured" passed={Boolean(models?.providers.length)} detail={models ? `${models.providers.length} provider(s)` : "Unavailable"} />
                <Ready label="Runtime configured" passed={Boolean(runtime)} detail={runtime ? `${runtime.chat.num_ctx.toLocaleString("en-US")} chat context` : "Unavailable"} />
                <Ready label="Hardware detected" passed={Boolean(hardware)} detail={hardware ? `${hardware.cpu.logical_cores} logical CPU cores` : "Unavailable"} />
              </div>
            </section>

            <section className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-900 shadow-sm dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
              <h3 className="text-sm font-semibold">Deliberate safety scope</h3>
              <p className="mt-2 text-xs leading-relaxed">
                This page is read-only. Editing remains in Models, Knowledge, Tasks, and Verification.
              </p>
              <p className="mt-3 text-xs leading-relaxed">
                Backup/restore and MCP mutation controls are left unchanged until their exact contracts are checked in the final integration pass.
              </p>
            </section>
          </aside>
        </div>
      </div>
    </section>
  );
}

function Section({ icon: Icon, title, description, children }: {
  icon: typeof SettingsIcon; title: string; description: string; children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      <div className="border-b border-zinc-200 p-4 sm:p-5 dark:border-zinc-800">
        <div className="flex items-start gap-3">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-zinc-100 text-zinc-600 dark:bg-zinc-900 dark:text-zinc-300"><Icon className="size-4" /></div>
          <div><h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{title}</h3><p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{description}</p></div>
        </div>
      </div>
      <div className="p-4 sm:p-5">{children}</div>
    </section>
  );
}

function Card({ icon: Icon, label, value, detail, success = false }: {
  icon: typeof ServerIcon; label: string; value: string; detail: string; success?: boolean;
}) {
  return (
    <div className="min-w-0 rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400">{label}</p>
        <div className={cn("flex size-8 items-center justify-center rounded-lg", success ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" : "bg-zinc-100 text-zinc-600 dark:bg-zinc-900 dark:text-zinc-300")}><Icon className="size-4" /></div>
      </div>
      <p className="mt-4 truncate text-base font-semibold text-zinc-950 dark:text-zinc-50">{value}</p>
      <p className="mt-1 truncate text-[11px] text-zinc-400">{detail}</p>
    </div>
  );
}

function LinkCard({ href, icon: Icon, title, text }: {
  href: string; icon: typeof BotIcon; title: string; text: string;
}) {
  return (
    <Link href={href} className="rounded-xl border border-zinc-200 bg-zinc-50/60 p-4 transition hover:border-emerald-300 dark:border-zinc-800 dark:bg-zinc-900/40 dark:hover:border-emerald-900">
      <div className="flex items-center gap-2"><Icon className="size-4 text-emerald-600 dark:text-emerald-400" /><p className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">{title}</p></div>
      <p className="mt-2 text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">{text}</p>
    </Link>
  );
}

function Ready({ label, passed, detail }: { label: string; passed: boolean; detail: string }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-3">
      <div className="flex items-center gap-2">
        {passed ? <CheckCircle2Icon className="size-3.5 text-emerald-400" /> : <TriangleAlertIcon className="size-3.5 text-amber-400" />}
        <p className="text-xs font-medium text-zinc-200">{label}</p>
      </div>
      <p className="mt-1 break-all text-[10px] text-zinc-500">{detail}</p>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="rounded-xl border border-dashed border-zinc-200 p-6 text-center text-xs text-zinc-400 dark:border-zinc-800">{text}</div>;
}

function firstString(...values: unknown[]): string {
  for (const value of values) if (typeof value === "string" && value.trim()) return value;
  return "";
}

function collectPaths(snapshots: Snapshots): Array<{ label: string; value: string }> {
  const output: Array<{ label: string; value: string }> = [];
  const seen = new Set<string>();
  function visit(value: unknown, path: string[]) {
    if (output.length >= 30) return;
    if (typeof value === "string") {
      const key = path.at(-1)?.toLowerCase() ?? "";
      const pathLike =
        ["path", "root", "directory", "database", "storage", "workspace"].some((token) => key.includes(token))
        || /^[a-zA-Z]:[\\/]/.test(value) || value.startsWith("/")
        || value.includes("\\") || value.endsWith(".sqlite3") || value.endsWith(".db");
      if (pathLike && !seen.has(value)) {
        seen.add(value);
        output.push({ label: path.join("."), value });
      }
      return;
    }
    if (Array.isArray(value)) {
      value.slice(0, 20).forEach((item, index) => visit(item, [...path, String(index)]));
    } else if (value && typeof value === "object") {
      Object.entries(value as Record<string, unknown>).slice(0, 100).forEach(([key, item]) => visit(item, [...path, key]));
    }
  }
  Object.entries(snapshots).forEach(([key, value]) => visit(value, [key]));
  return output;
}
