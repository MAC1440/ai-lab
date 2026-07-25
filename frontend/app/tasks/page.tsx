import type { Metadata } from "next";

import { ProjectTasksWorkspace } from "@/features/project-tasks/project-tasks-workspace";

export const metadata: Metadata = {
  title: "Project Tasks",
};

export default function TasksPage() {
  return <ProjectTasksWorkspace />;
}
