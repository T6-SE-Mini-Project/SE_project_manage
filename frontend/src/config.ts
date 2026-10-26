/**
 * Central frontend configuration.
 *
 * Every environment-dependent value used by the React app is read here,
 * in one place, from Vite environment variables (`.env` files next to
 * `frontend/package.json`, e.g. `.env.development.local`). See
 * `frontend/.env.example`.
 */
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();

/** Base URL for Django API requests ("/api" by default, via the Vite proxy). */
export const API_BASE_URL = apiBaseUrl ? apiBaseUrl : "/api";

/** Whether the app runs against the local Vite dev server proxy. */
export const IS_DEV = import.meta.env.DEV;
