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
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

async function parseProposal(response: Response): Promise<ChangeProposal> {
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

  return response.json() as Promise<ChangeProposal>;
}

export async function getChangeProposal(
  proposalId: string,
): Promise<ChangeProposal> {
  return parseProposal(
    await fetch(`${API_BASE_URL}/changes/${proposalId}`, {
      cache: "no-store",
    }),
  );
}

export async function approveChangeProposal(
  proposalId: string,
): Promise<ChangeProposal> {
  return parseProposal(
    await fetch(`${API_BASE_URL}/changes/${proposalId}/approve`, {
      method: "POST",
    }),
  );
}

export async function rejectChangeProposal(
  proposalId: string,
): Promise<ChangeProposal> {
  return parseProposal(
    await fetch(`${API_BASE_URL}/changes/${proposalId}/reject`, {
      method: "POST",
    }),
  );
}
