import type { Metadata } from "next";

import { PerformanceDashboard } from "@/features/runtime/performance-dashboard";

export const metadata: Metadata = {
  title: "Performance",
};

export default function PerformancePage() {
  return <PerformanceDashboard />;
}
