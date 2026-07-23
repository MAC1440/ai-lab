import assert from "node:assert/strict";
import test from "node:test";

import {
  initialReliabilityState,
  reduceReliabilityEvent,
} from "./reliability-benchmark-state.mjs";

test("reliability event reducer tracks progress and terminal run", () => {
  const started = reduceReliabilityEvent(initialReliabilityState, {
    type: "reliability_started",
    run_id: "run-1",
    scenario_count: 3,
  });
  const active = reduceReliabilityEvent(started, {
    type: "scenario_started",
    scenario: { scenario_id: "python", name: "Python" },
  });
  const completed = reduceReliabilityEvent(active, {
    type: "scenario_done",
    result: {
      scenario_id: "python",
      repetition: 1,
      status: "passed",
    },
  });
  const done = reduceReliabilityEvent(completed, {
    type: "reliability_done",
    run: { run_id: "run-1", status: "passed" },
  });

  assert.equal(started.scenarioCount, 3);
  assert.equal(active.currentScenario.name, "Python");
  assert.equal(completed.completedCount, 1);
  assert.equal(completed.results.length, 1);
  assert.equal(done.currentScenario, null);
  assert.equal(done.run.status, "passed");
});

test("reliability event reducer replaces duplicate scenario repetitions", () => {
  const first = reduceReliabilityEvent(initialReliabilityState, {
    type: "scenario_done",
    result: {
      scenario_id: "python",
      repetition: 1,
      status: "failed",
    },
  });
  const retried = reduceReliabilityEvent(first, {
    type: "scenario_done",
    result: {
      scenario_id: "python",
      repetition: 1,
      status: "passed",
    },
  });

  assert.equal(retried.results.length, 1);
  assert.equal(retried.results[0].status, "passed");
});
