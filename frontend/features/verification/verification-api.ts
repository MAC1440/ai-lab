import type {
  StartVerificationRequest,
  VerificationOverview,
  VerificationRun,
  VerificationStreamEvent,
} from "@/features/verification/verification-types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

async function getErrorMessage(response: Response): Promise<string> {
  const body = (await response.json().catch(() => null)) as
    | { detail?: unknown; error?: unknown }
    | null;

  if (typeof body?.detail === "string") {
    return body.detail;
  }
  if (typeof body?.error === "string") {
    return body.error;
  }
  return `Verification request failed with status ${response.status}`;
}

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(await getErrorMessage(response));
  }
  return response.json() as Promise<T>;
}

export async function getVerificationOverview(): Promise<VerificationOverview> {
  return parseJson<VerificationOverview>(
    await fetch(`${API_BASE_URL}/verifications/profiles`, {
      cache: "no-store",
    }),
  );
}

export async function listVerificationRuns(
  limit = 20,
): Promise<VerificationRun[]> {
  const response = await fetch(
    `${API_BASE_URL}/verifications/runs?limit=${limit}`,
    { cache: "no-store" },
  );
  const result = await parseJson<{ runs: VerificationRun[] }>(response);
  return result.runs;
}

export async function getVerificationRun(
  runId: string,
): Promise<VerificationRun> {
  return parseJson<VerificationRun>(
    await fetch(`${API_BASE_URL}/verifications/runs/${runId}`, {
      cache: "no-store",
    }),
  );
}

export async function cancelVerificationRun(runId: string): Promise<void> {
  await parseJson<{ run_id: string; cancellation_requested: boolean }>(
    await fetch(`${API_BASE_URL}/verifications/runs/${runId}/cancel`, {
      method: "POST",
    }),
  );
}

export async function* streamVerificationRun(
  request: StartVerificationRequest,
  signal?: AbortSignal,
): AsyncGenerator<VerificationStreamEvent, void, void> {
  const response = await fetch(`${API_BASE_URL}/verifications/run/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/x-ndjson",
    },
    body: JSON.stringify(request),
    signal,
  });

  if (!response.ok) {
    throw new Error(await getErrorMessage(response));
  }
  if (!response.body) {
    throw new Error("The verification stream could not be read.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });

    let newlineIndex = buffer.indexOf("\n");
    while (newlineIndex >= 0) {
      const line = buffer.slice(0, newlineIndex).trim();
      buffer = buffer.slice(newlineIndex + 1);

      if (line) {
        yield parseVerificationEvent(line);
      }
      newlineIndex = buffer.indexOf("\n");
    }

    if (done) {
      break;
    }
  }

  const finalLine = buffer.trim();
  if (finalLine) {
    yield parseVerificationEvent(finalLine);
  }
}

function parseVerificationEvent(line: string): VerificationStreamEvent {
  let parsed: unknown;

  try {
    parsed = JSON.parse(line);
  } catch {
    throw new Error("The backend returned an invalid verification event.");
  }

  if (
    !parsed ||
    typeof parsed !== "object" ||
    !("type" in parsed) ||
    typeof parsed.type !== "string"
  ) {
    throw new Error("The backend returned a malformed verification event.");
  }

  return parsed as VerificationStreamEvent;
}
