/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the Django API. Defaults to "/api" (same origin / Vite proxy). */
  readonly VITE_API_BASE_URL?: string;

  /* Firebase web configuration — read in src/config.ts, used by
     src/firebase.ts. Not secrets: see the comment there. */
  readonly VITE_FIREBASE_API_KEY?: string;
  readonly VITE_FIREBASE_AUTH_DOMAIN?: string;
  readonly VITE_FIREBASE_PROJECT_ID?: string;
  readonly VITE_FIREBASE_STORAGE_BUCKET?: string;
  readonly VITE_FIREBASE_MESSAGING_SENDER_ID?: string;
  readonly VITE_FIREBASE_APP_ID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
