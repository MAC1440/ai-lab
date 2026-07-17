import type { VerificationRun } from "./verification-types";

export const VERIFICATION_FIX_REQUEST_EVENT =
  "ai-lab:verification-fix-request";

export type VerificationFixRequestDetail = {
  prompt: string;
  toolPolicy: "propose";
  freshContext: true;
  repairTaskId: string;
};

const MAX_FIX_OUTPUT_CHARS = 12_000;

function compactVerificationOutput(run: VerificationRun): string {
  const rawOutput = (run.output ?? run.output_excerpt).trim();
  const output = rawOutput || "No command output was captured.";

  if (output.length <= MAX_FIX_OUTPUT_CHARS) {
    return output;
  }

  const sectionLength = Math.floor(MAX_FIX_OUTPUT_CHARS / 2);
  return [
    output.slice(0, sectionLength),
    "\n... verification output shortened for model context ...\n",
    output.slice(-sectionLength),
  ].join("");
}

export function buildVerificationFixPrompt(run: VerificationRun): string {
  const output = compactVerificationOutput(run);
  const errorLine = run.error ? `Runner error: ${run.error}` : null;

  return [
    "Repair the failing workspace verification check below.",
    `Check: ${run.profile_name}`,
    `Command: ${run.display_command}`,
    `Exit code: ${run.exit_code ?? "unknown"}`,
    errorLine,
    "Read the exact files named in the traceback before searching broadly.",
    "Identify only the reported cause and call propose_file_change for each required fix.",
    "A chat-only explanation is not a completed repair. Do not discuss unrelated architecture.",
    "Do not claim the issue is fixed; the proposal still requires approval and another verification run.",
    "",
    "Verification output:",
    "```text",
    output,
    "```",
  ]
    .filter((line): line is string => line !== null)
    .join("\n");
}

export function requestAgentFix(
  run: VerificationRun,
  repairTaskId: string,
): void {
  const detail: VerificationFixRequestDetail = {
    prompt: buildVerificationFixPrompt(run),
    toolPolicy: "propose",
    freshContext: true,
    repairTaskId,
  };
  window.dispatchEvent(
    new CustomEvent<VerificationFixRequestDetail>(
      VERIFICATION_FIX_REQUEST_EVENT,
      { detail },
    ),
  );
}
