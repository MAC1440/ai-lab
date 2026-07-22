const PROJECT_TASK_AGENT_IDS = new Set(["coding", "unity", "web"]);

export function resolveProjectTaskAgentId(value, fallback = "coding") {
  if (typeof value === "string" && PROJECT_TASK_AGENT_IDS.has(value)) {
    return value;
  }
  return PROJECT_TASK_AGENT_IDS.has(fallback) ? fallback : "coding";
}
