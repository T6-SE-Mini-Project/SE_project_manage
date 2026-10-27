
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useRegister, useSession } from "../hooks/useAuth";
import { errorMessage, fieldError, fieldErrors } from "../errors";

interface RegisterForm {
  username: string;
  email: string;
  password1: string;
  password2: string;
}

const EMPTY_FORM: RegisterForm = {
  username: "",
  email: "",
  password1: "",
  password2: "",
};

export default function RegisterPage() {
  const navigate = useNavigate();
  const { isAuthenticated } = useSession();
  const registerMutation = useRegister();

  const [form, setForm] = useState<RegisterForm>(EMPTY_FORM);

  const errors = fieldErrors(registerMutation.error);

  function updateField(name: keyof RegisterForm, value: string) {
    setForm((current) => ({ ...current, [name]: value }));
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    try {
      await registerMutation.mutateAsync(form);

      // Account creation succeeds without logging the user in.
      // Redirect to login and display a success message there.
      navigate("/login", {
        replace: true,
        state: { registered: true },
      });
    } catch {
      // Registration errors are displayed below.
    }
  }

  if (isAuthenticated) {
    return (
      <div className="status-panel">
        <h1>You already have an account</h1>
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
          <h1>Create an account</h1>
          <p className="page-intro">
            Anything already in your cart stays there after you register.
          </p>
        </div>
      </header>

      {registerMutation.isError ? (
        <div className="alert error" role="alert">
          {errorMessage(
            registerMutation.error,
            "Your account could not be created.",
          )}
        </div>
      ) : null}

      <form className="auth-form" onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="new-username">Username</label>
          <input
            id="new-username"
            name="username"
            type="text"
            autoComplete="username"
            value={form.username}
            onChange={(event) => updateField("username", event.target.value)}
            required
          />
          {fieldError(errors, "username") ? (
            <p className="field-error">{fieldError(errors, "username")}</p>
          ) : null}
        </div>

        <div className="field">
          <label htmlFor="new-email">Email address</label>
          <input
            id="new-email"
            name="email"
            type="email"
            autoComplete="email"
            value={form.email}
            onChange={(event) => updateField("email", event.target.value)}
            required
          />
          {fieldError(errors, "email") ? (
            <p className="field-error">{fieldError(errors, "email")}</p>
          ) : null}
        </div>

        <div className="field">
          <label htmlFor="new-password">Password</label>
          <input
            id="new-password"
            name="password1"
            type="password"
            autoComplete="new-password"
            value={form.password1}
            onChange={(event) => updateField("password1", event.target.value)}
            required
          />
          {fieldError(errors, "password1") ? (
            <p className="field-error">{fieldError(errors, "password1")}</p>
          ) : null}
        </div>

        <div className="field">
          <label htmlFor="confirm-password">Confirm password</label>
          <input
            id="confirm-password"
            name="password2"
            type="password"
            autoComplete="new-password"
            value={form.password2}
            onChange={(event) => updateField("password2", event.target.value)}
            required
          />
          {fieldError(errors, "password2") ? (
            <p className="field-error">{fieldError(errors, "password2")}</p>
          ) : null}
        </div>

        <button
          type="submit"
          className="button primary"
          disabled={registerMutation.isPending}
        >
          {registerMutation.isPending
            ? "Creating your account..."
            : "Create account"}
        </button>
      </form>

      <p className="muted">
        Already registered?{" "}
        <Link className="text-link" to="/login">
          Log in
        </Link>
        .
      </p>
    </section>
  );
}
