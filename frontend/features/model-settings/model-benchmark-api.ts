import { streamNdjsonResponse } from "@/lib/ndjson-stream.mjs";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

export type BenchmarkStage = "planning" | "generation" | "repair";

export type BenchmarkStageResult = {
  stage: BenchmarkStage;
  status: "passed" | "failed" | "error";
  score: number;
  assertions: Array<{ name: string; passed: boolean }>;
  duration_ms: number;
  tokens_per_second: number | null;
  model?: string;
  provider_id?: string;
  error?: string;
};

export type ModelRecommendation = {
  provider_id: string;
  model: string;
  score: number;
  measured_tokens_per_second: number | null;
  benchmarked_at: string;
};

export type ModelRecommendations = {
  recommendations: Record<BenchmarkStage, ModelRecommendation | null>;
  benchmarked_model_count: number;
  applied: false;
};

export type ModelBenchmarkEvent = {
  type: string;
  benchmark_id?: string;
  stage?: BenchmarkStage;
  result?: BenchmarkStageResult;
  results?: BenchmarkStageResult[];
  recommendations?: ModelRecommendations;
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
        : `Model benchmark request failed with status ${response.status}`,
    );
  }
  return response.json() as Promise<T>;
}

export async function getModelRecommendations(): Promise<ModelRecommendations> {
  return parseJson<ModelRecommendations>(
    await fetch(`${API_BASE_URL}/model-benchmarks/recommendations`, {
      cache: "no-store",
    }),
  );
}

export async function* streamModelBenchmark(
  agentId: "coding" | "unity" | "web",
  signal?: AbortSignal,
): AsyncGenerator<ModelBenchmarkEvent, void, void> {
  const response = await fetch(`${API_BASE_URL}/model-benchmarks/run/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/x-ndjson",
    },
    body: JSON.stringify({ agent_id: agentId }),
    signal,
  });
  for await (const event of streamNdjsonResponse(
    response,
    "model benchmark stream",
  )) {
    const typed = event as ModelBenchmarkEvent;
    if (typed.type === "error") {
      throw new Error(typed.message || "The model benchmark failed.");
    }
    yield typed;
  }
}
