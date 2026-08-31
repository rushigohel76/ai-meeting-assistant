import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { AuthShell } from "../components/AuthShell";
import { useToast } from "../context/ToastContext";
import { passwordResetConfirm } from "../lib/api";

export default function PasswordResetConfirmPage() {
  const { showError, showSuccess } = useToast();
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await passwordResetConfirm(email.trim(), otp.trim(), newPassword);
      showSuccess("Password updated. You can now sign in.");
    } catch (err: any) {
      showError(err?.detail ?? "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      title="Enter reset code"
      subtitle="Provide the code we emailed and choose a new password."
      footerText="Need a code?"
      footerLinkText="Request one"
      footerLinkTo="/password-reset"
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

        <label className="block">
          <span className="text-sm font-medium text-zinc-800">Code</span>
          <input
            className="mt-2 h-11 w-full rounded-lg border border-zinc-300 bg-white px-3 text-sm outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
            type="text"
            value={otp}
            onChange={(e) => setOtp(e.target.value)}
          />
        </label>

        <label className="block">
          <span className="text-sm font-medium text-zinc-800">New password</span>
          <input
            className="mt-2 h-11 w-full rounded-lg border border-zinc-300 bg-white px-3 text-sm outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            autoComplete="new-password"
          />
        </label>

        <button
          className="h-11 rounded-lg bg-zinc-950 px-4 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-300"
          type="submit"
          disabled={loading}
        >
          {loading ? "Updating..." : "Update password"}
        </button>

        <Link className="text-sm font-medium text-teal-700 hover:text-teal-800" to="/login">
          Back to sign in
        </Link>
      </form>
    </AuthShell>
  );
}
