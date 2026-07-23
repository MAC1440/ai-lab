export type NdjsonEvent = { type: string; [key: string]: unknown };

export function parseNdjsonStream(
  stream: ReadableStream<Uint8Array>,
  label?: string,
): AsyncGenerator<NdjsonEvent, void, void>;

export function getResponseError(
  response: Response,
  fallbackLabel?: string,
): Promise<string>;

export function streamNdjsonResponse(
  response: Response,
  label?: string,
): AsyncGenerator<NdjsonEvent, void, void>;
