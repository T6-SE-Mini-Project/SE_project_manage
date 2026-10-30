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

function read(name: keyof ImportMetaEnv): string {
  return import.meta.env[name]?.trim() ?? "";
}

/**
 * Firebase web configuration, used by `src/firebase.ts` to sign customers
 * in with an email and password or with Google.
 *
 * None of these are secrets. A Firebase web config is published in every
 * browser bundle by design: it identifies the project, it does not
 * authorize anything. What protects the project is the authorized-domain
 * list in the Firebase console and the backend verifying each ID token
 * against `FIREBASE_PROJECT_ID`. Even so, keep them in `.env` files
 * rather than in source, so a different project can be pointed at
 * without a code change.
 */
export const FIREBASE_CONFIG = {
  apiKey: read("VITE_FIREBASE_API_KEY"),
  authDomain: read("VITE_FIREBASE_AUTH_DOMAIN"),
  projectId: read("VITE_FIREBASE_PROJECT_ID"),
  storageBucket: read("VITE_FIREBASE_STORAGE_BUCKET"),
  messagingSenderId: read("VITE_FIREBASE_MESSAGING_SENDER_ID"),
  appId: read("VITE_FIREBASE_APP_ID"),
};

/**
 * Whether sign-in can work at all.
 *
 * The three values below are the ones the Firebase SDK cannot start
 * without. A build whose `.env` has not been filled in yet must still
 * load and show a readable message instead of crashing on import, so
 * every entry point checks this first.
 */
export const IS_FIREBASE_CONFIGURED = Boolean(
  FIREBASE_CONFIG.apiKey &&
    FIREBASE_CONFIG.authDomain &&
    FIREBASE_CONFIG.projectId,
);
