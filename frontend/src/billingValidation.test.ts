import { describe, expect, it } from "vitest";

import {
  EMPTY_BILLING_ADDRESS,
  normalizeBillingAddress,
  validateBillingAddress,
} from "./billingValidation";

const VALID = {
  ...EMPTY_BILLING_ADDRESS,
  full_name: "Ananya Sharma",
  phone_number: "9876543210",
  email: "ananya.sharma@example.com",
  address_line1: "12 MG Road",
  address_line2: "Near City Library",
  city: "Bengaluru",
  state: "Karnataka",
  postal_code: "560001",
  country: "India",
};

describe("billing address validation", () => {
  it("accepts a complete address", () => {
    expect(validateBillingAddress(VALID)).toEqual({});
  });

  it("rejects missing required fields", () => {
    const errors = validateBillingAddress({
      ...EMPTY_BILLING_ADDRESS,
      country: "",
    });

    expect(errors.full_name).toMatch(/required/i);
    expect(errors.phone_number).toMatch(/required/i);
    expect(errors.email).toMatch(/required/i);
    expect(errors.address_line1).toMatch(/required/i);
    expect(errors.city).toMatch(/required/i);
    expect(errors.state).toMatch(/required/i);
    expect(errors.postal_code).toMatch(/required/i);
    expect(errors.country).toMatch(/required/i);
    expect(errors.address_line2).toBeUndefined();
  });

  it("requires a ten digit phone number", () => {
    expect(
      validateBillingAddress({ ...VALID, phone_number: "98765" }).phone_number,
    ).toMatch(/10 digits/i);
    expect(
      validateBillingAddress({ ...VALID, phone_number: "98765abcde" })
        .phone_number,
    ).toMatch(/10 digits/i);
  });

  it("accepts spaces and hyphens in a ten digit phone number", () => {
    expect(
      validateBillingAddress({
        ...VALID,
        phone_number: "98765-43210",
      }).phone_number,
    ).toBeUndefined();
  });

  it("rejects an invalid email address", () => {
    expect(
      validateBillingAddress({ ...VALID, email: "not-an-email" }).email,
    ).toMatch(/valid email/i);
  });

  it("requires a six digit PIN code", () => {
    expect(
      validateBillingAddress({ ...VALID, postal_code: "1234" }).postal_code,
    ).toMatch(/6 digits/i);
    expect(
      validateBillingAddress({ ...VALID, postal_code: "56A001" }).postal_code,
    ).toMatch(/6 digits/i);
  });

  it("normalizes values before submission", () => {
    expect(
      normalizeBillingAddress({
        ...VALID,
        full_name: "  Ananya   Sharma ",
        phone_number: "98765-43210",
        email: " ANANYA@EXAMPLE.COM ",
        postal_code: "560 001",
        country: " India ",
      }),
    ).toMatchObject({
      full_name: "Ananya Sharma",
      phone_number: "9876543210",
      email: "ananya@example.com",
      postal_code: "560001",
      country: "India",
    });
  });
});
