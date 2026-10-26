/** Helpers for reading the API's error payloads. */
import { ApiError } from "./api";
import type { FieldErrors } from "./types";

/**
 * Per-field validation messages from a rejected request.
 *
 * The form-backed endpoints (registration, login, reviews, catalogue
 * writes) return `{ error, errors: { field: [messages] } }`, so forms can
 * show a message next to the input that caused it. Returns an empty
 * object for failures that carry no field detail.
 */
export function fieldErrors(error: unknown): FieldErrors {
  if (error instanceof ApiError && error.body.errors) {
    return error.body.errors as FieldErrors;
  }
  return {};
}

/** The first message for a field, or an empty string. */
export function fieldError(errors: FieldErrors, field: string): string {
  return errors[field]?.[0] ?? "";
}

/** A readable message for any failure, API or otherwise. */
export function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return error instanceof Error ? error.message : fallback;
}
