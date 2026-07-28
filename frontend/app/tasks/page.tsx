import type { Metadata } from "next";
import { Suspense } from "react";

import { ProjectTasksWorkspace } from "@/features/project-tasks/project-tasks-workspace";

export const metadata: Metadata = {
  title: "Project Tasks",
};

export default function TasksPage() {
  return (
    <Suspense fallback={<TasksWorkspaceFallback />}>
      <ProjectTasksWorkspace />
    </Suspense>
  );
}

function TasksWorkspaceFallback() {
  return (
    <div className="flex flex-1 items-center justify-center p-6 text-sm text-muted-foreground">
      Loading project tasks…
    </div>
  );
}
