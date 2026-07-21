import type { ProjectTaskStatus } from "./project-task-types";

export function getProjectTaskAction(
  status: ProjectTaskStatus,
  canResume: boolean,
  hasRepairTask: boolean,
): "verify" | "repair" | "start" | "continue" | null;
