import type {
  ReliabilityBenchmarkEvent,
  ReliabilityBenchmarkRun,
  ReliabilityScenario,
  ReliabilityScenarioResult,
} from "./reliability-benchmark-api";

export type ReliabilityBenchmarkState = {
  runId: string | null;
  currentScenario: ReliabilityScenario | null;
  completedCount: number;
  scenarioCount: number;
  results: ReliabilityScenarioResult[];
  run: ReliabilityBenchmarkRun | null;
};

export const initialReliabilityState: ReliabilityBenchmarkState;

export function reduceReliabilityEvent(
  state: ReliabilityBenchmarkState,
  event: ReliabilityBenchmarkEvent,
): ReliabilityBenchmarkState;
