import type { ChangeProposal } from "@/features/changes/change-api";

export type ProjectTaskStatus =
  | "queued"
  | "ready"
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

export type ProjectTaskArtifact = {
  artifact_id: string;
  task_id: string;
  artifact_type: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type ImplementationPlanFile = {
  path: string;
  operation: "create" | "update" | "delete" | "move";
  reason: string;
  destination_path: string | null;
  required_context: boolean;
};

export type ImplementationPlan = {
  summary: string;
  files: ImplementationPlanFile[];
  verification: string[];
  risks: string[];
};

export type ProjectTaskStreamEvent = {
  type: string;
  run_id?: string;
  stage?: string;
  message?: string;
  status_code?: number;
  code?: string;
  model?: string;
  task?: ProjectTask;
  plan?: ImplementationPlan;
  context?: {
    file_count?: number;
    bytes?: number;
    complete?: boolean;
    files?: Array<{ path?: string; sha256?: string; bytes?: number }>;
    omitted?: string[];
  };
  validation?: {
    valid?: boolean;
    checked_files?: number;
    diagnostics?: Array<{
      path?: string;
      severity?: string;
      message?: string;
      line?: number;
    }>;
  };
  proposals?: ChangeProposal[];
  proposal_count?: number;
  change_set_id?: string;
  content?: string;
  result?: {
    status?: string;
    output?: string;
    output_excerpt?: string;
    error?: string | null;
    exit_code?: number | null;
  };
  repair_task?: Record<string, unknown>;
  [key: string]: unknown;
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
  artifacts: ProjectTaskArtifact[];
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
