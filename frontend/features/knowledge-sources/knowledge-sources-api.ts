const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type KnowledgeSource = {
  id: string;
  name: string;
  selections?: string[];
  source_directory?: string;
  document_count: number;
  chunk_count: number;
  updated_at: string;
};

export type KnowledgeStatus = {
  total_chunk_count: number;
  embedding_model: string;
  sources: KnowledgeSource[];
};

export type BrowseEntry = {
  name: string;
  path: string;
  kind: "directory" | "file";
  supported: boolean;
  size_bytes: number | null;
  reason: string | null;
};

export type BrowseResult = {
  path: string;
  parent: string | null;
  entries: BrowseEntry[];
  supported_extensions: string[];
};

export type SelectionPreview = {
  selection_count: number;
  document_count: number;
  total_bytes: number;
  estimated_chunks: number;
  extensions: Record<string, number>;
  files: {
    path: string;
    relative_path: string;
    size_bytes: number;
    extension: string;
  }[];
  truncated: boolean;
  skipped: { path: string; reason: string }[];
};

export type KnowledgeIndexEvent =
  | { type: "status"; stage: string; message: string; file_count?: number }
  | {
      type: "progress";
      stage: string;
      completed: number;
      total: number;
      chunk_count?: number;
      skipped_count?: number;
    }
  | {
      type: "done";
      result: KnowledgeSource & {
        skipped_count: number;
        skipped: { source: string; reason: string }[];
      };
    }
  | { type: "error"; message: string };

async function json<T>(path: string, init?: RequestInit): Promise<T> {
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

export const getKnowledgeStatus = () =>
  json<KnowledgeStatus>("/knowledge/sources");

export const browseKnowledgeFiles = (path?: string) =>
  json<BrowseResult>(
    `/knowledge/sources/browse${
      path ? `?path=${encodeURIComponent(path)}` : ""
    }`,
  );

export const previewKnowledgeSelection = (selections: string[]) =>
  json<SelectionPreview>("/knowledge/sources/preview", {
    method: "POST",
    body: JSON.stringify({ selections }),
  });

export async function* streamKnowledgeIndex(input: {
  sourceId: string;
  name: string;
  selections: string[];
}): AsyncGenerator<KnowledgeIndexEvent> {
  const response = await fetch(
    `${API_BASE_URL}/knowledge/sources/index/stream`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_id: input.sourceId,
        name: input.name,
        selections: input.selections,
      }),
    },
  );
  if (!response.ok || !response.body) {
    throw new Error(`Indexing request failed (${response.status})`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (line.trim()) yield JSON.parse(line) as KnowledgeIndexEvent;
    }
    if (done) break;
  }
  if (buffer.trim()) yield JSON.parse(buffer) as KnowledgeIndexEvent;
}

export const removeKnowledgeSource = (sourceId: string) =>
  json<{ removed: boolean }>(
    `/knowledge/sources/${encodeURIComponent(sourceId)}`,
    { method: "DELETE" },
  );
