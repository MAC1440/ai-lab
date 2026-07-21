export function getProjectTaskAction(status, canResume, hasRepairTask) {
  if (status === "ready_to_verify") return "verify";
  if (!canResume) return null;
  if (hasRepairTask) return "repair";
  return status === "queued" ? "start" : "continue";
}
