import type { VerificationRun } from "./verification-types";


export const VERIFICATION_FIX_REQUEST_EVENT =
  "ai-lab:verification-fix-request";

export type VerificationFixRequestDetail = {
  prompt: string;
};

export function buildVerificationFixPrompt(run: VerificationRun): string {
  const output = run.output_excerpt.trim() || "No command output was captured.";

  return [
    `The workspace verification check \"${run.profile_name}\" failed.`,
    `Command: ${run.display_command}`,
    `Exit code: ${run.exit_code ?? "unknown"}`,
    "Inspect the relevant files, identify the cause, and propose a reviewable file change.",
    "Do not claim the issue is fixed until you have used the file-change tool.",
    "",
    "Verification output:",
    "```text",
    output,
    "```",
  ].join("\n");
}

export function requestAgentFix(run: VerificationRun): void {
  const detail: VerificationFixRequestDetail = {
    prompt: buildVerificationFixPrompt(run),
  };
  window.dispatchEvent(
    new CustomEvent<VerificationFixRequestDetail>(
      VERIFICATION_FIX_REQUEST_EVENT,
      { detail },
    ),
  );
}
