import type { ChangeProposal } from "@/features/changes/change-api";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

export type ScaffoldDefinition = {
  scaffold_id: string;
  name: string;
  description: string;
  project_type: string;
  source: string;
  requires_network: boolean;
  default_directory: string;
  available: boolean;
  unavailable_reason: string | null;
};

export type ScaffoldResult = {
  scaffold_id: string;
  name: string;
  target_directory: string;
  change_set_id: string;
  proposal_count: number;
  proposals: ChangeProposal[];
  generator_output: string;
  requires_approval: true;
};

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as
      | { detail?: unknown }
      | null;
    throw new Error(
      typeof body?.detail === "string"
        ? body.detail
        : `Scaffold request failed with status ${response.status}`,
    );
  }
  return response.json() as Promise<T>;
}

export async function listScaffolds(): Promise<ScaffoldDefinition[]> {
  const result = await parseJson<{ scaffolds: ScaffoldDefinition[] }>(
    await fetch(`${API_BASE_URL}/scaffolds`, { cache: "no-store" }),
  );
  return result.scaffolds;
}

export async function createScaffold(input: {
  scaffoldId: string;
  targetDirectory: string;
  projectName: string;
}): Promise<ScaffoldResult> {
  return parseJson<ScaffoldResult>(
    await fetch(`${API_BASE_URL}/scaffolds`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scaffold_id: input.scaffoldId,
        target_directory: input.targetDirectory,
        project_name: input.projectName,
      }),
    }),
  );
}
