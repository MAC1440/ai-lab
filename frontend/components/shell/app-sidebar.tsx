"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  CloudIcon,
  FlaskConicalIcon,
  HardDriveIcon,
} from "lucide-react";

import { DrawerManagementSection } from "@/components/shell/drawer-management-section";
import {
  isNavigationItemActive,
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
  const pathname = usePathname();

  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-30 hidden border-r border-border bg-surface/95 backdrop-blur transition-[width] duration-200 lg:flex lg:flex-col",
        collapsed ? "w-20" : "w-64",
      )}
    >
      <div
        className={cn(
          "flex h-16 items-center border-b border-border px-4",
          collapsed ? "justify-center" : "gap-3",
        )}
      >
        <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-accent text-accent-foreground shadow-sm">
          <FlaskConicalIcon className="size-5" />
        </div>

        {!collapsed ? (
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-foreground">
              AI Lab
            </p>
            <p className="truncate text-[11px] text-muted-foreground">
              Agent development workspace
            </p>
          </div>
        ) : null}
      </div>

      <div className="ai-lab-scrollbar flex-1 overflow-y-auto p-3">
        <NavigationGroup
          items={primaryNavigation}
          collapsed={collapsed}
          pathname={pathname}
        />

        <div className="my-3 border-t border-border" />

        <NavigationGroup
          items={secondaryNavigation}
          collapsed={collapsed}
          pathname={pathname}
        />

        <DrawerManagementSection
          collapsed={collapsed}
          onExpand={onCollapse}
        />
      </div>

      <div className="border-t border-border p-3">
        <div
          className={cn(
            "rounded-xl border border-border bg-surface-hover p-3",
            collapsed && "flex justify-center p-2",
          )}
        >
          <div className="flex items-center gap-2">
            <HardDriveIcon className="size-4 shrink-0 text-accent" />
            {!collapsed ? (
              <CloudIcon className="size-3.5 shrink-0 text-pending" />
            ) : null}
          </div>

          {!collapsed ? (
            <div className="mt-2">
              <p className="text-xs font-medium text-foreground">
                Local and cloud runtime
              </p>
              <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                Local models stay on this machine. Cloud providers receive
                prompts and context only when explicitly selected.
              </p>
            </div>
          ) : null}
        </div>

        <button
          type="button"
          onClick={onCollapse}
          className={cn(
            "mt-3 flex w-full cursor-pointer items-center rounded-lg px-3 py-2 text-xs font-medium text-muted-foreground transition hover:bg-surface-hover hover:text-foreground",
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
  pathname,
}: {
  items: NavigationItem[];
  collapsed: boolean;
  pathname: string;
}) {
  return (
    <nav className="space-y-1" aria-label="AI Lab sections">
      {items.map((item) => {
        const Icon = item.icon;
        const disabled = !item.available;
        const active = isNavigationItemActive(pathname, item);
        const content = (
          <>
            <Icon
              className={cn(
                "size-4 shrink-0",
                active && "text-accent",
              )}
            />

            {!collapsed ? (
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">
                  {item.label}
                </span>
                <span className="block truncate text-[10px] text-muted-foreground">
                  {item.description}
                </span>
              </span>
            ) : null}

            {!collapsed && disabled ? (
              <span className="rounded-full bg-surface-hover px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wide text-muted-foreground">
                Soon
              </span>
            ) : null}
          </>
        );

        const className = cn(
          "group flex w-full items-center rounded-xl px-3 py-2.5 text-left transition",
          collapsed ? "justify-center" : "gap-3",
          active
            ? "bg-accent/12 text-accent"
            : "text-muted-foreground hover:bg-surface-hover hover:text-foreground",
          disabled
            ? "cursor-not-allowed opacity-55"
            : "cursor-pointer",
        );

        if (disabled) {
          return (
            <button
              key={item.id}
              type="button"
              disabled
              title={
                collapsed
                  ? item.label
                  : `${item.label} — coming in a later drop`
              }
              className={className}
            >
              {content}
            </button>
          );
        }

        return (
          <Link
            key={item.id}
            href={item.href}
            title={collapsed ? item.label : item.description}
            className={className}
          >
            {content}
          </Link>
        );
      })}
    </nav>
  );
}
