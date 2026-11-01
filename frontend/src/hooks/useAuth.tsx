
/**
 * Authentication hooks: Firebase for identity, TanStack Query for state.
 *
 * Firebase owns authentication. Django resolves the account and permissions.
 * Customer-specific cached data is cleared whenever the account changes.
 *
 * Authenticated sessions automatically expire after 15 minutes without
 * customer activity. Activity timestamps are shared across browser tabs.
 */

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, endSession, getSession, syncSession } from "../api";
import { IS_FIREBASE_CONFIGURED } from "../config";
import {
  type FirebaseUser,
  sendPasswordReset,
  signInWithEmail,
  signInWithGoogle,
  signOutOfFirebase,
  signUpWithEmail,
  watchIdToken,
} from "../firebase";
import type {
  EmailCredentials,
  EmailRegistration,
  SessionResponse,
} from "../types";

// 15 minutes without activity.
const INACTIVITY_TIMEOUT_MS = 15 * 60 * 1000;

// Shared between tabs belonging to the same browser origin.
const LAST_ACTIVITY_KEY = "obs_last_activity";

// In-memory fallback if localStorage is unavailable.
let fallbackLastActivity = 0;

// Avoid writing to localStorage on every mouse movement.
const ACTIVITY_WRITE_INTERVAL_MS = 1000;

export const authKeys = {
  session: () => ["auth", "session"] as const,
};

interface FirebaseAuthState {
  authId: string | null;
  email: string | null;
  displayName: string | null;
  isReady: boolean;
  isConfigured: boolean;
}

const ANONYMOUS: FirebaseAuthState = {
  authId: null,
  email: null,
  displayName: null,
  isReady: false,
  isConfigured: IS_FIREBASE_CONFIGURED,
};

const FirebaseAuthContext = createContext<FirebaseAuthState>({
  ...ANONYMOUS,
  isReady: true,
});

/**
 * Reads the last activity timestamp shared across browser tabs,
 * with an in-memory fallback if localStorage is unavailable.
 */
function readLastActivity(): number {
  try {
    const value = window.localStorage.getItem(LAST_ACTIVITY_KEY);
    const timestamp = Number(value);

    if (Number.isFinite(timestamp) && timestamp > 0) {
      fallbackLastActivity = Math.max(
        fallbackLastActivity,
        timestamp,
      );
    }
  } catch {
    // Use the in-memory timestamp when storage is unavailable.
  }

  return fallbackLastActivity;
}

/**
 * Saves the latest customer activity.
 */
function saveLastActivity(timestamp: number): void {
  fallbackLastActivity = timestamp;

  try {
    window.localStorage.setItem(
      LAST_ACTIVITY_KEY,
      String(timestamp),
    );
  } catch {
    // The current tab continues tracking activity in memory.
  }
}

/**
 * Clears customer-specific cached data.
 */
function resetCustomerData(
  queryClient: ReturnType<typeof useQueryClient>,
): void {
  void queryClient.invalidateQueries({ queryKey: ["cart"] });
  void queryClient.invalidateQueries({ queryKey: ["orders"] });
  void queryClient.invalidateQueries({ queryKey: ["reviews"] });
  void queryClient.invalidateQueries({ queryKey: ["admin"] });
}

/**
 * Holds Firebase authentication state for the entire application.
 *
 * Also monitors customer activity and automatically signs out after
 * 15 minutes of inactivity.
 */
export function FirebaseAuthProvider({
  children,
}: {
  children: ReactNode;
}) {
  const queryClient = useQueryClient();

  const [state, setState] = useState<FirebaseAuthState>(ANONYMOUS);

  const lastAuthId = useRef<string | null | undefined>(undefined);

  // Subscribe to Firebase authentication changes.
  useEffect(() => {
    if (!IS_FIREBASE_CONFIGURED) {
      setState({ ...ANONYMOUS, isReady: true });
      return;
    }

    return watchIdToken((user: FirebaseUser | null) => {
      setState({
        authId: user?.uid ?? null,
        email: user?.email ?? null,
        displayName: user?.displayName ?? null,
        isReady: true,
        isConfigured: true,
      });

      const authId = user?.uid ?? null;

      if (
        lastAuthId.current !== undefined &&
        lastAuthId.current !== authId
      ) {
        void queryClient.invalidateQueries({
          queryKey: authKeys.session(),
        });
      }

      lastAuthId.current = authId;
    });
  }, [queryClient]);

  // Monitor inactivity for authenticated customers.
  useEffect(() => {
    if (!state.isReady || !state.authId || !IS_FIREBASE_CONFIGURED) {
      return;
    }

    let timer: ReturnType<typeof setTimeout> | undefined;
    let logoutStarted = false;
    let lastLocalWrite = 0;

    // A new login is considered activity.
    saveLastActivity(Date.now());

    /**
     * Sign out once the inactivity period has elapsed.
     */
    async function expireSession() {
      if (logoutStarted) {
        return;
      }

      logoutStarted = true;

      if (timer !== undefined) {
        clearTimeout(timer);
      }

      try {
        // Firebase logout first, so protected API requests lose
        // their authentication token immediately.
        await signOutOfFirebase();

        // Terminate the corresponding Django session.
        const data = await endSession();

        queryClient.setQueryData(authKeys.session(), data);
      } catch {
        // If the backend request fails, Firebase may already be signed
        // out. Refresh the session query to reconcile the state.
        void queryClient.invalidateQueries({
          queryKey: authKeys.session(),
        });
      } finally {
        resetCustomerData(queryClient);
      }
    }

    /**
     * Checks elapsed inactivity time and schedules the next check.
     */
    function checkInactivity() {
      if (logoutStarted) {
        return;
      }

      const lastActivity = readLastActivity();

      // Missing or invalid activity data is treated as inactivity.
      const elapsed = lastActivity
        ? Date.now() - lastActivity
        : INACTIVITY_TIMEOUT_MS;

      const remaining = INACTIVITY_TIMEOUT_MS - elapsed;

      if (remaining <= 0) {
        void expireSession();
        return;
      }

      if (timer !== undefined) {
        clearTimeout(timer);
      }

      timer = setTimeout(checkInactivity, remaining);
    }

    /**
     * Records activity and restarts the inactivity countdown.
     */
    function handleActivity() {
      if (logoutStarted) {
        return;
      }

      const now = Date.now();

      // Do not allow a late event to revive an expired session.
      const lastActivity = readLastActivity();

      if (
        !lastActivity ||
        now - lastActivity >= INACTIVITY_TIMEOUT_MS
      ) {
        checkInactivity();
        return;
      }

      // Limit localStorage writes to once per second.
      if (now - lastLocalWrite >= ACTIVITY_WRITE_INTERVAL_MS) {
        saveLastActivity(now);
        lastLocalWrite = now;
      }

      checkInactivity();
    }

    // Mouse, keyboard, touch, pointer and scrolling activity.
    const activityEvents = [
      "pointerdown",
      "pointermove",
      "keydown",
      "touchstart",
      "scroll",
      "wheel",
    ] as const;

    activityEvents.forEach((eventName) => {
      window.addEventListener(eventName, handleActivity, {
        passive: true,
      });
    });

    // Another tab may have recorded customer activity.
    function handleStorage(event: StorageEvent) {
      if (event.key === LAST_ACTIVITY_KEY) {
        checkInactivity();
      }
    }

    // Check again when the browser tab becomes visible or focused.
    function handleVisibilityChange() {
      if (document.visibilityState === "visible") {
        checkInactivity();
      }
    }

    window.addEventListener("storage", handleStorage);
    window.addEventListener("focus", checkInactivity);

    document.addEventListener(
      "visibilitychange",
      handleVisibilityChange,
    );

    // Start the initial countdown.
    checkInactivity();

    return () => {
      if (timer !== undefined) {
        clearTimeout(timer);
      }

      activityEvents.forEach((eventName) => {
        window.removeEventListener(eventName, handleActivity);
      });

      window.removeEventListener("storage", handleStorage);
      window.removeEventListener("focus", checkInactivity);

      document.removeEventListener(
        "visibilitychange",
        handleVisibilityChange,
      );
    };
  }, [state.authId, state.isReady, queryClient]);

  return (
    <FirebaseAuthContext.Provider value={state}>
      {children}
    </FirebaseAuthContext.Provider>
  );
}

/** The Firebase sign-in state. */
export function useFirebaseAuth(): FirebaseAuthState {
  return useContext(FirebaseAuthContext);
}

/**
 * The current session: who is signed in, and whether they are staff.
 */
export function useSession() {
  const { authId, isReady, isConfigured } = useFirebaseAuth();

  const query = useQuery<SessionResponse, ApiError>({
    queryKey: authKeys.session(),
    queryFn: getSession,
    enabled: isReady,
    staleTime: 0,
  });

  const user = query.data?.user ?? null;

  const matchesAuthId =
    user === null || authId === null || user.uid === authId;

  return {
    ...query,
    isPending: !isReady || query.isPending,
    authId,
    isConfigured,
    user: matchesAuthId ? user : null,
    isAuthenticated: Boolean(
      authId && query.data?.authenticated && matchesAuthId,
    ),
    isStaff: Boolean(matchesAuthId && user?.is_staff),
  };
}

/**
 * Wraps a Firebase sign-in so the API learns about it.
 */
function useSignInMutation<TVariables>(
  signIn: (variables: TVariables) => Promise<unknown>,
) {
  const queryClient = useQueryClient();

  return useMutation<SessionResponse, Error, TVariables>({
    mutationFn: async (variables) => {
      await signIn(variables);
      return syncSession();
    },
    onSuccess: (data) => {
      queryClient.setQueryData(authKeys.session(), data);
      resetCustomerData(queryClient);
    },
  });
}

/** Sign in with email and password. */
export function useEmailSignIn() {
  return useSignInMutation(({ email, password }: EmailCredentials) =>
    signInWithEmail(email, password),
  );
}

/** Create an account. */
export function useEmailSignUp() {
  return useSignInMutation(
    ({ email, password, displayName }: EmailRegistration) =>
      signUpWithEmail(email, password, displayName),
  );
}

/** Sign in with Google. */
export function useGoogleSignIn() {
  return useSignInMutation(() => signInWithGoogle());
}

/** Send a password-reset email. */
export function usePasswordReset() {
  return useMutation<void, Error, string>({
    mutationFn: (email: string) => sendPasswordReset(email),
  });
}

/**
 * Manual sign-out.
 *
 * Firebase is signed out before the backend session is terminated.
 */
export function useSignOut() {
  const queryClient = useQueryClient();

  return useMutation<SessionResponse, Error, void>({
    mutationFn: async () => {
      await signOutOfFirebase();
      return endSession();
    },
    onSuccess: (data) => {
      queryClient.setQueryData(authKeys.session(), data);
      resetCustomerData(queryClient);
    },
  });
}

/** Display name for the sign-in provider. */
export function providerLabel(provider: string): string {
  if (provider === "google.com") {
    return "Google";
  }

  if (provider === "password") {
    return "Email";
  }

  return provider;
}

/** Friendly name of the signed-in customer. */
export function useAccountName(): string {
  const { user } = useSession();
  const { displayName, email } = useFirebaseAuth();

  return useMemo(() => {
    const name = user?.display_name || displayName || "";
    return name || user?.email || email || user?.username || "";
  }, [user, displayName, email]);
}
