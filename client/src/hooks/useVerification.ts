/**
 * Verification request state machine for the Home page.
 *
 * Flow: validate input -> POST /api/analyze -> persist the
 * VerificationResponse in sessionStorage -> navigate to /analyze/<request_id>.
 *
 * The loading stages are a deterministic UI presentation of the backend
 * evidence pipeline — they are NOT measured backend progress percentages.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "wouter";
import {
  analyzeVerification,
  validateVerificationInput,
  VerificationApiError,
} from "@/lib/api";
import type { FrontendInputMode, VerificationResponse } from "@/lib/types";

export const VERIFICATION_STAGES = [
  "Analyzing input",
  "Extracting claims",
  "Searching evidence",
  "Checking independent sources",
  "Comparing evidence",
  "Building report",
] as const;

const STAGE_INTERVAL_MS = 2600;

export function reportStorageKey(requestId: string): string {
  return `verifact-report:${requestId}`;
}

export function persistVerificationResponse(response: VerificationResponse): void {
  try {
    sessionStorage.setItem(reportStorageKey(response.request_id), JSON.stringify(response));
  } catch {
    // Storage full/blocked — the Analyze page will show a clean empty state.
  }
}

export function readVerificationResponse(requestId: string): VerificationResponse | null {
  try {
    const raw = sessionStorage.getItem(reportStorageKey(requestId));
    if (!raw) return null;
    return JSON.parse(raw) as VerificationResponse;
  } catch {
    return null;
  }
}

export type VerificationStatus = "idle" | "loading" | "error";

export function useVerification() {
  const [, navigate] = useLocation();
  const [status, setStatus] = useState<VerificationStatus>("idle");
  const [stageIndex, setStageIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (status !== "loading") return;
    setStageIndex(0);
    const timer = window.setInterval(() => {
      setStageIndex((index) =>
        index >= VERIFICATION_STAGES.length - 1 ? index : index + 1,
      );
    }, STAGE_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [status]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const verify = useCallback(
    async (value: string, mode: FrontendInputMode) => {
      if (status === "loading") return;
      const validationError = validateVerificationInput(mode, value);
      if (validationError) {
        setError(validationError);
        return { ok: false as const, error: validationError };
      }
      setError(null);
      setStatus("loading");
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        const response = await analyzeVerification(mode, value, {
          signal: controller.signal,
        });
        persistVerificationResponse(response);
        // Preserve the legacy session keys used across the app.
        try {
          sessionStorage.setItem("verifact-input", value);
          sessionStorage.setItem("verifact-mode", mode);
        } catch {
          /* session storage unavailable — report key is what matters */
        }
        setStatus("idle");
        navigate(`/analyze/${response.request_id}`);
        return { ok: true as const, response };
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          setStatus("idle");
          return { ok: false as const, error: "Verification was cancelled." };
        }
        const message =
          err instanceof VerificationApiError
            ? err.message
            : "Verification failed. Please try again.";
        setError(message);
        setStatus("error");
        return { ok: false as const, error: message };
      }
    },
    [navigate, status],
  );

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setStatus("idle");
    setError(null);
  }, []);

  return {
    status,
    loading: status === "loading",
    stage: VERIFICATION_STAGES[Math.min(stageIndex, VERIFICATION_STAGES.length - 1)],
    stageIndex,
    stageCount: VERIFICATION_STAGES.length,
    error,
    verify,
    reset,
  };
}
