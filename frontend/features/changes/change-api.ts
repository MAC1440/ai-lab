export type ChangeProposalStatus = "pending" | "approved" | "rejected";

export type ChangeProposal = {
  proposal_id: string;
  workspace: string;
  file_path: string;
  summary: string;
  status: ChangeProposalStatus;
  operation: "create" | "update";
  diff: string;
  created_at: string;
  resolved_at: string | null;
  change_set_id: string | null;
  repair_task_id: string | null;
};

type ChangeProposalListResponse = {
  proposals: ChangeProposal[];
};

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
        : `Change request failed with status ${response.status}`,
    );
  }

  return response.json() as Promise<T>;
}

export async function listChangeProposals(
  status?: ChangeProposalStatus,
  filters?: { changeSetId?: string; repairTaskId?: string },
): Promise<ChangeProposal[]> {
  const params = new URLSearchParams();
  if (status) {
    params.set("status", status);
  }
  if (filters?.changeSetId) {
    params.set("change_set_id", filters.changeSetId);
  }
  if (filters?.repairTaskId) {
    params.set("repair_task_id", filters.repairTaskId);
  }

  const query = params.toString();
  const response = await fetch(
    `${API_BASE_URL}/changes${query ? `?${query}` : ""}`,
    { cache: "no-store" },
  );
  const result = await parseJson<ChangeProposalListResponse>(response);
  return result.proposals;
}

async function resolveChangeSet(
  changeSetId: string,
  action: "approve" | "reject",
): Promise<ChangeProposal[]> {
  const result = await parseJson<ChangeProposalListResponse>(
    await fetch(`${API_BASE_URL}/changes/sets/${changeSetId}/${action}`, {
      method: "POST",
    }),
  );
  return result.proposals;
}

export function approveChangeSet(changeSetId: string) {
  return resolveChangeSet(changeSetId, "approve");
}

export function rejectChangeSet(changeSetId: string) {
  return resolveChangeSet(changeSetId, "reject");
}

export async function getChangeProposal(
  proposalId: string,
): Promise<ChangeProposal> {
  return parseJson<ChangeProposal>(
    await fetch(`${API_BASE_URL}/changes/${proposalId}`, {
      cache: "no-store",
    }),
  );
}

export async function approveChangeProposal(
  proposalId: string,
): Promise<ChangeProposal> {
  return parseJson<ChangeProposal>(
    await fetch(`${API_BASE_URL}/changes/${proposalId}/approve`, {
      method: "POST",
    }),
  );
}

export async function rejectChangeProposal(
  proposalId: string,
): Promise<ChangeProposal> {
  return parseJson<ChangeProposal>(
    await fetch(`${API_BASE_URL}/changes/${proposalId}/reject`, {
      method: "POST",
    }),
  );
}
