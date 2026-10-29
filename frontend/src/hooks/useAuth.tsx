/**
 * Authentication hooks: Firebase for identity, TanStack Query for state.
 *
 * Two layers, deliberately separate:
 *
 * 1. `FirebaseAuthProvider` subscribes to the Firebase SDK once, for the
 *    whole app, and holds the **authId** — the Firebase uid of whoever
 *    is signed in. The SDK fires on sign-in, sign-out and every token
 *    refresh, so the provider is what keeps that value correct without
 *    any screen polling for it.
 * 2. `useSession()` asks the API who that token resolves to. The account
 *    (and `is_staff`) is the server's answer, never the browser's: the
 *    Firebase token says *who* the customer is, only Django says what
 *    they may do.
 *
 * Signing in or out also clears cached per-customer data (cart, orders,
 * reviews, admin), so one customer never sees another customer's data.
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

export const authKeys = {
  session: () => ["auth", "session"] as const,
};

interface FirebaseAuthState {
  /** The Firebase uid of the signed-in customer, or null. */
  authId: string | null;
  /** The email address Firebase holds for them. */
  email: string | null;
  /** The display name Firebase holds for them, when set. */
  displayName: string | null;
  /** True once the SDK has reported its initial state. */
  isReady: boolean;
  /** False when the VITE_FIREBASE_* variables are missing. */
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
  // A component rendered outside the provider would otherwise wait for a
  // readiness that never arrives.
  isReady: true,
});

/**
 * Holds the Firebase sign-in state for the whole app.
 *
 * Mounted once, above the router, in `main.tsx`.
 */
export function FirebaseAuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<FirebaseAuthState>(ANONYMOUS);
  const lastAuthId = useRef<string | null | undefined>(undefined);

  useEffect(() => {
    if (!IS_FIREBASE_CONFIGURED) {
      // Nothing to subscribe to. Report readiness so the login check
      // resolves and the pages can explain what is missing.
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

      // A hourly token refresh fires this listener with the same uid and
      // changes nothing the API would answer differently, so only a real
      // change of account refetches the session.
      const authId = user?.uid ?? null;
      if (lastAuthId.current !== undefined && lastAuthId.current !== authId) {
        void queryClient.invalidateQueries({ queryKey: authKeys.session() });
      }
      lastAuthId.current = authId;
    });
  }, [queryClient]);

  return (
    <FirebaseAuthContext.Provider value={state}>
      {children}
    </FirebaseAuthContext.Provider>
  );
}

/** The Firebase sign-in state: the authId and whether it is known yet. */
export function useFirebaseAuth(): FirebaseAuthState {
  return useContext(FirebaseAuthContext);
}

/**
 * The current session: who is signed in, and whether they are staff.
 *
 * `isPending` stays true until both the Firebase SDK and the API have
 * answered, which is what the route guards wait on — rendering a
 * protected page before then would flash the login screen at a customer
 * who is in fact signed in.
 */
export function useSession() {
  const { authId, isReady, isConfigured } = useFirebaseAuth();

  const query = useQuery<SessionResponse, ApiError>({
    queryKey: authKeys.session(),
    queryFn: getSession,
    // Asking before the SDK has restored the saved sign-in would send an
    // unauthenticated request and cache "nobody is signed in".
    enabled: isReady,
    // The session is cheap and decides what the whole UI may show, so it
    // is kept fresh rather than served from a long-lived cache.
    staleTime: 0,
  });

  const user = query.data?.user ?? null;

  // The API's answer must be about the account the SDK currently holds.
  // The two disagree only in the moment between switching accounts and
  // the refetch landing, and showing one customer's name above another
  // customer's orders would be worse than showing nothing.
  const matchesAuthId = user === null || authId === null || user.uid === authId;

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
 *
 * Every successful sign-in is followed by one POST to `/auth/signin/`:
 * that is what links the Firebase uid to a customer account and hands
 * over the guest cart. Caches that depend on who the customer is are
 * dropped at the same time.
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

function resetCustomerData(
  queryClient: ReturnType<typeof useQueryClient>,
): void {
  // Who the customer is changes what the cart, order history and review
  // ownership contain, so drop those caches.
  void queryClient.invalidateQueries({ queryKey: ["cart"] });
  void queryClient.invalidateQueries({ queryKey: ["orders"] });
  void queryClient.invalidateQueries({ queryKey: ["reviews"] });
  void queryClient.invalidateQueries({ queryKey: ["admin"] });
}

/** Sign in with an email address and password. */
export function useEmailSignIn() {
  return useSignInMutation(({ email, password }: EmailCredentials) =>
    signInWithEmail(email, password),
  );
}

/** Create an account with an email address and password. */
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

/** Email a password-reset link to an address. */
export function usePasswordReset() {
  return useMutation<void, Error, string>({
    mutationFn: (email: string) => sendPasswordReset(email),
  });
}

/**
 * Sign out of Firebase, then of the API.
 *
 * Firebase first: once the SDK has dropped the token, no request can be
 * authenticated again, even if the call to the API fails.
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

/** How a customer signed in, for display. */
export function providerLabel(provider: string): string {
  if (provider === "google.com") {
    return "Google";
  }
  if (provider === "password") {
    return "Email";
  }
  return provider;
}

/** The friendliest name available for the signed-in customer. */
export function useAccountName(): string {
  const { user } = useSession();
  const { displayName, email } = useFirebaseAuth();

  return useMemo(() => {
    const name = user?.display_name || displayName || "";
    return name || user?.email || email || user?.username || "";
  }, [user, displayName, email]);
}
