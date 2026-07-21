export type VerificationStatus =
  | "running"
  | "passed"
  | "failed"
  | "cancelled"
  | "timed_out"
  | "error";

export type DetectedProject = {
  type: "python" | "node" | "dotnet" | "unity" | string;
  name: string;
  root: string;
  markers: string[];
  version?: string;
  warning?: string;
};

export type VerificationProfile = {
  profile_id: string;
  name: string;
  description: string;
  project_type: string;
  working_directory: string;
  command: string;
  timeout_seconds: number;
  available: boolean;
  unavailable_reason: string | null;
  result_format?: string | null;
};

export type VerificationOverview = {
  workspace: string;
  projects: DetectedProject[];
  profiles: VerificationProfile[];
};

export type VerificationRun = {
  run_id: string;
  workspace: string;
  profile_id: string;
  profile_name: string;
  project_type: string;
  working_directory: string;
  command: string[];
  display_command: string;
  proposal_id: string | null;
  status: VerificationStatus;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  exit_code: number | null;
  output_excerpt: string;
  output?: string;
  output_truncated: boolean;
  error: string | null;
};

export type VerificationStartedEvent = {
  type: "verification_started";
  run_id: string;
  workspace: string;
  profile: VerificationProfile;
  proposal_id: string | null;
  started_at: string;
};

export type VerificationCommandStartedEvent = {
  type: "command_started";
  run_id: string;
  command: string;
  working_directory: string;
};

export type VerificationOutputEvent = {
  type: "output";
  run_id: string;
  stream: "stdout" | "stderr";
  content: string;
};

export type VerificationCommandFinishedEvent = {
  type: "command_finished";
  run_id: string;
  exit_code: number | null;
  duration_ms: number;
};

export type VerificationDoneEvent = {
  type: "verification_done";
  result: VerificationRun;
};

export type VerificationErrorEvent = {
  type: "error";
  message: string;
  status_code?: number;
};

export type VerificationStreamEvent =
  | VerificationStartedEvent
  | VerificationCommandStartedEvent
  | VerificationOutputEvent
  | VerificationCommandFinishedEvent
  | VerificationDoneEvent
  | VerificationErrorEvent;

export type StartVerificationRequest = {
  profile_id: string;
  proposal_id?: string | null;
  repair_task_id?: string | null;
  project_task_id?: string | null;
};
