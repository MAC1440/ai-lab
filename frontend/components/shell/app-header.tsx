"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  MenuIcon,
  PanelLeftCloseIcon,
  PanelLeftOpenIcon,
  PlusIcon,
  SparklesIcon,
} from "lucide-react";

const sections: Record<string, { title: string; description: string }> = {
  "/": { title: "Agent Chat", description: "Inspect, reason, propose changes, and verify work." },
  "/tasks": { title: "Project Tasks", description: "Run bounded coding work from planning through verification." },
  "/terminal": { title: "Workspace Terminal", description: "Run PowerShell and Claude Code directly in the selected workspace." },
  "/changes": { title: "Changes", description: "Review task-linked change sets and proposed file operations." },
  "/verification": { title: "Verification", description: "Inspect workspace checks, failures, and repair readiness." },
  "/knowledge": { title: "Knowledge and Context", description: "Inspect indexed sources, project retrieval, and workspace context." },
  "/models": { title: "Models and Runtime", description: "Manage local providers, assignments, limits, and hardware fit." },
  "/performance": { title: "Performance", description: "Review persisted model speed, duration, and token usage." },
  "/settings": { title: "Settings and System", description: "Inspect application health, workspace state, and configuration." },
};

export function AppHeader({
  sidebarCollapsed,
  onOpenMobileNavigation,
}: {
  sidebarCollapsed: boolean;
  onOpenMobileNavigation: () => void;
}) {
  const pathname = usePathname();
  const details = sections[pathname] ?? {
    title: "AI Lab",
    description: "Local agent workspace.",
  };

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-border bg-background/85 px-4 backdrop-blur">
      <button
        type="button"
        onClick={onOpenMobileNavigation}
        className="flex size-9 items-center justify-center rounded-lg border border-border bg-surface text-muted-foreground shadow-sm lg:hidden"
        aria-label="Open navigation"
      >
        <MenuIcon className="size-4" />
      </button>

      <div className="hidden text-muted-foreground lg:block">
        {sidebarCollapsed ? <PanelLeftOpenIcon className="size-4" /> : <PanelLeftCloseIcon className="size-4" />}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <h1 className="truncate text-sm font-semibold text-foreground">{details.title}</h1>
          <span className="hidden rounded-full border border-success/30 bg-success/10 px-2 py-0.5 text-[10px] font-medium text-success sm:inline">
            Local workspace
          </span>
        </div>
        <p className="truncate text-[11px] text-muted-foreground">{details.description}</p>
      </div>

      <div className="hidden items-center gap-2 sm:flex">
        <div className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-xs text-muted-foreground shadow-sm">
          <SparklesIcon className="size-3.5 text-accent" />
          AI Lab workspace
        </div>
        <Link href="/tasks?create=1" className="flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-xs font-medium text-accent-foreground hover:bg-accent-hover">
          <PlusIcon className="size-3.5" />
          New task
        </Link>
      </div>
    </header>
  );
}
