const API_BASE_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

export type ProviderKind = "ollama" | "openai_compatible";
export type ModelAvailability = "local" | "cloud" | "remote";

export type ModelProvider = {
  id: string;
  name: string;
  kind: ProviderKind;
  base_url: string;
  built_in: boolean;
  api_key_configured: boolean;
  is_cloud?: boolean;
  supports_pull?: boolean;
};

export type GenerationSettings = {
  temperature: number;
  max_tokens: number;
  context_window: number;
};

export type AgentModelSettings = {
  provider_id: string;
  model: string;
  generation: GenerationSettings;
  provider: ModelProvider;
  assignment_source?: string;
};

export type TaskStage = "planning" | "generation" | "repair";

export type ModelSettingsSnapshot = {
  providers: ModelProvider[];
  agents: Record<string, AgentModelSettings>;
  task_stages: Record<
    string,
    Partial<Record<TaskStage, AgentModelSettings>>
  >;
};

export type DiscoveredModel = {
  name: string;
  size: number | null;
  modified_at: string | null;
  warnings: string[];
  digest?: string | null;
  details?: {
    format?: string;
    family?: string;
    parameter_size?: string;
    quantization_level?: string;
  };
  availability?: ModelAvailability;
  ready?: boolean;
  pull_name?: string | null;
};

export type PullProgressEvent = {
  type: "progress" | "done" | "error";
  provider_id: string;
  model: string;
  status: string;
  digest?: string | null;
  total: number | null;
  completed: number | null;
  percent: number | null;
  error?: string;
};

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null;
    throw new Error(
      body?.detail || `Request failed (${response.status})`,
    );
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function getModelSettings(): Promise<ModelSettingsSnapshot> {
  return request("/settings/models");
}

export function saveProvider(
  id: string,
  value: {
    name: string;
    kind: ProviderKind;
    base_url: string;
    api_key?: string | null;
  },
): Promise<ModelProvider> {
  return request(`/settings/providers/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify(value),
  });
}

export function deleteProvider(id: string): Promise<void> {
  return request(`/settings/providers/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export function discoverModels(id: string): Promise<{
  provider: ModelProvider;
  models: DiscoveredModel[];
}> {
  return request(
    `/settings/providers/${encodeURIComponent(id)}/models`,
  );
}

export function testProvider(id: string): Promise<{
  ok: boolean;
  message: string;
  models: DiscoveredModel[];
}> {
  return request(`/settings/providers/${encodeURIComponent(id)}/test`, {
    method: "POST",
  });
}

export async function pullOllamaModel(
  providerId: string,
  model: string,
  onEvent: (event: PullProgressEvent) => void,
  signal?: AbortSignal,
): Promise<PullProgressEvent> {
  const response = await fetch(
    `${API_BASE_URL}/settings/providers/${encodeURIComponent(
      providerId,
    )}/models/pull`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/x-ndjson",
      },
      body: JSON.stringify({
        model,
        insecure: false,
      }),
      cache: "no-store",
      signal,
    },
  );

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null;
    throw new Error(
      body?.detail || `Model pull failed (${response.status})`,
    );
  }

  if (!response.body) {
    throw new Error("The backend returned no pull progress stream.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let terminalEvent: PullProgressEvent | null = null;

  const consumeLine = (line: string) => {
    const clean = line.trim();
    if (!clean) return;

    let event: PullProgressEvent;
    try {
      event = JSON.parse(clean) as PullProgressEvent;
    } catch {
      throw new Error("The backend returned malformed pull progress.");
    }

    onEvent(event);
    if (event.type === "error") {
      throw new Error(event.error || event.status || "Model pull failed.");
    }
    if (event.type === "done") {
      terminalEvent = event;
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });

    let newlineIndex = buffer.indexOf("\n");
    while (newlineIndex >= 0) {
      const line = buffer.slice(0, newlineIndex);
      buffer = buffer.slice(newlineIndex + 1);
      consumeLine(line);
      newlineIndex = buffer.indexOf("\n");
    }

    if (done) break;
  }

  if (buffer.trim()) consumeLine(buffer);

  if (!terminalEvent) {
    throw new Error(
      "The model pull ended without a success confirmation.",
    );
  }

  return terminalEvent;
}

export function saveAgentModel(
  agentId: string,
  value: Omit<AgentModelSettings, "provider">,
): Promise<AgentModelSettings> {
  return request(`/settings/agents/${encodeURIComponent(agentId)}`, {
    method: "PUT",
    body: JSON.stringify(value),
  });
}

export function saveTaskStageModel(
  agentId: string,
  stage: TaskStage,
  value: Omit<
    AgentModelSettings,
    "provider" | "assignment_source"
  >,
): Promise<AgentModelSettings> {
  return request(
    `/settings/agents/${encodeURIComponent(
      agentId,
    )}/stages/${stage}`,
    {
      method: "PUT",
      body: JSON.stringify(value),
    },
  );
}

export function deleteTaskStageModel(
  agentId: string,
  stage: TaskStage,
): Promise<void> {
  return request(
    `/settings/agents/${encodeURIComponent(
      agentId,
    )}/stages/${stage}`,
    { method: "DELETE" },
  );
}
