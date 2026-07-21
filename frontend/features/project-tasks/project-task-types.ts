import type { ChangeProposal } from "@/features/changes/change-api";

export type ProjectTaskStatus =
  | "queued"
  | "running"
  | "awaiting_approval"
  | "ready_to_verify"
  | "verifying"
  | "paused"
  | "needs_attention"
  | "completed"
  | "cancelled";

export type ProjectTaskEvent = {
  event_id: string;
  task_id: string;
  event_type: string;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type ProjectTask = {
  task_id: string;
  workspace: string;
  title: string;
  goal: string;
  agent_id: "coding" | "unity" | "web";
  status: ProjectTaskStatus;
  phase: string;
  verification_profile_id: string | null;
  current_change_set_id: string | null;
  current_agent_run_id: string | null;
  latest_verification_run_id: string | null;
  repair_task_id: string | null;
  attempt_count: number;
  max_attempts: number;
  last_error: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  cancelled_at: string | null;
  proposals: ChangeProposal[];
  proposal_count: number;
  events: ProjectTaskEvent[];
  can_resume: boolean;
  execution_prompt: string;
};

export type CreateProjectTaskRequest = {
  title: string;
  goal: string;
  agent_id: "coding" | "unity" | "web";
  verification_profile_id?: string | null;
  max_attempts?: number;
};
