import { describe, expect, it } from "vitest";

import { formatPrice } from "./format";

describe("formatPrice", () => {
  it("formats prices in Indian rupees", () => {
    const formatted = formatPrice("2499.00");

    expect(formatted).toContain("₹");
    expect(formatted).toContain("2,499.00");
    expect(formatted).not.toContain("$");
  });

  it("groups large amounts using the Indian digit system", () => {
    expect(formatPrice("125000.00")).toContain("1,25,000.00");
  });

  it("returns unparseable values unchanged", () => {
    expect(formatPrice("not-a-price")).toBe("not-a-price");
  });
});
