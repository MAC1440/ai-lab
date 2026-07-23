import assert from "node:assert/strict";
import test from "node:test";

import {
  getResponseError,
  parseNdjsonStream,
  streamNdjsonResponse,
} from "./ndjson-stream.mjs";

function chunkedStream(chunks) {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
      controller.close();
    },
  });
}

test("parses events split across arbitrary chunks and CRLF boundaries", async () => {
  const stream = chunkedStream([
    '{"type":"status","stage":"plan',
    'ning"}\r\n{"type":"done","value":',
    "2}\n",
  ]);
  const events = [];
  for await (const event of parseNdjsonStream(stream, "task stream")) {
    events.push(event);
  }
  assert.deepEqual(events, [
    { type: "status", stage: "planning" },
    { type: "done", value: 2 },
  ]);
});

test("parses a final event without a trailing newline", async () => {
  const events = [];
  for await (const event of parseNdjsonStream(
    chunkedStream(['{"type":"done"}']),
  )) {
    events.push(event);
  }
  assert.deepEqual(events, [{ type: "done" }]);
});

test("rejects malformed and invalid JSON events", async () => {
  await assert.rejects(
    async () => {
      for await (const event of parseNdjsonStream(
        chunkedStream(["not-json\n"]),
        "benchmark",
      )) {
        assert.ok(event);
      }
    },
    /invalid benchmark event/,
  );
  await assert.rejects(
    async () => {
      for await (const event of parseNdjsonStream(
        chunkedStream(['{"value":1}\n']),
        "task",
      )) {
        assert.ok(event);
      }
    },
    /malformed task event/,
  );
});

test("extracts JSON errors and refuses successful responses without a body", async () => {
  const response = new Response(JSON.stringify({ detail: "No model" }), {
    status: 422,
    headers: { "Content-Type": "application/json" },
  });
  assert.equal(await getResponseError(response, "benchmark"), "No model");

  const empty = new Response(null, { status: 200 });
  await assert.rejects(
    async () => {
      for await (const event of streamNdjsonResponse(empty, "task stream")) {
        assert.ok(event);
      }
    },
    /could not be read/,
  );
});
