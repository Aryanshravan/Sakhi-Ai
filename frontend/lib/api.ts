const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL;

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request(path: string, init: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, credentials: "include" });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "Can't reach Sakhi AI right now. Please check your connection and try again.");
  }
  if (!response.ok) {
    const data: unknown = await response.json().catch(() => null);
    const detail = data && typeof data === "object" && "detail" in data ? data.detail : null;
    throw new ApiError(
      response.status,
      typeof detail === "string" ? detail : "Something went wrong. Please check the details and try again.",
    );
  }
  return response;
}

const JSON_HEADERS = { "Content-Type": "application/json" };

interface JsonInit {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
}

export async function api<T>(path: string, init: JsonInit = {}): Promise<T> {
  const response = await request(path, {
    method: init.method ?? "GET",
    headers: init.body ? JSON_HEADERS : undefined,
    body: init.body ? JSON.stringify(init.body) : undefined,
    signal: init.signal,
  });
  return (response.status === 204 ? undefined : await response.json()) as T;
}

/** POST JSON and receive binary data back (text-to-speech audio). */
export async function apiAudio(path: string, body: unknown, signal?: AbortSignal): Promise<Blob> {
  const response = await request(path, { method: "POST", headers: JSON_HEADERS, body: JSON.stringify(body), signal });
  return response.blob();
}

/** POST a recording and receive JSON back (speech-to-text). */
export async function apiUpload<T>(path: string, recording: Blob, signal?: AbortSignal): Promise<T> {
  const response = await request(path, {
    method: "POST",
    headers: { "Content-Type": recording.type },
    body: recording,
    signal,
  });
  return (await response.json()) as T;
}
