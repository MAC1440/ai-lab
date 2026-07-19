const API_BASE_URL =
    process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

export type MCPServer = {
    id: string;
    name: string;
    url: string;
    enabled: boolean;
    tool_prefix: string;
    allowed_tools: string[];
    agent_ids: string[];
};

export type MCPTool = {
    name: string;
    description: string;
    annotations: {
        readOnlyHint?: boolean;
        destructiveHint?: boolean;
        [key: string]: unknown;
    };
    currently_allowed: boolean;
    safe_to_enable: boolean;
    safety_reason: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${path}`, {
        ...init,
        headers: { "Content-Type": "application/json", ...init?.headers },
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

export async function listMCPServers(): Promise<MCPServer[]> {
    const result = await request<{ servers: MCPServer[] }>("/mcp");
    return result.servers;
}

export function saveMCPServer(server: MCPServer): Promise<MCPServer> {
    return request(`/mcp/servers/${encodeURIComponent(server.id)}`, {
        method: "PUT",
        body: JSON.stringify({
            name: server.name,
            url: server.url,
            enabled: server.enabled,
            tool_prefix: server.tool_prefix,
            allowed_tools: server.allowed_tools,
            agent_ids: server.agent_ids,
        }),
    });
}

export function deleteMCPServer(id: string): Promise<void> {
    return request(`/mcp/servers/${encodeURIComponent(id)}`, {
        method: "DELETE",
    });
}

export function discoverMCPTools(id: string): Promise<{
    server: MCPServer;
    tools: MCPTool[];
}> {
    return request(`/mcp/servers/${encodeURIComponent(id)}/tools`);
}

export function testMCPServer(id: string): Promise<{
    ok: boolean;
    message: string;
    server: MCPServer;
    tools: MCPTool[];
}> {
    return request(`/mcp/servers/${encodeURIComponent(id)}/test`, {
        method: "POST",
    });
}
