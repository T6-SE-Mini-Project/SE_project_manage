import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useLogin, useSession } from "../hooks/useAuth";
import { errorMessage, fieldError, fieldErrors } from "../errors";

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { isAuthenticated } = useSession();
  const loginMutation = useLogin();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  // Where to return after a successful login: the page that redirected
  // here, or the catalogue.
  const from =
    (location.state as { from?: string } | null)?.from ?? "/books";
  const errors = fieldErrors(loginMutation.error);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();

    try {
      await loginMutation.mutateAsync({ username, password });
      navigate(from, { replace: true });
    } catch {
      // Rendered from the mutation state below.
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

      {loginMutation.isError ? (
        <div className="alert error" role="alert">
          {errorMessage(loginMutation.error, "Could not log you in.")}
        </div>
      ) : null}

      <form className="auth-form" onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="username">Username</label>
          <input
            id="username"
            name="username"
            type="text"
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            required
          />
          {fieldError(errors, "username") ? (
            <p className="field-error">{fieldError(errors, "username")}</p>
          ) : null}
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
          {fieldError(errors, "password") ? (
            <p className="field-error">{fieldError(errors, "password")}</p>
          ) : null}
        </div>

        <button
          type="submit"
          className="button primary"
          disabled={loginMutation.isPending}
        >
          {loginMutation.isPending ? "Logging in..." : "Log in"}
        </button>
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
