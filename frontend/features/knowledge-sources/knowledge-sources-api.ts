const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

export type KnowledgeSource = {
    id: string;
    name: string;
    source_directory: string;
    document_count: number;
    chunk_count: number;
    updated_at: string;
};

export type KnowledgeStatus = {
    total_chunk_count: number;
    embedding_model: string;
    sources: KnowledgeSource[];
};

export type KnowledgeIndexEvent =
    | { type: "status"; stage: string; message: string; file_count: number }
    | { type: "progress"; stage: string; completed: number; total: number; chunk_count?: number; skipped_count?: number }
    | { type: "done"; result: KnowledgeSource & { skipped_count: number } }
    | { type: "error"; message: string };

async function errorMessage(response: Response) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    return body?.detail ?? `Request failed (${response.status})`;
}

export async function getKnowledgeStatus(): Promise<KnowledgeStatus> {
    const response = await fetch(`${API_BASE_URL}/knowledge/sources`, { cache: "no-store" });
    if (!response.ok) throw new Error(await errorMessage(response));
    return response.json() as Promise<KnowledgeStatus>;
}

export async function removeKnowledgeSource(sourceId: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/knowledge/sources/${encodeURIComponent(sourceId)}`, { method: "DELETE" });
    if (!response.ok) throw new Error(await errorMessage(response));
}

export async function* streamKnowledgeIndex(input: {
    sourceId: string;
    name: string;
    sourceDirectory: string;
}): AsyncGenerator<KnowledgeIndexEvent> {
    const response = await fetch(`${API_BASE_URL}/knowledge/sources/index/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_id: input.sourceId, name: input.name, source_directory: input.sourceDirectory, batch_size: 24 }),
    });
    if (!response.ok || !response.body) throw new Error(await errorMessage(response));
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        let newline = buffer.indexOf("\n");
        while (newline >= 0) {
            const line = buffer.slice(0, newline).trim();
            buffer = buffer.slice(newline + 1);
            if (line) yield JSON.parse(line) as KnowledgeIndexEvent;
            newline = buffer.indexOf("\n");
        }
        if (done) break;
    }
    if (buffer.trim()) yield JSON.parse(buffer) as KnowledgeIndexEvent;
}
