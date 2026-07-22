import assert from "node:assert/strict";
import test from "node:test";

import { resolveProjectTaskAgentId } from "./project-task-agent.mjs";

test("uses the workspace recommendation for a recognized task agent", () => {
  assert.equal(resolveProjectTaskAgentId("web"), "web");
  assert.equal(resolveProjectTaskAgentId("unity"), "unity");
});

test("falls back to coding instead of silently selecting Unity", () => {
  assert.equal(resolveProjectTaskAgentId("general"), "coding");
  assert.equal(resolveProjectTaskAgentId(undefined), "coding");
});
