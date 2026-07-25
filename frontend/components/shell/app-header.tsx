"use client";

import {
  MenuIcon,
  PanelLeftCloseIcon,
  PanelLeftOpenIcon,
  PlusIcon,
  SparklesIcon,
} from "lucide-react";

export function AppHeader({
  sidebarCollapsed,
  onOpenMobileNavigation,
}: {
  sidebarCollapsed: boolean;
  onOpenMobileNavigation: () => void;
}) {
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
            Agent Chat
          </h1>
          <span className="hidden rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700 sm:inline dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-300">
            Local workspace
          </span>
        </div>
        <p className="truncate text-[11px] text-zinc-500 dark:text-zinc-400">
          Inspect, reason, propose changes, and verify work.
        </p>
      </div>

      <div className="hidden items-center gap-2 sm:flex">
        <div className="flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs text-zinc-500 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
          <SparklesIcon className="size-3.5 text-emerald-500" />
          <span>AI Lab workspace</span>
        </div>

        <button
          type="button"
          disabled
          title="New task workflow arrives in a later drop"
          className="flex cursor-not-allowed items-center gap-2 rounded-lg bg-zinc-900 px-3 py-2 text-xs font-medium text-white opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
        >
          <PlusIcon className="size-3.5" />
          New task
        </button>
      </div>
    </header>
  );
}
