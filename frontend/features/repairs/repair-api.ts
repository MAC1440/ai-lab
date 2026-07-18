import type { RepairTask } from "@/features/repairs/repair-types";

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
        : `Repair request failed with status ${response.status}`,
    );
  }
  return response.json() as Promise<T>;
}

export async function listRepairTasks(): Promise<RepairTask[]> {
  const result = await parseJson<{ tasks: RepairTask[] }>(
    await fetch(`${API_BASE_URL}/repairs`, { cache: "no-store" }),
  );
  return result.tasks;
}

export async function createRepairTask(verificationRunId: string) {
  return parseJson<RepairTask>(
    await fetch(`${API_BASE_URL}/repairs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ verification_run_id: verificationRunId }),
    }),
  );
}

export async function dismissRepairTask(taskId: string) {
  return parseJson<RepairTask>(
    await fetch(`${API_BASE_URL}/repairs/${taskId}/dismiss`, { method: "POST" }),
  );
}

export async function reopenRepairTask(taskId: string) {
  return parseJson<RepairTask>(
    await fetch(`${API_BASE_URL}/repairs/${taskId}/reopen`, { method: "POST" }),
  );
}

export async function startRepairAttempt(taskId: string) {
  return parseJson<RepairTask>(
    await fetch(`${API_BASE_URL}/repairs/${taskId}/attempts`, {
      method: "POST",
    }),
  );
}
