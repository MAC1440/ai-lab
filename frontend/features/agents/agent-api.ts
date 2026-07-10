export type AgentProfile = {
    id: string;
    name: string;
    description: string;
    model: string;
    system_prompt: string;
    use_rag: boolean;
    tools: string[];
};

type AgentsResponse = {
    agents: AgentProfile[];
};

const API_BASE_URL =
    process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

export async function getAgents(): Promise<AgentProfile[]> {
    const response = await fetch(`${API_BASE_URL}/agents`, {
        cache: "no-store",
    });

    if (!response.ok) {
        throw new Error("Could not load agents.");
    }

    const data = (await response.json()) as AgentsResponse;
    return data.agents;
}