const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type RuntimeStageSettings = {
  num_ctx: number;
  max_tokens: number;
  temperature: number;
  reserve_tokens: number;
};

export type RuntimeSettings = {
  version: number;
  automatic: boolean;
  chat: RuntimeStageSettings;
  planning: RuntimeStageSettings;
  generation: RuntimeStageSettings;
  repair: RuntimeStageSettings;
};

export type HardwareSnapshot = {
  platform: {
    system: string;
    release: string;
    machine: string;
    processor: string;
  };
  cpu: { logical_cores: number };
  memory: {
    total_bytes: number;
    available_bytes: number;
    used_percent: number | null;
  };
  gpu: null | {
    name: string;
    memory_total_bytes: number;
    memory_free_bytes: number | null;
    utilization_percent: number | null;
    temperature_c: number | null;
  };
  recommendation: {
    quantization_assumption: string;
    fastest: ModelBand;
    balanced: ModelBand;
    maximum_practical: ModelBand;
    recommended_context_window: number;
    recommended_parallel_requests: number;
  };
  installed_models: {
    name: string;
    size_bytes: number | null;
    parameters_billion: number | null;
    tier:
      | "fastest"
      | "balanced"
      | "maximum_practical"
      | "not_recommended"
      | "unknown";
  }[];
  disclaimer: string;
};

type ModelBand = {
  max_parameters_billion: number;
  placement: string;
  expected: string;
};

export type RuntimeMetric = {
  recorded_at: string;
  agent_id: string;
  stage: string;
  provider_id: string;
  model: string;
  duration_seconds: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  tokens_per_second: number | null;
  context_window: number;
  max_tokens: number;
  safe_input_tokens: number;
  context_used_tokens: number;
  context_remaining_tokens: number;
  temperature: number;
  assignment_source: string | null;
};

export type RuntimeMetricsSnapshot = {
  latest: RuntimeMetric | null;
  history: RuntimeMetric[];
  summary: {
    run_count: number;
    average_tokens_per_second: number | null;
    average_duration_seconds: number | null;
  };
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
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
  return response.json() as Promise<T>;
}

export const getHardwareSnapshot = () =>
  api<HardwareSnapshot>("/runtime/hardware");

export const getRuntimeSettings = () =>
  api<RuntimeSettings>("/runtime/settings");

export const saveRuntimeSettings = (settings: RuntimeSettings) =>
  api<RuntimeSettings>("/runtime/settings", {
    method: "PUT",
    body: JSON.stringify(settings),
  });

export const autoConfigureRuntime = () =>
  api<RuntimeSettings>("/runtime/settings/auto", { method: "POST" });

export const getRuntimeMetrics = () =>
  api<RuntimeMetricsSnapshot>("/runtime/metrics");
