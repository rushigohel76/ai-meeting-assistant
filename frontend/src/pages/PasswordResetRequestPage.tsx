import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { AuthShell } from "../components/AuthShell";
import { useToast } from "../context/ToastContext";
import { passwordResetRequest } from "../lib/api";

export default function PasswordResetRequestPage() {
  const { showError, showSuccess } = useToast();
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await passwordResetRequest(email.trim());
      showSuccess("If that email exists, a reset code was sent.");
    } catch (err: any) {
      showError(err?.detail ?? "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      title="Reset your password"
      subtitle="Enter your account email to receive a reset code."
      footerText="Remembered it?"
      footerLinkText="Sign in"
      footerLinkTo="/login"
    >
      <form className="flex flex-col gap-5" onSubmit={handleSubmit}>
        <label className="block">
          <span className="text-sm font-medium text-zinc-800">Email</span>
          <input
            className="mt-2 h-11 w-full rounded-lg border border-zinc-300 bg-white px-3 text-sm outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
          />
        </label>

        <button
          className="h-11 rounded-lg bg-zinc-950 px-4 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-300"
          type="submit"
          disabled={loading}
        >
          {loading ? "Sending..." : "Send reset code"}
        </button>

        <Link className="text-sm font-medium text-teal-700 hover:text-teal-800" to="/password-reset/confirm">
          I already have a code
        </Link>
      </form>
    </AuthShell>
  );
}
