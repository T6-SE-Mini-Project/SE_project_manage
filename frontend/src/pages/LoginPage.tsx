
import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import GoogleButton from "../components/GoogleButton";
import {
  useEmailSignIn,
  useGoogleSignIn,
  usePasswordReset,
  useSession,
} from "../hooks/useAuth";
import { errorMessage } from "../errors";

interface LoginLocationState {
  /** The protected page that sent the customer here, if any. */
  from?: string;
}

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { isAuthenticated, isConfigured } = useSession();

  const emailSignIn = useEmailSignIn();
  const googleSignIn = useGoogleSignIn();
  const passwordReset = usePasswordReset();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  // Return to the page the login check interrupted, or the catalogue.
  const locationState = location.state as LoginLocationState | null;
  const from = locationState?.from ?? "/books";

  const pending = emailSignIn.isPending || googleSignIn.isPending;
  // Both sign-in paths end in the same place, so one message slot shows
  // whichever of them failed.
  const failure = emailSignIn.error ?? googleSignIn.error;

  async function signIn(start: () => Promise<unknown>) {
    try {
      await start();
      navigate(from, { replace: true });
    } catch {
      // The error message is displayed below.
    }
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void signIn(() => emailSignIn.mutateAsync({ email, password }));
  }

  function handleGoogle() {
    void signIn(() => googleSignIn.mutateAsync(undefined));
  }

  function handlePasswordReset() {
    passwordReset.reset();
    if (email.trim()) {
      passwordReset.mutate(email);
    }
  }

  if (isAuthenticated) {
    return (
      <div className="status-panel">
        <h1>You are already logged in</h1>
        <Link className="button primary" to="/books">
          Browse books
        </Link>
      </div>
    );
  }

  return (
    <section className="auth-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Account</p>
          <h1>Log in</h1>
          <p className="page-intro">
            Logging in keeps your order history with your account and lets
            you review the books you have read.
          </p>
        </div>
      </header>

      {!isConfigured ? (
        <div className="alert error" role="alert">
          Sign-in is not configured for this deployment. Add the
          <code> VITE_FIREBASE_*</code> variables to
          <code> frontend/.env</code> and reload.
        </div>
      ) : null}

      {failure ? (
        <div className="alert error" role="alert">
          {errorMessage(failure, "Could not log you in.")}
        </div>
      ) : null}

      {passwordReset.isSuccess ? (
        <div className="alert" role="status">
          If an account exists for {email}, a password reset link is on its
          way.
        </div>
      ) : null}

      {passwordReset.isError ? (
        <div className="alert error" role="alert">
          {errorMessage(passwordReset.error, "Could not send a reset email.")}
        </div>
      ) : null}

      <form className="auth-form" onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="email">Email address</label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </div>

        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </div>

        <button
          type="submit"
          className="button primary"
          disabled={pending || !isConfigured}
        >
          {emailSignIn.isPending ? "Logging in..." : "Log in"}
        </button>

        <button
          type="button"
          className="button-link"
          onClick={handlePasswordReset}
          disabled={!email.trim() || passwordReset.isPending || !isConfigured}
        >
          {passwordReset.isPending
            ? "Sending reset email..."
            : "Forgot your password?"}
        </button>

        <p className="auth-divider">
          <span>or</span>
        </p>

        <GoogleButton
          onClick={handleGoogle}
          pending={googleSignIn.isPending}
          disabled={pending || !isConfigured}
        />
      </form>

      <p className="muted">
        No account yet?{" "}
        <Link className="text-link" to="/register">
          Create one
        </Link>
        .
      </p>
    </section>
  );
}
