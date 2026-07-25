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

const sectionDetails: Record<
  string,
  { title: string; description: string }
> = {
  "/": {
    title: "Agent Chat",
    description: "Inspect, reason, propose changes, and verify work.",
  },
  "/tasks": {
    title: "Project Tasks",
    description: "Run bounded coding work from planning through verification.",
  },
  "/changes": {
    title: "Changes",
    description: "Review task-linked change sets and proposed file operations.",
  },
  "/verification": {
    title: "Verification",
    description: "Inspect workspace checks, failures, and repair readiness.",
  },
  "/knowledge": {
    title: "Knowledge and Context",
    description: "Inspect indexed sources, project retrieval, and workspace context.",
  },
  "/models": {
    title: "Models and Runtime",
    description: "Manage local providers, assignments, limits, and hardware fit.",
  },
  "/performance": {
    title: "Performance",
    description: "Review persisted model speed, duration, and token usage.",
  },
};

export function AppHeader({
  sidebarCollapsed,
  onOpenMobileNavigation,
}: {
  sidebarCollapsed: boolean;
  onOpenMobileNavigation: () => void;
}) {
  const pathname = usePathname();
  const details = sectionDetails[pathname] ?? {
    title: "AI Lab",
    description: "Local agent workspace.",
  };

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-zinc-200 bg-zinc-100/85 px-4 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/85">
      <button
        type="button"
        onClick={onOpenMobileNavigation}
        className="flex size-9 items-center justify-center rounded-lg border border-zinc-200 bg-white text-zinc-600 shadow-sm lg:hidden dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300"
        aria-label="Open navigation"
      >
        <MenuIcon className="size-4" />
      </button>

      <div className="hidden text-zinc-400 lg:block">
        {sidebarCollapsed ? (
          <PanelLeftOpenIcon className="size-4" />
        ) : (
          <PanelLeftCloseIcon className="size-4" />
        )}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <h1 className="truncate text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            {details.title}
          </h1>
          <span className="hidden rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700 sm:inline dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-300">
            Local workspace
          </span>
        </div>
        <p className="truncate text-[11px] text-zinc-500 dark:text-zinc-400">
          {details.description}
        </p>
      </div>

      <div className="hidden items-center gap-2 sm:flex">
        <div className="flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs text-zinc-500 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
          <SparklesIcon className="size-3.5 text-emerald-500" />
          <span>AI Lab workspace</span>
        </div>

        <Link
          href="/tasks?create=1"
          className="flex items-center gap-2 rounded-lg bg-zinc-900 px-3 py-2 text-xs font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
        >
          <PlusIcon className="size-3.5" />
          New task
        </Link>
      </div>
    </header>
  );
}
