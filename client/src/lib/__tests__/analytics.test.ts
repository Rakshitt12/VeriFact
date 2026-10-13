import { describe, expect, it } from "vitest";
import { resolveAnalyticsConfig } from "@/lib/analytics";

describe("analytics config resolution", () => {
  it("no-ops when both vars are absent", () => {
    expect(resolveAnalyticsConfig({})).toBeNull();
  });

  it("no-ops when only the endpoint is set", () => {
    expect(
      resolveAnalyticsConfig({ VITE_ANALYTICS_ENDPOINT: "https://stats.example.com" }),
    ).toBeNull();
  });

  it("no-ops when only the website id is set", () => {
    expect(
      resolveAnalyticsConfig({ VITE_ANALYTICS_WEBSITE_ID: "abc-123" }),
    ).toBeNull();
  });

  it("no-ops on blank values", () => {
    expect(
      resolveAnalyticsConfig({
        VITE_ANALYTICS_ENDPOINT: "   ",
        VITE_ANALYTICS_WEBSITE_ID: "",
      }),
    ).toBeNull();
  });

  it("returns a config when both vars are set", () => {
    expect(
      resolveAnalyticsConfig({
        VITE_ANALYTICS_ENDPOINT: "https://stats.example.com",
        VITE_ANALYTICS_WEBSITE_ID: "abc-123",
      }),
    ).toEqual({
      endpoint: "https://stats.example.com",
      websiteId: "abc-123",
    });
  });

  it("trims whitespace and trailing slashes from the endpoint", () => {
    expect(
      resolveAnalyticsConfig({
        VITE_ANALYTICS_ENDPOINT: "  https://stats.example.com/// ",
        VITE_ANALYTICS_WEBSITE_ID: "  abc-123  ",
      }),
    ).toEqual({
      endpoint: "https://stats.example.com",
      websiteId: "abc-123",
    });
  });
});
