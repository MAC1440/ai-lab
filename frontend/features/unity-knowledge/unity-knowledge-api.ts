const API_BASE_URL =
    process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

export type UnityKnowledgeStatus = {
    collection: string;
    chunk_count: number;
    embedding_model: string;
};

export type UnityPreview = {
    source: string;
    front_matter: Record<string, string | number>;
    cleaned_content: string;
    original_characters: number;
    cleaned_characters: number;
    chunk_count: number;
    chunks: Array<{
        text: string;
        metadata: Record<string, string | number>;
    }>;
};

export type UnityIndexEvent =
    | {
        type: "status";
        stage: string;
        message: string;
        file_count: number;
    }
    | {
        type: "progress";
        stage: "cleaning" | "embedding";
        completed: number;
        total: number;
        chunk_count?: number;
        skipped_count?: number;
    }
    | {
        type: "done";
        result: {
            source_directory: string;
            document_count: number;
            skipped_count: number;
            chunk_count: number;
            skipped: Array<{ source: string; reason: string }>;
            skipped_truncated: boolean;
        };
    }
    | { type: "error"; message: string };

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
    return response.json() as Promise<T>;
}

export function getUnityKnowledgeStatus(): Promise<UnityKnowledgeStatus> {
    return request("/knowledge/unity/status");
}

export function previewUnityDocument(
    sourceDirectory: string,
    relativeFile: string,
): Promise<UnityPreview> {
    return request("/knowledge/unity/preview", {
        method: "POST",
        body: JSON.stringify({
            source_directory: sourceDirectory,
            relative_file: relativeFile,
        }),
    });
}

export async function* streamUnityIndex(
    sourceDirectory: string,
): AsyncGenerator<UnityIndexEvent> {
    const response = await fetch(`${API_BASE_URL}/knowledge/unity/index/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_directory: sourceDirectory, batch_size: 24 }),
    });
    if (!response.ok || !response.body) {
        const body = (await response.json().catch(() => null)) as
            | { detail?: string }
            | null;
        throw new Error(body?.detail || `Index request failed (${response.status})`);
    }

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
            if (line) yield JSON.parse(line) as UnityIndexEvent;
            newline = buffer.indexOf("\n");
        }
        if (done) break;
    }
    if (buffer.trim()) yield JSON.parse(buffer) as UnityIndexEvent;
}
