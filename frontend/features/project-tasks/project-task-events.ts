import type { ProjectTask } from "@/features/project-tasks/project-task-types";

export const PROJECT_TASK_RUN_EVENT = "ai-lab:project-task-run";

export type ProjectTaskRunDetail = {
  projectTaskId: string;
  prompt: string;
  recommendedAgentId: "coding" | "unity" | "web";
  repairTaskId: string | null;
  freshContext: true;
  toolPolicy: "propose";
};

export function requestProjectTaskRun(task: ProjectTask): void {
  const detail: ProjectTaskRunDetail = {
    projectTaskId: task.task_id,
    prompt: task.execution_prompt,
    recommendedAgentId: task.agent_id,
    repairTaskId: task.repair_task_id,
    freshContext: true,
    toolPolicy: "propose",
  };
  window.dispatchEvent(
    new CustomEvent<ProjectTaskRunDetail>(PROJECT_TASK_RUN_EVENT, { detail }),
  );
}
