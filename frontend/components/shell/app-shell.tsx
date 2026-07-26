"use client";

import { useState } from "react";

import { AppHeader } from "@/components/shell/app-header";
import { AppSidebar } from "@/components/shell/app-sidebar";
import { MobileNavigation } from "@/components/shell/mobile-navigation";
import { cn } from "@/lib/utils";

export function AppShell({
  children,
}: {
  children: React.ReactNode;
}) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);

  return (
    <div className="min-h-dvh bg-background">
      <div className="flex min-h-dvh">
        <AppSidebar
          collapsed={sidebarCollapsed}
          onCollapse={() => setSidebarCollapsed((value) => !value)}
        />

        <MobileNavigation
          open={mobileNavigationOpen}
          onClose={() => setMobileNavigationOpen(false)}
        />

        <div
          className={cn(
            "flex min-h-dvh min-w-0 flex-1 flex-col transition-[padding] duration-200",
            sidebarCollapsed ? "lg:pl-20" : "lg:pl-64",
          )}
        >
          <AppHeader
            sidebarCollapsed={sidebarCollapsed}
            onOpenMobileNavigation={() =>
              setMobileNavigationOpen(true)
            }
          />

          <main className="flex min-h-0 flex-1 flex-col px-0 pb-16 sm:px-3 sm:pb-3 lg:px-4">
            <div className="flex min-h-0 flex-1 overflow-hidden border-border bg-surface shadow-sm sm:rounded-2xl sm:border">
              {children}
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
