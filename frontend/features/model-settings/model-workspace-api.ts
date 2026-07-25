const API_BASE_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL
  ?? process.env.NEXT_PUBLIC_API_BASE_URL
  ?? "http://127.0.0.1:8000";

export type StageScores = {
  planning: number;
  generation: number;
  repair: number;
};

export type ModelCapabilityProfile = {
  provider_id: string;
  model: string;
  context_window: number;
  safe_input_tokens: number | null;
  max_output_tokens: number;
  structured_output_mode: "native" | "tool" | "unsupported";
  supports_tools: boolean;
  supports_parallel_tools: boolean;
  stage_scores: StageScores;
  measured_tokens_per_second: number | null;
  estimated_characters_per_token: number;
  benchmarked_at: string | null;
  notes: string;
  updated_at?: string | null;
};

export type ModelAssignmentRecommendation = {
  provider_id: string;
  model: string;
  score: number;
  measured_tokens_per_second: number | null;
  benchmarked_at: string | null;
};

export type ModelRecommendations = {
  recommendations: {
    planning: ModelAssignmentRecommendation | null;
    generation: ModelAssignmentRecommendation | null;
    repair: ModelAssignmentRecommendation | null;
  };
  benchmarked_model_count: number;
  applied: false;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? `Request failed (${response.status})`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export function getModelCapabilities(): Promise<{
  profiles: ModelCapabilityProfile[];
}> {
  return request("/settings/model-capabilities");
}

export function getModelRecommendations(): Promise<ModelRecommendations> {
  return request("/model-benchmarks/recommendations");
}
