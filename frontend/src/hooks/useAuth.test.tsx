/** @vitest-environment jsdom */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { FirebaseUser } from "../firebase";
import type { SessionResponse, User } from "../types";

declare global {
  // React's act() requires this flag in test environments.
  var IS_REACT_ACT_ENVIRONMENT: boolean;
}

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

// The Firebase SDK is replaced by a listener this test drives by hand, so
// the hook's handling of "signed in", "signed out" and "not reported
// yet" can each be exercised.
let notify: ((user: FirebaseUser | null) => void) | null = null;

vi.mock("../config", () => ({
  API_BASE_URL: "/api",
  IS_DEV: false,
  IS_FIREBASE_CONFIGURED: true,
  FIREBASE_CONFIG: {},
}));

vi.mock("../firebase", () => ({
  watchIdToken: (listener: (user: FirebaseUser | null) => void) => {
    notify = listener;
    return () => {
      notify = null;
    };
  },
  currentIdToken: () => Promise.resolve(""),
  signInWithEmail: vi.fn(),
  signUpWithEmail: vi.fn(),
  signInWithGoogle: vi.fn(),
  signOutOfFirebase: vi.fn(),
  sendPasswordReset: vi.fn(),
}));

const getSession = vi.fn<() => Promise<SessionResponse>>();

vi.mock("../api", () => ({
  ApiError: class ApiError extends Error {},
  getSession: () => getSession(),
  syncSession: vi.fn(),
  endSession: vi.fn(),
}));

const { FirebaseAuthProvider, providerLabel, useSession } = await import(
  "./useAuth"
);

function user(overrides: Partial<User> = {}): User {
  return {
    id: 1,
    username: "reader",
    email: "reader@example.com",
    is_staff: false,
    date_joined: "2026-01-01T00:00:00+00:00",
    uid: "uid-1",
    provider: "password",
    display_name: "Reader",
    ...overrides,
  };
}

function signedIn(uid: string): FirebaseUser {
  return { uid, email: "reader@example.com", displayName: "Reader" } as FirebaseUser;
}

interface Observed {
  isPending: boolean;
  isAuthenticated: boolean;
  authId: string | null;
  username: string | null;
}

let observed: Observed | null = null;

function Probe() {
  const session = useSession();
  observed = {
    isPending: session.isPending,
    isAuthenticated: session.isAuthenticated,
    authId: session.authId,
    username: session.user?.username ?? null,
  };
  return null;
}

describe("useSession", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    getSession.mockReset();
    observed = null;
    notify = null;
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
  });

  /** Let the session query start, resolve and re-render. */
  async function settle() {
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }

  async function render() {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <FirebaseAuthProvider>
            <Probe />
          </FirebaseAuthProvider>
        </QueryClientProvider>,
      );
    });
  }

  it("stays pending until Firebase has reported who is signed in", async () => {
    getSession.mockResolvedValue({ authenticated: true, user: user() });

    await render();

    // Deciding now would bounce a signed-in customer to the login page on
    // every page load, while the SDK is still reading its stored session.
    expect(observed?.isPending).toBe(true);
    expect(observed?.isAuthenticated).toBe(false);
  });

  it("reports the signed-in customer once both answers are in", async () => {
    getSession.mockResolvedValue({ authenticated: true, user: user() });

    await render();
    await act(async () => {
      notify?.(signedIn("uid-1"));
    });
    await settle();

    expect(observed?.authId).toBe("uid-1");
    expect(observed?.isAuthenticated).toBe(true);
    expect(observed?.username).toBe("reader");
    expect(observed?.isPending).toBe(false);
  });

  it("reports nobody when Firebase has no account", async () => {
    getSession.mockResolvedValue({ authenticated: false, user: null });

    await render();
    await act(async () => {
      notify?.(null);
    });
    await settle();

    expect(observed?.authId).toBeNull();
    expect(observed?.isAuthenticated).toBe(false);
    expect(observed?.isPending).toBe(false);
  });

  it("ignores an account the current token does not belong to", async () => {
    // The API's answer is about the previous customer: between switching
    // accounts and the refetch landing, showing their name above the new
    // customer's data would be worse than showing nothing.
    getSession.mockResolvedValue({
      authenticated: true,
      user: user({ uid: "uid-someone-else" }),
    });

    await render();
    await act(async () => {
      notify?.(signedIn("uid-1"));
    });
    await settle();

    expect(observed?.isAuthenticated).toBe(false);
    expect(observed?.username).toBeNull();
  });
});

describe("providerLabel", () => {
  it("names the sign-in methods the project offers", () => {
    expect(providerLabel("google.com")).toBe("Google");
    expect(providerLabel("password")).toBe("Email");
  });
});
