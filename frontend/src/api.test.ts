import { describe, expect, it } from "vitest";

import { ApiError, shouldRetry } from "./api";

function apiError(status: number): ApiError {
  return new ApiError("nope", status, {});
}

describe("shouldRetry", () => {
  it("never retries a rate-limited request", () => {
    // Retrying a 429 spends the next window's allowance as well, so the
    // caller stays limited for longer than they need to.
    expect(shouldRetry(0, apiError(429))).toBe(false);
  });

  it("never retries a request the server rejected", () => {
    expect(shouldRetry(0, apiError(400))).toBe(false);
    expect(shouldRetry(0, apiError(401))).toBe(false);
    expect(shouldRetry(0, apiError(404))).toBe(false);
  });

  it("retries a server failure once", () => {
    expect(shouldRetry(0, apiError(503))).toBe(true);
    expect(shouldRetry(1, apiError(503))).toBe(false);
  });

  it("retries a network failure once", () => {
    const offline = new TypeError("Failed to fetch");

    expect(shouldRetry(0, offline)).toBe(true);
    expect(shouldRetry(1, offline)).toBe(false);
  });
});
