
/** @vitest-environment jsdom */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { FirebaseUser } from "../firebase";
import type { SessionResponse, User } from "../types";

declare global {
  var IS_REACT_ACT_ENVIRONMENT: boolean;
}

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

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
const endSession = vi.fn<() => Promise<SessionResponse>>();

vi.mock("../api", () => ({
  ApiError: class ApiError extends Error {},
  getSession: () => getSession(),
  syncSession: vi.fn(),
  endSession: () => endSession(),
}));

const { signOutOfFirebase } = await import("../firebase");

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
  return {
    uid,
    email: "reader@example.com",
    displayName: "Reader",
  } as FirebaseUser;
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
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.useRealTimers();

    getSession.mockReset();
    endSession.mockReset();
    vi.mocked(signOutOfFirebase).mockReset();

    endSession.mockResolvedValue({
      authenticated: false,
      user: null,
    });

    vi.mocked(signOutOfFirebase).mockResolvedValue(undefined);

    localStorage.clear();
    observed = null;
    notify = null;

    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);

    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          gcTime: 0,
        },
      },
    });
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });

    container.remove();
    queryClient.clear();
    vi.useRealTimers();
  });

  /**
   * Flush React and React Query updates.
   * React Query may schedule notifications using setTimeout(0).
   */
  async function settle() {
  await act(async () => {
    for (let i = 0; i < 5; i++) {
      await Promise.resolve();

      if (vi.isFakeTimers()) {
        await vi.advanceTimersByTimeAsync(0);
      } else {
        await new Promise((resolve) => setTimeout(resolve, 0));
      }
    }

    await Promise.resolve();
  });
}

  async function render() {
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

  async function authenticate() {
    getSession.mockResolvedValue({
      authenticated: true,
      user: user(),
    });

    await render();

    await act(async () => {
      notify?.(signedIn("uid-1"));
    });

    await settle();

    expect(observed?.isAuthenticated).toBe(true);
  }

  it("stays pending until Firebase has reported who is signed in", async () => {
    getSession.mockResolvedValue({
      authenticated: true,
      user: user(),
    });

    await render();

    expect(observed?.isPending).toBe(true);
    expect(observed?.isAuthenticated).toBe(false);
  });

  it("reports the signed-in customer once both answers are in", async () => {
    await authenticate();

    expect(observed?.authId).toBe("uid-1");
    expect(observed?.isAuthenticated).toBe(true);
    expect(observed?.username).toBe("reader");
    expect(observed?.isPending).toBe(false);
  });

  it("reports nobody when Firebase has no account", async () => {
    getSession.mockResolvedValue({
      authenticated: false,
      user: null,
    });

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

  it("automatically signs out after 15 minutes without activity", async () => {
    vi.useFakeTimers();

    await authenticate();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(15 * 60 * 1000);
    });

    expect(signOutOfFirebase).toHaveBeenCalledTimes(1);
    expect(endSession).toHaveBeenCalledTimes(1);
  });

  it("resets the inactivity timer when the customer interacts", async () => {
    vi.useFakeTimers();

    await authenticate();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(14 * 60 * 1000);
    });

    await act(async () => {
      window.dispatchEvent(new Event("pointerdown"));
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2 * 60 * 1000);
    });

    expect(signOutOfFirebase).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(13 * 60 * 1000);
    });

    expect(signOutOfFirebase).toHaveBeenCalledTimes(1);
    expect(endSession).toHaveBeenCalledTimes(1);
  });

  it("checks inactivity when the customer returns to the tab", async () => {
    vi.useFakeTimers();

    await authenticate();

    await act(async () => {
      vi.setSystemTime(Date.now() + 16 * 60 * 1000);

      document.dispatchEvent(new Event("visibilitychange"));
    });

    expect(signOutOfFirebase).toHaveBeenCalledTimes(1);
    expect(endSession).toHaveBeenCalledTimes(1);
  });
});

describe("providerLabel", () => {
  it("names the sign-in methods the project offers", () => {
    expect(providerLabel("google.com")).toBe("Google");
    expect(providerLabel("password")).toBe("Email");
  });
});
