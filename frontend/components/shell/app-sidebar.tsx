"use client";

import {
  ChevronLeftIcon,
  ChevronRightIcon,
  CpuIcon,
  FlaskConicalIcon,
} from "lucide-react";

import {
  primaryNavigation,
  secondaryNavigation,
  type NavigationItem,
} from "@/components/shell/navigation-items";
import { cn } from "@/lib/utils";

export function AppSidebar({
  collapsed,
  onCollapse,
}: {
  collapsed: boolean;
  onCollapse: () => void;
}) {
  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-30 hidden border-r border-zinc-200 bg-white/95 backdrop-blur transition-[width] duration-200 lg:flex lg:flex-col dark:border-zinc-800 dark:bg-zinc-950/95",
        collapsed ? "w-20" : "w-64",
      )}
    >
      <div
        className={cn(
          "flex h-16 items-center border-b border-zinc-200 px-4 dark:border-zinc-800",
          collapsed ? "justify-center" : "gap-3",
        )}
      >
        <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-emerald-500 text-emerald-950 shadow-sm">
          <FlaskConicalIcon className="size-5" />
        </div>

        {!collapsed ? (
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              AI Lab
            </p>
            <p className="truncate text-[11px] text-zinc-500 dark:text-zinc-400">
              Local agent workspace
            </p>
          </div>
        ) : null}
      </div>

      <div className="ai-lab-scrollbar flex-1 overflow-y-auto p-3">
        <NavigationGroup
          items={primaryNavigation}
          collapsed={collapsed}
        />

        <div className="my-3 border-t border-zinc-200 dark:border-zinc-800" />

        <NavigationGroup
          items={secondaryNavigation}
          collapsed={collapsed}
        />
      </div>

      <div className="border-t border-zinc-200 p-3 dark:border-zinc-800">
        <div
          className={cn(
            "rounded-xl border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-900/70",
            collapsed && "flex justify-center p-2",
          )}
        >
          <CpuIcon className="size-4 shrink-0 text-emerald-500" />

          {!collapsed ? (
            <div className="mt-2">
              <p className="text-xs font-medium text-zinc-700 dark:text-zinc-200">
                Local-first runtime
              </p>
              <p className="mt-1 text-[11px] leading-relaxed text-zinc-500 dark:text-zinc-400">
                Models, files, and project context remain on this machine.
              </p>
            </div>
          ) : null}
        </div>

        <button
          type="button"
          onClick={onCollapse}
          className={cn(
            "mt-3 flex w-full items-center rounded-lg px-3 py-2 text-xs font-medium text-zinc-500 transition hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-900 dark:hover:text-zinc-100",
            collapsed ? "justify-center" : "justify-between",
          )}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {!collapsed ? <span>Collapse sidebar</span> : null}
          {collapsed ? (
            <ChevronRightIcon className="size-4" />
          ) : (
            <ChevronLeftIcon className="size-4" />
          )}
        </button>
      </div>
    </aside>
  );
}

function NavigationGroup({
  items,
  collapsed,
}: {
  items: NavigationItem[];
  collapsed: boolean;
}) {
  return (
    <nav className="space-y-1" aria-label="AI Lab sections">
      {items.map((item) => {
        const Icon = item.icon;
        const disabled = !item.available;

        return (
          <button
            key={item.id}
            type="button"
            disabled={disabled}
            title={
              collapsed
                ? item.label
                : disabled
                  ? `${item.label} — coming in a later drop`
                  : item.description
            }
            className={cn(
              "group flex w-full items-center rounded-xl px-3 py-2.5 text-left transition",
              collapsed ? "justify-center" : "gap-3",
              item.active
                ? "bg-emerald-500/12 text-emerald-700 dark:text-emerald-300"
                : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-950 dark:text-zinc-400 dark:hover:bg-zinc-900 dark:hover:text-zinc-100",
              disabled && "cursor-not-allowed opacity-55",
            )}
          >
            <Icon
              className={cn(
                "size-4 shrink-0",
                item.active && "text-emerald-500",
              )}
            />

            {!collapsed ? (
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">
                  {item.label}
                </span>
                <span className="block truncate text-[10px] text-zinc-400 dark:text-zinc-500">
                  {item.description}
                </span>
              </span>
            ) : null}

            {!collapsed && disabled ? (
              <span className="rounded-full bg-zinc-100 px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wide text-zinc-400 dark:bg-zinc-800">
                Soon
              </span>
            ) : null}
          </button>
        );
      })}
    </nav>
  );
}
