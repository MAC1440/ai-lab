"use client";

import {
  FlaskConicalIcon,
  XIcon,
} from "lucide-react";

import {
  primaryNavigation,
  secondaryNavigation,
  type NavigationItem,
} from "@/components/shell/navigation-items";
import { cn } from "@/lib/utils";

export function MobileNavigation({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  return (
    <div
      className={cn(
        "fixed inset-0 z-50 lg:hidden",
        open ? "pointer-events-auto" : "pointer-events-none",
      )}
      aria-hidden={!open}
    >
      <button
        type="button"
        onClick={onClose}
        className={cn(
          "absolute inset-0 bg-zinc-950/50 backdrop-blur-sm transition-opacity",
          open ? "opacity-100" : "opacity-0",
        )}
        aria-label="Close navigation"
      />

      <aside
        className={cn(
          "absolute inset-y-0 left-0 flex w-[min(86vw,20rem)] flex-col border-r border-zinc-200 bg-white shadow-2xl transition-transform dark:border-zinc-800 dark:bg-zinc-950",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-16 items-center gap-3 border-b border-zinc-200 px-4 dark:border-zinc-800">
          <div className="flex size-9 items-center justify-center rounded-xl bg-emerald-500 text-emerald-950">
            <FlaskConicalIcon className="size-5" />
          </div>

          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold">AI Lab</p>
            <p className="text-[11px] text-zinc-500">
              Local agent workspace
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="flex size-9 items-center justify-center rounded-lg text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-900"
            aria-label="Close navigation"
          >
            <XIcon className="size-4" />
          </button>
        </div>

        <div className="ai-lab-scrollbar flex-1 overflow-y-auto p-3">
          <MobileNavigationGroup
            items={primaryNavigation}
            onSelect={onClose}
          />

          <div className="my-3 border-t border-zinc-200 dark:border-zinc-800" />

          <MobileNavigationGroup
            items={secondaryNavigation}
            onSelect={onClose}
          />
        </div>
      </aside>
    </div>
  );
}

function MobileNavigationGroup({
  items,
  onSelect,
}: {
  items: NavigationItem[];
  onSelect: () => void;
}) {
  return (
    <nav className="space-y-1">
      {items.map((item) => {
        const Icon = item.icon;
        const disabled = !item.available;

        return (
          <button
            key={item.id}
            type="button"
            disabled={disabled}
            onClick={onSelect}
            className={cn(
              "flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left",
              item.active
                ? "bg-emerald-500/12 text-emerald-700 dark:text-emerald-300"
                : "text-zinc-600 dark:text-zinc-400",
              disabled && "cursor-not-allowed opacity-50",
            )}
          >
            <Icon className="size-4 shrink-0" />
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-medium">
                {item.label}
              </span>
              <span className="block truncate text-[10px] text-zinc-400">
                {item.description}
              </span>
            </span>
            {disabled ? (
              <span className="text-[9px] font-medium uppercase text-zinc-400">
                Soon
              </span>
            ) : null}
          </button>
        );
      })}
    </nav>
  );
}
