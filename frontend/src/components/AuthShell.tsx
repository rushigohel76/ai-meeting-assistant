import { type ReactNode } from "react";
import { Link } from "react-router-dom";

type AuthShellProps = {
  title: string;
  subtitle: string;
  footerText: string;
  footerLinkText: string;
  footerLinkTo: string;
  children: ReactNode;
};

export function AuthShell({
  title,
  subtitle,
  footerText,
  footerLinkText,
  footerLinkTo,
  children,
}: AuthShellProps) {
  return (
    <main className="min-h-screen bg-zinc-50 text-zinc-950">
      <div className="mx-auto grid min-h-screen max-w-6xl grid-cols-1 lg:grid-cols-[1fr_28rem]">
        <section className="flex min-h-[15rem] flex-col justify-between bg-zinc-950 px-6 py-8 text-white sm:px-10 lg:min-h-screen">
          <Link to="/" className="text-lg font-semibold">
            MOM
          </Link>
          <div className="max-w-xl py-12">
            <p className="text-sm font-medium uppercase tracking-wide text-teal-300">
              Meeting intelligence
            </p>
            <h1 className="mt-4 text-4xl font-semibold leading-tight sm:text-5xl">
              Turn calls into useful memory.
            </h1>
            <p className="mt-5 max-w-md text-base leading-7 text-zinc-300">
              Capture meetings, transcribe speakers, and generate summaries with
              clear action items.
            </p>
          </div>
          <p className="text-sm text-zinc-400">FastAPI, Recall.ai, Deepgram, Claude</p>
        </section>

        <section className="flex items-center px-6 py-10 sm:px-10">
          <div className="w-full">
            <div>
              <h2 className="text-2xl font-semibold">{title}</h2>
              <p className="mt-2 text-sm leading-6 text-zinc-600">{subtitle}</p>
            </div>
            <div className="mt-8">{children}</div>
            <p className="mt-6 text-sm text-zinc-600">
              {footerText}{" "}
              <Link className="font-medium text-teal-700 hover:text-teal-800" to={footerLinkTo}>
                {footerLinkText}
              </Link>
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}
