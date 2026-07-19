const API_BASE_URL =
    process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

export type ProviderKind = "ollama" | "openai_compatible";

export type ModelProvider = {
    id: string;
    name: string;
    kind: ProviderKind;
    base_url: string;
    built_in: boolean;
    api_key_configured: boolean;
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
};

export type ModelSettingsSnapshot = {
    providers: ModelProvider[];
    agents: Record<string, AgentModelSettings>;
};

export type DiscoveredModel = {
    name: string;
    size: number | null;
    modified_at: string | null;
    warnings: string[];
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
        const body = (await response.json().catch(() => null)) as
            | { detail?: string }
            | null;
        throw new Error(body?.detail || `Request failed (${response.status})`);
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

export function saveAgentModel(
    agentId: string,
    value: Omit<AgentModelSettings, "provider">,
): Promise<AgentModelSettings> {
    return request(`/settings/agents/${encodeURIComponent(agentId)}`, {
        method: "PUT",
        body: JSON.stringify(value),
    });
}
