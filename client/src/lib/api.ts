/**
 * VeriFact backend API layer.
 *
 * Talks to the existing FastAPI backend (Part 10 API). No verification logic
 * lives here — this module only transports `VerificationRequest` payloads and
 * typed `VerificationResponse` results.
 *
 * Base URL resolution (no hardcoded localhost in production):
 * 1. `VITE_API_BASE_URL` when set (production convention).
 * 2. `http://localhost:8000` for local development (matches backend `PORT=8000`).
 * 3. Same-origin (`""`) as a reverse-proxy-friendly production fallback.
 */
import type {
  BackendInputType,
  FrontendInputMode,
  VerificationRequest,
  VerificationResponse,
} from "./types";

export const BACKEND_DEV_URL = "http://localhost:8000";
export const ANALYZE_PATH = "/api/analyze";
export const REQUEST_TIMEOUT_MS = 120_000;

/** Minimum input length mirrors backend `MIN_INPUT_LENGTH` (settings.py). */
export const MIN_INPUT_LENGTH = 20;

export function getApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL as string | undefined;
  if (configured && configured.trim().length > 0) return configured.replace(/\/+$/, "");
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    if (host === "localhost" || host === "127.0.0.1") return BACKEND_DEV_URL;
  }
  return "";
}

/**
 * Map frontend input tabs onto the backend schema (backend/api/schemas.py).
 * The backend only accepts `text` | `url`: a single claim is verified as text.
 */
export function buildVerificationPayload(
  mode: FrontendInputMode,
  value: string,
): VerificationRequest {
  const input_type: BackendInputType = mode === "url" ? "url" : "text";
  return { input_type, content: value.trim() };
}

/** Validate before sending so obvious mistakes never hit the network. */
export function validateVerificationInput(
  mode: FrontendInputMode,
  value: string,
): string | null {
  const trimmed = value.trim();
  if (trimmed.length === 0) return "Add a claim, article URL, or article text first.";
  if (mode === "url") {
    try {
      const parsed = new URL(trimmed);
      if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
        return "That URL needs to start with http:// or https://.";
      }
    } catch {
      return "That does not look like a valid article URL.";
    }
  }
  if (trimmed.length < MIN_INPUT_LENGTH) {
    return `Add a little more detail (at least ${MIN_INPUT_LENGTH} characters) so there is something verifiable to check.`;
  }
  return null;
}

export class VerificationApiError extends Error {
  readonly status: number | null;
  readonly code: string;

  constructor(message: string, opts: { status?: number | null; code?: string } = {}) {
    super(message);
    this.name = "VerificationApiError";
    this.status = opts.status ?? null;
    this.code = opts.code ?? "REQUEST_FAILED";
  }
}

function errorMessageForStatus(status: number, detail: unknown): string {
  const serverDetail =
    typeof detail === "object" && detail !== null && "message" in detail
      ? String((detail as { message: unknown }).message)
      : null;
  switch (status) {
    case 400:
      return serverDetail ?? "The backend rejected that input. Check the text or URL and try again.";
    case 422:
      return "No verifiable claims could be extracted from that input. Try a more factual statement.";
    case 503:
      return "Evidence retrieval is temporarily unavailable. Please try again in a moment.";
    case 504:
      return "Verification timed out. The evidence search took too long — try again.";
    default:
      return serverDetail ?? "Verification failed. Please try again.";
  }
}

/** Runtime shape guard — never trust the network blindly. */
export function isVerificationResponse(value: unknown): value is VerificationResponse {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.request_id === "string" &&
    Array.isArray(v.claims) &&
    (typeof v.overall_score === "number" || v.overall_score === null) &&
    typeof v.overall_classification === "string"
  );
}

export async function analyzeVerification(
  mode: FrontendInputMode,
  value: string,
  opts: { signal?: AbortSignal } = {},
): Promise<VerificationResponse> {
  const payload = buildVerificationPayload(mode, value);
  const url = `${getApiBaseUrl()}${ANALYZE_PATH}`;
  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: opts.signal ?? AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "TimeoutError") {
      throw new VerificationApiError("Verification timed out. Please try again.", {
        code: "TIMEOUT",
      });
    }
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new VerificationApiError(
      "The verification service is unreachable. Check your connection and that the backend is running.",
      { code: "NETWORK_ERROR" },
    );
  }

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    throw new VerificationApiError(errorMessageForStatus(response.status, body), {
      status: response.status,
    });
  }
  if (!isVerificationResponse(body)) {
    throw new VerificationApiError(
      "The backend returned an unexpected response. Please try again.",
      { code: "MALFORMED_RESPONSE" },
    );
  }
  return body;
}
