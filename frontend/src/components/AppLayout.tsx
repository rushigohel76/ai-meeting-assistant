import { Link, NavLink } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

export function AppLayout({
  children,
  variant = "default",
}: {
  children: React.ReactNode;
  variant?: "default" | "dashboard" | "meeting";
}) {
  const { logout } = useAuth();

  return (
    <main className={`app-shell ${variant === "dashboard" ? "dashboard-app workspace-dark" : variant === "meeting" ? "meeting-app workspace-dark" : "min-h-screen bg-zinc-50 text-zinc-950"}`}>
      <header className="app-header border-b border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-8">
            <Link to="/" className="app-brand text-lg font-semibold">
              {variant !== "default" && <span className="app-brand-mark" aria-hidden="true"><span /><span /><span /></span>}
              <span>MOM{variant !== "default" && <span className="app-brand-period">.</span>}</span>
            </Link>
            <nav className="hidden items-center gap-2 sm:flex">
              <NavLink
                className={({ isActive }) =>
                  [
                    "rounded-lg px-3 py-2 text-sm font-medium transition",
                    isActive ? "bg-zinc-100 text-zinc-950" : "text-zinc-600 hover:text-zinc-950",
                  ].join(" ")
                }
                to="/"
              >
                Dashboard
              </NavLink>
            </nav>
          </div>
          <button
            className="app-signout h-10 rounded-lg border border-zinc-300 px-4 text-sm font-medium text-zinc-800 transition hover:bg-zinc-100"
            onClick={logout}
            type="button"
          >
            Sign out
          </button>
        </div>
      </header>
      {children}
    </main>
  );
}
