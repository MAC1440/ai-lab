import type { ChangeProposal } from "@/features/changes/change-api";

export type RepairTaskStatus =
  | "open"
  | "awaiting_review"
  | "ready_to_verify"
  | "failed"
  | "passed"
  | "dismissed";

export type RepairTask = {
  task_id: string;
  workspace: string;
  title: string;
  status: RepairTaskStatus;
  source_run_id: string;
  latest_run_id: string | null;
  profile_id: string;
  profile_name: string;
  display_command: string;
  failure_excerpt: string;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  proposal_count: number;
  proposals: ChangeProposal[];
};
