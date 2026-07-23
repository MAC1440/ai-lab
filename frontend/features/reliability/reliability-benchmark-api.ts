import { streamNdjsonResponse } from "@/lib/ndjson-stream.mjs";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

export type ReliabilitySuite = "quick" | "full";
export type ReliabilityAgentOverride =
  | "assigned"
  | "coding"
  | "unity"
  | "web";

export type ReliabilityScenario = {
  scenario_id: string;
  name: string;
  description: string;
  category: "workflow" | "safety";
  project_type: "python" | "nextjs" | "unity" | "platform";
  agent_id: "coding" | "unity" | "web" | null;
  suites: ReliabilitySuite[];
  model_calls: number;
};

export type ReliabilityAssertion = {
  name: string;
  passed: boolean;
  detail: string;
};

export type ReliabilityScenarioResult = {
  sequence?: number;
  scenario_id: string;
  repetition: number;
  category: "workflow" | "safety";
  project_type: string;
  agent_id: string | null;
  status: "passed" | "failed" | "error";
  duration_ms: number;
  score: number;
  assertions: ReliabilityAssertion[];
  metrics: {
    model_calls?: number;
    models?: string[];
    usage?: Record<string, number>;
    verification_kind?: string;
    fault?: string;
  };
  error: string | null;
  created_at: string;
};

export type ReliabilityBenchmarkRun = {
  run_id: string;
  suite: ReliabilitySuite;
  agent_override: string | null;
  repetitions: number;
  status: "running" | "passed" | "failed" | "interrupted" | "error";
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  scenario_count: number;
  passed_count: number;
  failed_count: number;
  pass_rate: number;
  error: string | null;
  results?: ReliabilityScenarioResult[];
};

export type ReliabilityBenchmarkEvent = {
  type: string;
  run_id?: string;
  scenario_count?: number;
  sequence?: number;
  scenario?: ReliabilityScenario;
  result?: ReliabilityScenarioResult;
  run?: ReliabilityBenchmarkRun;
  message?: string;
  [key: string]: unknown;
};

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as
      | { detail?: unknown }
      | null;
    throw new Error(
      typeof body?.detail === "string"
        ? body.detail
        : `Reliability request failed with status ${response.status}`,
    );
  }
  return response.json() as Promise<T>;
}

export async function listReliabilityScenarios(): Promise<
  ReliabilityScenario[]
> {
  const response = await parseJson<{ scenarios: ReliabilityScenario[] }>(
    await fetch(`${API_BASE_URL}/reliability-benchmarks/scenarios`, {
      cache: "no-store",
    }),
  );
  return response.scenarios;
}

export async function listReliabilityRuns(): Promise<ReliabilityBenchmarkRun[]> {
  const response = await parseJson<{ runs: ReliabilityBenchmarkRun[] }>(
    await fetch(`${API_BASE_URL}/reliability-benchmarks/runs?limit=10`, {
      cache: "no-store",
    }),
  );
  return response.runs;
}

export async function getReliabilityRun(
  runId: string,
): Promise<ReliabilityBenchmarkRun> {
  return parseJson<ReliabilityBenchmarkRun>(
    await fetch(`${API_BASE_URL}/reliability-benchmarks/runs/${runId}`, {
      cache: "no-store",
    }),
  );
}

export async function* streamReliabilityBenchmark(
  request: {
    suite: ReliabilitySuite;
    repetitions: number;
    agent_override: ReliabilityAgentOverride;
  },
  signal?: AbortSignal,
): AsyncGenerator<ReliabilityBenchmarkEvent, void, void> {
  const response = await fetch(`${API_BASE_URL}/reliability-benchmarks/run/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/x-ndjson",
    },
    body: JSON.stringify(request),
    signal,
  });
  for await (const event of streamNdjsonResponse(
    response,
    "reliability benchmark stream",
  )) {
    const typed = event as ReliabilityBenchmarkEvent;
    if (typed.type === "error") {
      throw new Error(typed.message || "The reliability benchmark failed.");
    }
    yield typed;
  }
}
