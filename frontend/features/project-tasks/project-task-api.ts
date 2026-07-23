import type {
  CreateProjectTaskRequest,
  ProjectTask,
  ProjectTaskStreamEvent,
} from "@/features/project-tasks/project-task-types";
import { streamNdjsonResponse } from "@/lib/ndjson-stream.mjs";

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

export async function getProjectTask(taskId: string): Promise<ProjectTask> {
  return parseJson<ProjectTask>(
    await fetch(
      `${API_BASE_URL}/project-tasks/${encodeURIComponent(taskId)}`,
      { cache: "no-store" },
    ),
  );
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

async function* streamTaskEndpoint(
  path: string,
  body: Record<string, unknown> | null,
  signal?: AbortSignal,
): AsyncGenerator<ProjectTaskStreamEvent, void, void> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      Accept: "application/x-ndjson",
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
    signal,
  });
  for await (const event of streamNdjsonResponse(
    response,
    "project task stream",
  )) {
    const typed = event as ProjectTaskStreamEvent;
    if (typed.type === "error") {
      throw new Error(typed.message || "The project task failed.");
    }
    yield typed;
  }
}

export function streamProjectTask(
  taskId: string,
  runId: string,
  signal?: AbortSignal,
) {
  return streamTaskEndpoint(
    `/project-tasks/${encodeURIComponent(taskId)}/run/stream`,
    { run_id: runId },
    signal,
  );
}

export function streamProjectTaskRepair(
  taskId: string,
  runId: string,
  signal?: AbortSignal,
) {
  return streamTaskEndpoint(
    `/project-tasks/${encodeURIComponent(taskId)}/repair/stream`,
    { run_id: runId },
    signal,
  );
}

export function streamProjectTaskApprovalAndVerification(
  taskId: string,
  signal?: AbortSignal,
) {
  return streamTaskEndpoint(
    `/project-tasks/${encodeURIComponent(taskId)}/approve-and-verify/stream`,
    null,
    signal,
  );
}
