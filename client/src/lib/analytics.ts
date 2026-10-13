/**
 * Optional Umami analytics loader.
 *
 * The tracking script is injected only when BOTH build-time env vars are set:
 * - VITE_ANALYTICS_ENDPOINT
 * - VITE_ANALYTICS_WEBSITE_ID
 *
 * Otherwise this module no-ops, so local dev and deploys without analytics
 * configured never request a literal `%VITE_ANALYTICS_ENDPOINT%` path (404).
 */
export interface AnalyticsConfig {
  endpoint: string;
  websiteId: string;
}

export function resolveAnalyticsConfig(
  env: Record<string, string | undefined>,
): AnalyticsConfig | null {
  const endpoint = (env.VITE_ANALYTICS_ENDPOINT ?? "").trim().replace(/\/+$/, "");
  const websiteId = (env.VITE_ANALYTICS_WEBSITE_ID ?? "").trim();
  if (!endpoint || !websiteId) return null;
  return { endpoint, websiteId };
}

export function initAnalytics(): void {
  if (typeof document === "undefined") return;
  const config = resolveAnalyticsConfig(
    import.meta.env as Record<string, string | undefined>,
  );
  if (!config) return;
  const src = `${config.endpoint}/umami`;
  // Guard against double-injection (e.g. HMR re-runs).
  if (document.querySelector(`script[src="${src}"]`)) return;
  const script = document.createElement("script");
  script.defer = true;
  script.src = src;
  script.setAttribute("data-website-id", config.websiteId);
  document.head.appendChild(script);
}
