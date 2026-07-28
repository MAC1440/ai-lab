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

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

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
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-success dark:text-success">Application control plane</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-foreground dark:text-foreground">Settings and system</h2>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground dark:text-muted-foreground">
              Review backend health, workspace selection, model/runtime configuration, storage locations, and subsystem diagnostics.
            </p>
          </div>
          <button type="button" onClick={() => void load()} disabled={loading}
            className="inline-flex w-fit items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-xs font-medium text-foreground shadow-sm disabled:opacity-50 dark:border-border dark:bg-surface-raised dark:text-foreground">
            <RefreshCwIcon className={cn("size-3.5", loading && "animate-spin")} />
            Refresh diagnostics
          </button>
        </header>

        {failedCount > 0 ? (
          <div className="flex items-start gap-3 rounded-xl border border-pending/30 bg-pending/10 p-4 text-sm text-pending dark:border-pending/30 dark:bg-pending/10 dark:text-pending">
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
                    <div key={`${item.label}:${item.value}`} className="rounded-xl border border-border bg-surface-hover/60 p-3 dark:border-border dark:bg-surface-raised/40">
                      <p className="text-[9px] font-medium uppercase tracking-wide text-muted-foreground">{item.label}</p>
                      <p className="mt-2 break-all font-mono text-[11px] text-foreground dark:text-foreground">{item.value}</p>
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
                  <details key={key} className="rounded-xl border border-border bg-surface-hover/60 p-3 dark:border-border dark:bg-surface-raised/40">
                    <summary className="cursor-pointer text-xs font-medium text-foreground dark:text-foreground">
                      {label}{failures[key] ? <span className="ml-2 text-[10px] text-danger">unavailable</span> : null}
                    </summary>
                    <pre className="ai-lab-scrollbar mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-surface-raised p-3 text-[10px] leading-relaxed text-muted-foreground">
                      {failures[key] ?? JSON.stringify(snapshots[key] ?? "No snapshot loaded.", null, 2)}
                    </pre>
                  </details>
                ))}
              </div>
            </Section>
          </div>

          <aside className="space-y-6">
            <section className="rounded-2xl border border-border bg-surface-raised p-4 text-foreground shadow-sm dark:border-border">
              <div className="flex items-center gap-2"><ShieldCheckIcon className="size-4 text-success" /><h3 className="text-sm font-semibold">System readiness</h3></div>
              <div className="mt-4 space-y-3">
                <Ready label="Backend responding" passed={healthStatus === "ok"} detail={healthStatus} />
                <Ready label="Workspace selected" passed={Boolean(workspacePath)} detail={workspacePath || "No active workspace"} />
                <Ready label="Provider configured" passed={Boolean(models?.providers.length)} detail={models ? `${models.providers.length} provider(s)` : "Unavailable"} />
                <Ready label="Runtime configured" passed={Boolean(runtime)} detail={runtime ? `${runtime.chat.num_ctx.toLocaleString("en-US")} chat context` : "Unavailable"} />
                <Ready label="Hardware detected" passed={Boolean(hardware)} detail={hardware ? `${hardware.cpu.logical_cores} logical CPU cores` : "Unavailable"} />
              </div>
            </section>

            <section className="rounded-2xl border border-pending/30 bg-pending/10 p-4 text-pending shadow-sm dark:border-pending/30 dark:bg-pending/10 dark:text-pending">
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
    <section className="rounded-2xl border border-border bg-surface shadow-sm dark:border-border dark:bg-surface-raised">
      <div className="border-b border-border p-4 sm:p-5 dark:border-border">
        <div className="flex items-start gap-3">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-surface-hover text-muted-foreground dark:bg-surface-raised dark:text-muted-foreground"><Icon className="size-4" /></div>
          <div><h3 className="text-sm font-semibold text-foreground dark:text-foreground">{title}</h3><p className="mt-1 text-xs text-muted-foreground dark:text-muted-foreground">{description}</p></div>
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
    <div className="min-w-0 rounded-2xl border border-border bg-surface p-4 shadow-sm dark:border-border dark:bg-surface-raised">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-muted-foreground dark:text-muted-foreground">{label}</p>
        <div className={cn("flex size-8 items-center justify-center rounded-lg", success ? "bg-success/10 text-success dark:text-success" : "bg-surface-hover text-muted-foreground dark:bg-surface-raised dark:text-muted-foreground")}><Icon className="size-4" /></div>
      </div>
      <p className="mt-4 truncate text-base font-semibold text-foreground dark:text-foreground">{value}</p>
      <p className="mt-1 truncate text-[11px] text-muted-foreground">{detail}</p>
    </div>
  );
}

function LinkCard({ href, icon: Icon, title, text }: {
  href: string; icon: typeof BotIcon; title: string; text: string;
}) {
  return (
    <Link href={href} className="rounded-xl border border-border bg-surface-hover/60 p-4 transition hover:border-success/30 dark:border-border dark:bg-surface-raised/40 dark:hover:border-success/30">
      <div className="flex items-center gap-2"><Icon className="size-4 text-success dark:text-success" /><p className="text-sm font-semibold text-foreground dark:text-foreground">{title}</p></div>
      <p className="mt-2 text-xs leading-relaxed text-muted-foreground dark:text-muted-foreground">{text}</p>
    </Link>
  );
}

function Ready({ label, passed, detail }: { label: string; passed: boolean; detail: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface-raised/70 p-3">
      <div className="flex items-center gap-2">
        {passed ? <CheckCircle2Icon className="size-3.5 text-success" /> : <TriangleAlertIcon className="size-3.5 text-pending" />}
        <p className="text-xs font-medium text-foreground">{label}</p>
      </div>
      <p className="mt-1 break-all text-[10px] text-muted-foreground">{detail}</p>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="rounded-xl border border-dashed border-border p-6 text-center text-xs text-muted-foreground dark:border-border">{text}</div>;
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
