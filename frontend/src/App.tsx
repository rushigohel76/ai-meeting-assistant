const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;

export function App() {
  return (
    <main className="min-h-screen bg-zinc-50 px-6 py-10 text-zinc-950">
      <section className="mx-auto flex max-w-3xl flex-col gap-6">
        <div>
          <p className="text-sm font-medium uppercase tracking-wide text-teal-700">
            Full-stack scaffold
          </p>
          <h1 className="mt-2 text-3xl font-semibold">MOM</h1>
        </div>

        <div className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-zinc-600">API base URL</p>
          <p className="mt-2 font-mono text-sm text-zinc-900">{apiBaseUrl}</p>
        </div>
      </section>
    </main>
  );
}
