function parseEvent(line, label) {
  let parsed;
  try {
    parsed = JSON.parse(line);
  } catch {
    throw new Error(`The backend returned an invalid ${label} event.`);
  }
  if (
    !parsed ||
    typeof parsed !== "object" ||
    !("type" in parsed) ||
    typeof parsed.type !== "string"
  ) {
    throw new Error(`The backend returned a malformed ${label} event.`);
  }
  return parsed;
}

export async function* parseNdjsonStream(stream, label = "stream") {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });

      let newlineIndex = buffer.indexOf("\n");
      while (newlineIndex >= 0) {
        const line = buffer.slice(0, newlineIndex).trim();
        buffer = buffer.slice(newlineIndex + 1);
        if (line) {
          yield parseEvent(line, label);
        }
        newlineIndex = buffer.indexOf("\n");
      }

      if (done) {
        break;
      }
    }

    const finalLine = buffer.trim();
    if (finalLine) {
      yield parseEvent(finalLine, label);
    }
  } finally {
    reader.releaseLock();
  }
}

export async function getResponseError(response, fallbackLabel = "request") {
  const text = await response.text().catch(() => "");
  if (text) {
    try {
      const body = JSON.parse(text);
      if (typeof body?.detail === "string") return body.detail;
      if (typeof body?.message === "string") return body.message;
      if (typeof body?.error === "string") return body.error;
    } catch {
      if (text.length <= 500) return text;
    }
  }
  return `${fallbackLabel} failed with status ${response.status}`;
}

export async function* streamNdjsonResponse(response, label = "stream") {
  if (!response.ok) {
    throw new Error(await getResponseError(response, label));
  }
  if (!response.body) {
    throw new Error(`The ${label} could not be read.`);
  }
  yield* parseNdjsonStream(response.body, label);
}
