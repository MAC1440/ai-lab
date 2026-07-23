import assert from "node:assert/strict";
import test from "node:test";

import { getProjectTaskAction } from "./project-task-actions.mjs";

test("active and approval states expose lifecycle actions", () => {
  assert.equal(
    getProjectTaskAction("running", "generation_model", false, false),
    "cancel",
  );
  assert.equal(
    getProjectTaskAction("awaiting_approval", "review", false, false),
    "review",
  );
  assert.equal(
    getProjectTaskAction("ready_to_verify", "verification", false, false),
    "verify",
  );
});

test("failed verification and cancelled verification route correctly", () => {
  assert.equal(
    getProjectTaskAction("needs_attention", "repairing", true, true),
    "repair",
  );
  assert.equal(
    getProjectTaskAction(
      "paused",
      "verification_cancelled",
      true,
      false,
    ),
    "verify",
  );
});

test("queued and interrupted tasks start or continue", () => {
  assert.equal(
    getProjectTaskAction("queued", "planning", true, false),
    "start",
  );
  assert.equal(
    getProjectTaskAction("ready", "generation", true, false),
    "start",
  );
  assert.equal(
    getProjectTaskAction("paused", "interrupted", true, false),
    "continue",
  );
});

test("terminal tasks have no primary action", () => {
  assert.equal(
    getProjectTaskAction("completed", "completed", false, false),
    null,
  );
  assert.equal(
    getProjectTaskAction("cancelled", "cancelled", false, false),
    null,
  );
});
