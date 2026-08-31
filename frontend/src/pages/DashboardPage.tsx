import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { AppLayout } from "../components/AppLayout";
import { StatusBadge } from "../components/StatusBadge";
import { useToast } from "../context/ToastContext";
import { ApiError, createMeeting, listMeetings, type Meeting } from "../lib/api";
import { formatDateTime, getMeetingTitle, isActiveStatus } from "../lib/meetings";

export function DashboardPage() {
  const { showError, showSuccess } = useToast();
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [meetingUrl, setMeetingUrl] = useState("");
  const [title, setTitle] = useState("");
  const [loadingMeetings, setLoadingMeetings] = useState(true);
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState("");

  const hasActiveMeetings = useMemo(
    () => meetings.some((meeting) => isActiveStatus(meeting.status)),
    [meetings],
  );

  const refreshMeetings = useCallback(
    async (quiet = false) => {
      try {
        const response = await listMeetings();
        setMeetings(response);
      } catch (error) {
        if (!quiet) {
          showError(error instanceof ApiError ? error.detail : "Unable to load meetings.");
        }
      } finally {
        setLoadingMeetings(false);
      }
    },
    [showError],
  );

  useEffect(() => {
    refreshMeetings();
  }, [refreshMeetings]);

  useEffect(() => {
    if (!hasActiveMeetings) {
      return;
    }

    const intervalId = window.setInterval(() => {
      refreshMeetings(true);
    }, 12_000);

    return () => window.clearInterval(intervalId);
  }, [hasActiveMeetings, refreshMeetings]);

  async function handleCreateMeeting(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError("");

    const validationError = validateMeetingUrl(meetingUrl);
    if (validationError) {
      setFormError(validationError);
      return;
    }

    setCreating(true);
    try {
      const meeting = await createMeeting(meetingUrl.trim(), title.trim());
      setMeetings((currentMeetings) => [meeting, ...currentMeetings]);
      setMeetingUrl("");
      setTitle("");
      showSuccess("Meeting bot is joining.");
    } catch (error) {
      const message =
        error instanceof ApiError ? error.detail : "Unable to create meeting.";
      setFormError(message);
      showError(message);
    } finally {
      setCreating(false);
    }
  }

  return (
    <AppLayout>
      <section className="mx-auto flex max-w-6xl flex-col gap-8 px-6 py-8">
        <div>
          <p className="text-sm font-medium uppercase tracking-wide text-teal-700">
            Dashboard
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-normal">Meetings</h1>
        </div>

        <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
          <div className="flex flex-col gap-1">
            <h2 className="text-lg font-semibold">Paste a meeting link</h2>
            <p className="text-sm text-zinc-600">
              Google Meet, Zoom, and Microsoft Teams links are supported.
            </p>
          </div>

          <form className="mt-5 grid gap-3 lg:grid-cols-[1fr_16rem_auto]" onSubmit={handleCreateMeeting}>
            <label className="block">
              <span className="sr-only">Meeting link</span>
              <input
                className="h-11 w-full rounded-lg border border-zinc-300 bg-white px-3 text-sm outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
                onChange={(event) => setMeetingUrl(event.target.value)}
                placeholder="https://meet.google.com/abc-defg-hij"
                type="url"
                value={meetingUrl}
              />
            </label>
            <label className="block">
              <span className="sr-only">Title</span>
              <input
                className="h-11 w-full rounded-lg border border-zinc-300 bg-white px-3 text-sm outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Optional title"
                type="text"
                value={title}
              />
            </label>
            <button
              className="h-11 rounded-lg bg-zinc-950 px-5 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-300"
              disabled={creating}
              type="submit"
            >
              {creating ? "Joining..." : "Join"}
            </button>
          </form>

          {formError && (
            <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
              {formError}
            </div>
          )}
        </section>

        <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
          <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-4">
            <h2 className="text-lg font-semibold">Past meetings</h2>
            {hasActiveMeetings && (
              <span className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                Auto-updating
              </span>
            )}
          </div>

          {loadingMeetings ? (
            <MeetingListSkeleton />
          ) : meetings.length === 0 ? (
            <EmptyMeetings />
          ) : (
            <div className="divide-y divide-zinc-200">
              {meetings.map((meeting) => (
                <Link
                  className="grid gap-3 px-5 py-4 transition hover:bg-zinc-50 sm:grid-cols-[1fr_auto] sm:items-center"
                  key={meeting.id}
                  to={`/meetings/${meeting.id}`}
                >
                  <div className="min-w-0">
                    <h3 className="truncate text-sm font-semibold text-zinc-950">
                      {getMeetingTitle(meeting)}
                    </h3>
                    <p className="mt-1 truncate text-sm text-zinc-600">
                      {formatDateTime(meeting.created_at)}
                    </p>
                  </div>
                  <StatusBadge status={meeting.status} />
                </Link>
              ))}
            </div>
          )}
        </section>
      </section>
    </AppLayout>
  );
}

function EmptyMeetings() {
  return (
    <div className="px-5 py-12 text-center">
      <h3 className="text-base font-semibold">No meetings yet</h3>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-zinc-600">
        Paste a meeting link above and MOM will send a bot to capture the conversation.
      </p>
    </div>
  );
}

function MeetingListSkeleton() {
  return (
    <div className="divide-y divide-zinc-200">
      {[0, 1, 2].map((item) => (
        <div className="grid gap-3 px-5 py-4 sm:grid-cols-[1fr_auto] sm:items-center" key={item}>
          <div>
            <div className="h-4 w-56 animate-pulse rounded bg-zinc-200" />
            <div className="mt-2 h-3 w-36 animate-pulse rounded bg-zinc-200" />
          </div>
          <div className="h-7 w-24 animate-pulse rounded-full bg-zinc-200" />
        </div>
      ))}
    </div>
  );
}

function validateMeetingUrl(value: string) {
  if (!value.trim()) {
    return "Paste a meeting link first.";
  }

  try {
    const url = new URL(value);
    if (url.protocol !== "https:") {
      return "Meeting links must use https.";
    }
  } catch {
    return "Enter a valid meeting URL.";
  }

  return "";
}
