import { Link, NavLink } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

export function AppLayout({ children }: { children: React.ReactNode }) {
  const { logout } = useAuth();

  return (
    <main className="min-h-screen bg-zinc-50 text-zinc-950">
      <header className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-8">
            <Link to="/" className="text-lg font-semibold">
              MOM
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
            className="h-10 rounded-lg border border-zinc-300 px-4 text-sm font-medium text-zinc-800 transition hover:bg-zinc-100"
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
