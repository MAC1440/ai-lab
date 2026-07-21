import assert from "node:assert/strict";
import test from "node:test";

import { getProjectTaskAction } from "./project-task-actions.mjs";

test("approval routes a task to verification", () => {
  assert.equal(getProjectTaskAction("ready_to_verify", false, false), "verify");
});

test("a failed verification routes a resumable task to repair", () => {
  assert.equal(getProjectTaskAction("needs_attention", true, true), "repair");
});

test("terminal tasks have no primary action", () => {
  assert.equal(getProjectTaskAction("completed", false, false), null);
  assert.equal(getProjectTaskAction("cancelled", false, false), null);
});
