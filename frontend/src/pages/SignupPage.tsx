import { FormEvent, useMemo, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { AuthShell } from "../components/AuthShell";
import { getFriendlyAuthError, useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

export function SignupPage() {
  const { signup, status } = useAuth();
  const { showError, showSuccess } = useToast();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [formError, setFormError] = useState("");
  const [loading, setLoading] = useState(false);

  const emailError = useMemo(() => validateEmail(email), [email]);
  const passwordError = useMemo(() => validatePassword(password), [password]);
  const fullNameError = fullName.length > 255 ? "Full name must be 255 characters or fewer." : "";
  const canSubmit = !emailError && !passwordError && !fullNameError && !loading;

  if (status === "authenticated") {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError("");

    if (!canSubmit) {
      setFormError(emailError || passwordError || fullNameError || "Please check the form.");
      return;
    }

    setLoading(true);
    try {
      await signup(email.trim(), password, fullName.trim());
      showSuccess("Account created.");
      navigate("/", { replace: true });
    } catch (error) {
      const message = getFriendlyAuthError(error, "Unable to create account.");
      setFormError(message);
      showError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      title="Create account"
      subtitle="Start capturing meeting notes, summaries, and action items."
      footerText="Already have an account?"
      footerLinkText="Sign in"
      footerLinkTo="/login"
    >
      <form className="flex flex-col gap-5" onSubmit={handleSubmit}>
        <Field
          label="Full name"
          type="text"
          value={fullName}
          onChange={setFullName}
          error={fullNameError}
          autoComplete="name"
        />
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
          error={password ? passwordError : ""}
          autoComplete="new-password"
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
          {loading ? "Creating account..." : "Create account"}
        </button>
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
  const [passwordVisible, setPasswordVisible] = useState(false);
  const isPassword = type === "password";

  return (
    <label className="block">
      <span className="text-sm font-medium text-zinc-800">{label}</span>
      <span className="relative block mt-2">
        <input
          autoComplete={autoComplete}
          className="h-11 w-full rounded-lg border border-zinc-300 bg-white px-3 pr-11 text-sm outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
          onChange={(event) => onChange(event.target.value)}
          type={isPassword ? (passwordVisible ? "text" : "password") : type}
          value={value}
        />
        {isPassword && (
          <button
            aria-label={passwordVisible ? "Hide password" : "Show password"}
            className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-zinc-500 transition hover:text-zinc-800"
            onClick={() => setPasswordVisible((visible) => !visible)}
            type="button"
          >
            <svg aria-hidden="true" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
              {passwordVisible ? (
                <>
                  <path d="M3 3l18 18" />
                  <path d="M10.6 10.6a2 2 0 002.8 2.8" />
                  <path d="M9.9 4.2A10.7 10.7 0 0112 4c5 0 8.5 4 9.8 6a18.7 18.7 0 01-3.1 3.5M6.1 6.1C3.8 7.5 2.4 9.4 2.2 10c1.3 2 4.8 6 9.8 6 1 0 2-.2 2.8-.5" />
                </>
              ) : (
                <>
                  <path d="M2.2 12C3.5 10 7 6 12 6s8.5 4 9.8 6c-1.3 2-4.8 6-9.8 6s-8.5-4-9.8-6z" />
                  <circle cx="12" cy="12" r="2.5" />
                </>
              )}
            </svg>
          </button>
        )}
      </span>
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

function validatePassword(password: string) {
  if (!password) {
    return "Password is required.";
  }
  if (password.length < 8) {
    return "Password must be at least 8 characters.";
  }
  if (!/\d/.test(password)) {
    return "Password must contain at least one number.";
  }
  return "";
}
