/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the Django API. Defaults to "/api" (same origin / Vite proxy). */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
