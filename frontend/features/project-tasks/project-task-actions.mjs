export function getProjectTaskAction(status, phase, canResume, hasRepairTask) {
  if (status === "running" || status === "verifying") return "cancel";
  if (status === "awaiting_approval") return "review";
  if (
    status === "ready_to_verify" ||
    (status === "paused" && phase === "verification_cancelled")
  ) {
    return "verify";
  }
  if (status === "needs_attention" && hasRepairTask && phase === "repairing") {
    return "repair";
  }
  if (!canResume) return null;
  return status === "queued" || status === "ready" ? "start" : "continue";
}
