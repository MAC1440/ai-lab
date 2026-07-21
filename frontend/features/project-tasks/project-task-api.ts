import type {
  CreateProjectTaskRequest,
  ProjectTask,
} from "@/features/project-tasks/project-task-types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as
      | { detail?: unknown }
      | null;
    throw new Error(
      typeof body?.detail === "string"
        ? body.detail
        : `Project task request failed with status ${response.status}`,
    );
  }
  return response.json() as Promise<T>;
}

export async function listProjectTasks(limit = 50): Promise<ProjectTask[]> {
  const result = await parseJson<{ tasks: ProjectTask[] }>(
    await fetch(`${API_BASE_URL}/project-tasks?limit=${limit}`, {
      cache: "no-store",
    }),
  );
  return result.tasks;
}

export async function createProjectTask(
  request: CreateProjectTaskRequest,
): Promise<ProjectTask> {
  return parseJson<ProjectTask>(
    await fetch(`${API_BASE_URL}/project-tasks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    }),
  );
}

export async function resumeProjectTask(taskId: string): Promise<ProjectTask> {
  return parseJson<ProjectTask>(
    await fetch(
      `${API_BASE_URL}/project-tasks/${encodeURIComponent(taskId)}/resume`,
      { method: "POST" },
    ),
  );
}

export async function cancelProjectTask(taskId: string): Promise<ProjectTask> {
  return parseJson<ProjectTask>(
    await fetch(
      `${API_BASE_URL}/project-tasks/${encodeURIComponent(taskId)}/cancel`,
      { method: "POST" },
    ),
  );
}
