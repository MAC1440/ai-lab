import type { ProjectTaskStatus } from "./project-task-types";

export function getProjectTaskAction(
  status: ProjectTaskStatus,
  phase: string,
  canResume: boolean,
  hasRepairTask: boolean,
): "review" | "verify" | "repair" | "start" | "continue" | "cancel" | null;
