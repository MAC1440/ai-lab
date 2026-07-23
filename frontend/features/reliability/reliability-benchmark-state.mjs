export const initialReliabilityState = Object.freeze({
  runId: null,
  currentScenario: null,
  completedCount: 0,
  scenarioCount: 0,
  results: [],
  run: null,
});

export function reduceReliabilityEvent(state, event) {
  if (!event || typeof event !== "object") return state;
  if (event.type === "reliability_started") {
    return {
      ...initialReliabilityState,
      runId: event.run_id ?? null,
      scenarioCount: Number(event.scenario_count ?? 0),
    };
  }
  if (event.type === "scenario_started") {
    return {
      ...state,
      currentScenario: event.scenario ?? null,
    };
  }
  if (event.type === "scenario_done" && event.result) {
    return {
      ...state,
      currentScenario: null,
      completedCount: state.completedCount + 1,
      results: [
        ...state.results.filter(
          (item) =>
            !(
              item.scenario_id === event.result.scenario_id &&
              item.repetition === event.result.repetition
            ),
        ),
        event.result,
      ],
    };
  }
  if (event.type === "reliability_done" && event.run) {
    return {
      ...state,
      currentScenario: null,
      run: event.run,
      results: event.run.results ?? state.results,
    };
  }
  return state;
}
