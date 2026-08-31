import { FormEvent, useMemo, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { AuthShell } from "../components/AuthShell";
import { getFriendlyAuthError, useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

type LocationState = {
  from?: {
    pathname?: string;
  };
};

export function LoginPage() {
  const { login, status } = useAuth();
  const { showError, showSuccess } = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [formError, setFormError] = useState("");
  const [loading, setLoading] = useState(false);

  const emailError = useMemo(() => validateEmail(email), [email]);
  const passwordError = password ? "" : "Password is required.";
  const canSubmit = !emailError && !passwordError && !loading;

  if (status === "authenticated") {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError("");

    if (!canSubmit) {
      setFormError(emailError || passwordError || "Please check the form.");
      return;
    }

    setLoading(true);
    try {
      await login(email.trim(), password);
      showSuccess("Signed in.");
      const state = location.state as LocationState | null;
      navigate(state?.from?.pathname ?? "/", { replace: true });
    } catch (error) {
      const message = getFriendlyAuthError(error, "Invalid credentials");
      setFormError(message);
      showError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      title="Sign in"
      subtitle="Use your account to continue to your meeting workspace."
      footerText="New here?"
      footerLinkText="Create an account"
      footerLinkTo="/signup"
    >
      <form className="flex flex-col gap-5" onSubmit={handleSubmit}>
        <Field
          label="Email"
          type="email"
          value={email}
          onChange={setEmail}
          error={email ? emailError : ""}
          autoComplete="email"
        />
        <Field
          label="Password"
          type="password"
          value={password}
          onChange={setPassword}
          error={password ? "" : ""}
          autoComplete="current-password"
        />
        {formError && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            {formError}
          </div>
        )}
        <button
          className="h-11 rounded-lg bg-zinc-950 px-4 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-300"
          disabled={loading}
          type="submit"
        >
          {loading ? "Signing in..." : "Sign in"}
        </button>
        <div className="flex items-center justify-between">
          <Link className="text-sm font-medium text-teal-700 hover:text-teal-800" to="/password-reset">
            Forgot password?
          </Link>
          <Link className="text-sm font-medium text-teal-700 hover:text-teal-800" to="/signup">
            Create account
          </Link>
        </div>
      </form>
    </AuthShell>
  );
}

type FieldProps = {
  label: string;
  type: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  autoComplete?: string;
};

function Field({ label, type, value, onChange, error, autoComplete }: FieldProps) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-zinc-800">{label}</span>
      <input
        autoComplete={autoComplete}
        className="mt-2 h-11 w-full rounded-lg border border-zinc-300 bg-white px-3 text-sm outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
        onChange={(event) => onChange(event.target.value)}
        type={type}
        value={value}
      />
      {error && <span className="mt-1 block text-sm text-red-700">{error}</span>}
    </label>
  );
}

function validateEmail(email: string) {
  if (!email.trim()) {
    return "Email is required.";
  }
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) ? "" : "Enter a valid email address.";
}
