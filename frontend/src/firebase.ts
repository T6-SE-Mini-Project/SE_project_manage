/**
 * Firebase Authentication — the one place that talks to the Firebase SDK.
 *
 * Firebase owns credentials: passwords are never sent to, or stored by,
 * this project's backend. Signing in yields an **ID token** (a JWT signed
 * by Google), which `api.ts` sends as `Authorization: Bearer <token>` on
 * every request; the Django middleware verifies it and maps the Firebase
 * uid to a customer account.
 *
 * Two things this module exists to contain:
 *
 * 1. **Lazy initialization.** `initializeApp` throws when the config is
 *    empty, and `frontend/.env` may not have been filled in yet, so the
 *    SDK is created on first use rather than at import. An unconfigured
 *    build still loads and explains itself instead of showing a blank
 *    page.
 * 2. **Readable errors.** Firebase rejects with messages like
 *    "Firebase: Error (auth/invalid-credential)." Every helper below
 *    converts those codes into something a customer can act on and
 *    throws an `AuthError`, so pages can render `error.message` the same
 *    way they render the API's messages.
 */
import { type FirebaseApp, initializeApp } from "firebase/app";
import {
  GoogleAuthProvider,
  type Auth,
  type User as FirebaseUser,
  browserLocalPersistence,
  createUserWithEmailAndPassword,
  getAuth,
  onIdTokenChanged,
  sendPasswordResetEmail,
  setPersistence,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut,
  updateProfile,
} from "firebase/auth";

import { FIREBASE_CONFIG, IS_FIREBASE_CONFIGURED } from "./config";

export type { FirebaseUser };

/** A sign-in failure with a message meant for the customer. */
export class AuthError extends Error {
  code: string;

  constructor(message: string, code = "") {
    super(message);
    this.name = "AuthError";
    this.code = code;
  }
}

const NOT_CONFIGURED =
  "Sign-in is not configured for this deployment. Set the VITE_FIREBASE_* " +
  "variables in frontend/.env and reload.";

const MESSAGES: Record<string, string> = {
  "auth/invalid-email": "That does not look like an email address.",
  "auth/user-disabled": "This account has been disabled.",
  "auth/user-not-found": "No account matches that email address.",
  "auth/wrong-password": "That email address and password do not match.",
  "auth/invalid-credential": "That email address and password do not match.",
  "auth/invalid-login-credentials":
    "That email address and password do not match.",
  "auth/email-already-in-use": "An account with that email already exists.",
  "auth/weak-password": "Choose a password of at least six characters.",
  "auth/missing-password": "Enter your password.",
  "auth/too-many-requests":
    "Too many attempts. Please wait a moment and try again.",
  "auth/network-request-failed":
    "The network is unavailable. Check your connection and try again.",
  "auth/popup-closed-by-user": "The Google sign-in window was closed.",
  "auth/cancelled-popup-request": "The Google sign-in window was closed.",
  "auth/popup-blocked":
    "Your browser blocked the Google sign-in window. Allow pop-ups and try again.",
  "auth/account-exists-with-different-credential":
    "That email address is already registered with a different sign-in method.",
  "auth/unauthorized-domain":
    "This site is not an authorized domain for the Firebase project.",
  "auth/operation-not-allowed":
    "This sign-in method is not enabled for the Firebase project.",
};

function toAuthError(error: unknown, fallback: string): AuthError {
  const code =
    typeof error === "object" && error !== null && "code" in error
      ? String((error as { code: unknown }).code)
      : "";

  return new AuthError(MESSAGES[code] ?? fallback, code);
}

let app: FirebaseApp | null = null;
let auth: Auth | null = null;

/** The Firebase Auth instance, created on first use. */
export function firebaseAuth(): Auth {
  if (!IS_FIREBASE_CONFIGURED) {
    throw new AuthError(NOT_CONFIGURED, "auth/not-configured");
  }

  if (auth === null) {
    app = app ?? initializeApp(FIREBASE_CONFIG);
    auth = getAuth(app);
    // Keep the customer signed in across reloads and tabs. This is the
    // SDK default, but stating it means a future change to the default
    // cannot silently log everybody out on refresh.
    void setPersistence(auth, browserLocalPersistence);
  }

  return auth;
}

/**
 * Watch the ID token. The listener fires on sign-in, on sign-out and
 * whenever the SDK refreshes the token (roughly hourly), which is what
 * keeps `authId` in `useAuth` current without polling. Returns the
 * unsubscribe function.
 */
export function watchIdToken(
  listener: (user: FirebaseUser | null) => void,
): () => void {
  if (!IS_FIREBASE_CONFIGURED) {
    listener(null);
    return () => {};
  }

  return onIdTokenChanged(firebaseAuth(), listener);
}

/**
 * The current ID token, or `""` when nobody is signed in.
 *
 * `getIdToken()` returns the cached token and refreshes it only when it
 * is close to expiring, so this is cheap enough to call before every
 * request.
 */
export async function currentIdToken(): Promise<string> {
  if (!IS_FIREBASE_CONFIGURED) {
    return "";
  }

  const user = firebaseAuth().currentUser;
  if (user === null) {
    return "";
  }

  try {
    return await user.getIdToken();
  } catch {
    // A revoked or disabled account cannot mint a token. Send the
    // request without one and let the API answer "not signed in".
    return "";
  }
}

export async function signInWithEmail(
  email: string,
  password: string,
): Promise<FirebaseUser> {
  try {
    const credential = await signInWithEmailAndPassword(
      firebaseAuth(),
      email.trim(),
      password,
    );
    return credential.user;
  } catch (error) {
    throw toAuthError(error, "Could not sign you in.");
  }
}

export async function signUpWithEmail(
  email: string,
  password: string,
  displayName = "",
): Promise<FirebaseUser> {
  try {
    const credential = await createUserWithEmailAndPassword(
      firebaseAuth(),
      email.trim(),
      password,
    );

    if (displayName.trim()) {
      // Stored on the Firebase account, so it arrives in the ID token's
      // "name" claim and the backend can show it to administrators.
      await updateProfile(credential.user, { displayName: displayName.trim() });
      // Refresh the token so the new name is in the claims the backend
      // reads on the sign-in request that follows.
      await credential.user.getIdToken(true);
    }

    return credential.user;
  } catch (error) {
    throw toAuthError(error, "Your account could not be created.");
  }
}

export async function signInWithGoogle(): Promise<FirebaseUser> {
  const provider = new GoogleAuthProvider();
  // Always show the chooser: on a shared machine, silently reusing the
  // one Google session is the wrong default.
  provider.setCustomParameters({ prompt: "select_account" });

  try {
    const credential = await signInWithPopup(firebaseAuth(), provider);
    return credential.user;
  } catch (error) {
    throw toAuthError(error, "Could not sign you in with Google.");
  }
}

export async function sendPasswordReset(email: string): Promise<void> {
  try {
    await sendPasswordResetEmail(firebaseAuth(), email.trim());
  } catch (error) {
    throw toAuthError(error, "Could not send a password reset email.");
  }
}

export async function signOutOfFirebase(): Promise<void> {
  if (!IS_FIREBASE_CONFIGURED) {
    return;
  }

  try {
    await signOut(firebaseAuth());
  } catch (error) {
    throw toAuthError(error, "Could not sign you out.");
  }
}
