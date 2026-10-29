
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import GoogleButton from "../components/GoogleButton";
import { useEmailSignUp, useGoogleSignIn, useSession } from "../hooks/useAuth";
import { errorMessage } from "../errors";

interface RegisterForm {
  displayName: string;
  email: string;
  password: string;
  confirmPassword: string;
}

const EMPTY_FORM: RegisterForm = {
  displayName: "",
  email: "",
  password: "",
  confirmPassword: "",
};

// Firebase's own minimum. Stating it here lets the form say so before a
// round trip, rather than showing the provider's rejection afterwards.
const MIN_PASSWORD_LENGTH = 6;

export default function RegisterPage() {
  const navigate = useNavigate();
  const { isAuthenticated, isConfigured } = useSession();

  const signUp = useEmailSignUp();
  const googleSignIn = useGoogleSignIn();

  const [form, setForm] = useState<RegisterForm>(EMPTY_FORM);
  const [mismatch, setMismatch] = useState("");

  const pending = signUp.isPending || googleSignIn.isPending;
  const failure = signUp.error ?? googleSignIn.error;

  function updateField(name: keyof RegisterForm, value: string) {
    setForm((current) => ({ ...current, [name]: value }));
    setMismatch("");
  }

  async function register(start: () => Promise<unknown>) {
    try {
      await start();
      // Firebase signs a new account in as it creates it, so the customer
      // is already logged in by the time this resolves.
      navigate("/books", { replace: true });
    } catch {
      // Registration errors are displayed below.
    }
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (form.password !== form.confirmPassword) {
      setMismatch("The two passwords do not match.");
      return;
    }

    void register(() =>
      signUp.mutateAsync({
        email: form.email,
        password: form.password,
        displayName: form.displayName,
      }),
    );
  }

  function handleGoogle() {
    void register(() => googleSignIn.mutateAsync(undefined));
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
            Sign up with your email address or with Google. Anything
            already in your cart stays there after you register.
          </p>
        </div>
      </header>

      {!isConfigured ? (
        <div className="alert error" role="alert">
          Sign-up is not configured for this deployment. Add the
          <code> VITE_FIREBASE_*</code> variables to
          <code> frontend/.env</code> and reload.
        </div>
      ) : null}

      {failure ? (
        <div className="alert error" role="alert">
          {errorMessage(failure, "Your account could not be created.")}
        </div>
      ) : null}

      <form className="auth-form" onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="display-name">Your name</label>
          <input
            id="display-name"
            name="displayName"
            type="text"
            autoComplete="name"
            value={form.displayName}
            onChange={(event) =>
              updateField("displayName", event.target.value)
            }
            required
          />
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
        </div>

        <div className="field">
          <label htmlFor="new-password">Password</label>
          <input
            id="new-password"
            name="password"
            type="password"
            autoComplete="new-password"
            minLength={MIN_PASSWORD_LENGTH}
            value={form.password}
            onChange={(event) => updateField("password", event.target.value)}
            required
          />
          <p className="field-hint">
            At least {MIN_PASSWORD_LENGTH} characters.
          </p>
        </div>

        <div className="field">
          <label htmlFor="confirm-password">Confirm password</label>
          <input
            id="confirm-password"
            name="confirmPassword"
            type="password"
            autoComplete="new-password"
            value={form.confirmPassword}
            onChange={(event) =>
              updateField("confirmPassword", event.target.value)
            }
            required
          />
          {mismatch ? <p className="field-error">{mismatch}</p> : null}
        </div>

        <button
          type="submit"
          className="button primary"
          disabled={pending || !isConfigured}
        >
          {signUp.isPending ? "Creating your account..." : "Create account"}
        </button>

        <p className="auth-divider">
          <span>or</span>
        </p>

        <GoogleButton
          onClick={handleGoogle}
          pending={googleSignIn.isPending}
          disabled={pending || !isConfigured}
          label="Sign up with Google"
        />
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
