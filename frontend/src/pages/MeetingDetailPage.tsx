import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";

import { AppLayout } from "../components/AppLayout";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Skeleton } from "../components/Skeleton";
import { StatusBadge } from "../components/StatusBadge";
import { useToast } from "../context/ToastContext";
import {
  ApiError,
  deleteMeeting,
  getMeeting,
  getMeetingSummary,
  getMeetingTranscript,
  retryMeetingTranscription,
  sendMeetingSummaryEmail,
  type Meeting,
  type MeetingSummaryResponse,
  type MeetingTranscriptResponse,
  type TranscriptSegment,
} from "../lib/api";
import {
  formatDateTime,
  formatTimestamp,
  getMeetingTitle,
  isActiveStatus,
  canDeleteMeeting,
} from "../lib/meetings";

export function MeetingDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { showError, showSuccess } = useToast();
  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [summaryData, setSummaryData] = useState<MeetingSummaryResponse | null>(null);
  const [transcriptData, setTranscriptData] = useState<MeetingTranscriptResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");

  const meetingId = id ?? "";
  const title = meeting ? getMeetingTitle(meeting) : "Meeting";
  const shouldPoll = meeting ? isActiveStatus(meeting.status) : false;

  const loadMeeting = useCallback(
    async (quiet = false) => {
      if (!meetingId) {
        return;
      }

      try {
        const meetingResponse = await getMeeting(meetingId);
        setMeeting(meetingResponse);
        setError("");

        if (meetingResponse.status === "completed") {
          const summaryResponse = await getMeetingSummary(meetingId);
          setSummaryData(summaryResponse);
          setTranscriptData(summaryResponse.transcript);
        } else if (meetingResponse.status === "failed" || meetingResponse.status === "processing") {
          try {
            setTranscriptData(await getMeetingTranscript(meetingId));
          } catch (transcriptError) {
            if (transcriptError instanceof ApiError && transcriptError.status === 404) {
              setTranscriptData(null);
            } else {
              throw transcriptError;
            }
          }
        }
      } catch (requestError) {
        const message =
          requestError instanceof ApiError
            ? requestError.detail
            : "Unable to load meeting.";
        if (!quiet) {
          setError(message);
          showError(message);
        }
      } finally {
        setLoading(false);
      }
    },
    [meetingId, showError],
  );

  useEffect(() => {
    loadMeeting();
  }, [loadMeeting]);

  useEffect(() => {
    if (!shouldPoll) {
      return;
    }

    const intervalId = window.setInterval(() => {
      loadMeeting(true);
    }, 12_000);

    return () => window.clearInterval(intervalId);
  }, [loadMeeting, shouldPoll]);

  async function handleRetry() {
    if (!meeting) {
      return;
    }

    setRetrying(true);
    try {
      await retryMeetingTranscription(meeting.id);
      showSuccess("Retry queued.");
      await loadMeeting(true);
    } catch (requestError) {
      const message =
        requestError instanceof ApiError ? requestError.detail : "Unable to retry processing.";
      showError(message);
    } finally {
      setRetrying(false);
    }
  }

  async function handleDelete() {
    if (!meeting || deleting) return;

    setDeleting(true);
    try {
      await deleteMeeting(meeting.id);
      showSuccess(meeting.status === "completed" ? "Meeting and its notes were deleted." : "Meeting capture was cancelled.");
      navigate("/", { replace: true });
    } catch (requestError) {
      showError(requestError instanceof ApiError ? requestError.detail : "Unable to delete meeting.");
    } finally {
      setDeleting(false);
    }
  }

  if (!id) {
    return <Navigate to="/" replace />;
  }

  return (
    <AppLayout variant="meeting">
      <section className="meeting-page mx-auto flex max-w-6xl flex-col gap-6 px-6 py-8">
        <Link className="meeting-back text-sm font-medium text-teal-700 hover:text-teal-800" to="/">
          <span aria-hidden="true">←</span> Back to dashboard
        </Link>

        {loading ? (
          <DetailSkeleton />
        ) : error && !meeting ? (
          <ErrorPanel message={error} />
        ) : meeting ? (
          <>
            <header className="meeting-hero rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div className="meeting-hero-copy min-w-0">
                  <p className="meeting-kicker"><span /> MEETING NOTES</p>
                  <h1 className="truncate text-3xl font-semibold">{title}</h1>
                  <p className="meeting-created mt-2 text-sm text-zinc-600">
                    <span aria-hidden="true">◷</span> Captured {formatDateTime(meeting.created_at)}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  {canDeleteMeeting(meeting.status) && (
                    <button
                      className="rounded-lg border border-red-300/25 px-3 py-2 text-sm font-medium text-red-200 transition hover:border-red-300/50 hover:bg-red-400/10"
                      onClick={() => setConfirmDelete(true)}
                      type="button"
                    >
                      Delete meeting
                    </button>
                  )}
                  <StatusBadge status={meeting.status} />
                </div>
              </div>
            </header>

            {meeting.status === "failed" ? (
              <FailedState
                retrying={retrying}
                transcriptData={transcriptData}
                onRetry={handleRetry}
              />
            ) : meeting.status === "completed" && summaryData ? (
              <CompletedMeeting summaryData={summaryData} />
            ) : transcriptData ? (
              <TranscriptOnlyMeeting transcriptData={transcriptData} />
            ) : (
              <ProcessingState status={meeting.status} />
            )}
          </>
        ) : null}
      </section>
      {confirmDelete && meeting && (
        <ConfirmDialog
          busy={deleting}
          confirmLabel="Delete meeting"
          description={meeting.status === "completed"
            ? `“${title}” and its summary and transcript will be permanently deleted.`
            : `The bot for “${title}” will be stopped and this meeting capture will be cancelled.`}
          onCancel={() => setConfirmDelete(false)}
          onConfirm={handleDelete}
          title={meeting.status === "completed" ? "Delete this completed meeting?" : "Cancel this meeting capture?"}
        />
      )}
    </AppLayout>
  );
}

function CompletedMeeting({ summaryData }: { summaryData: MeetingSummaryResponse }) {
  const [checkedItems, setCheckedItems] = useState<Record<number, boolean>>({});

  const actionItems = summaryData.summary.action_items;

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
      <section className="flex flex-col gap-6">
        <div className="meeting-panel summary-panel rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
          <div className="meeting-section-title"><span className="meeting-section-icon">✦</span><div><p>THE CONVERSATION</p><h2>Summary</h2></div></div>
          <p className="summary-copy mt-4 text-sm leading-6 text-zinc-700">
            {summaryData.summary.summary_text}
          </p>
          <h3 className="key-points-heading mt-6 text-sm font-semibold text-zinc-950">Key points</h3>
          <ul className="key-points mt-3 space-y-2 text-sm leading-6 text-zinc-700">
            {summaryData.summary.key_points.map((point) => (
              <li className="flex gap-2" key={point}>
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-600" />
                <span>{point}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="meeting-panel transcript-panel rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
          <div className="meeting-section-title"><span className="meeting-section-icon cyan">≋</span><div><p>THE FULL RECORD</p><h2>Transcript</h2></div></div>
          <div className="mt-4 max-h-[36rem] space-y-4 overflow-y-auto pr-2">
            {summaryData.transcript.raw_transcript_json.map((segment, index) => (
              <TranscriptRow key={`${segment.start_time}-${index}`} segment={segment} />
            ))}
          </div>
        </div>
      </section>

      <aside className="flex flex-col gap-6">
        <EmailSummaryPanel meetingId={summaryData.summary.meeting_id} />

        <div className="meeting-panel action-panel rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
          <div className="meeting-section-title"><span className="meeting-section-icon cyan">✓</span><div><p>WHAT'S NEXT</p><h2>Action items</h2></div></div>
          {actionItems.length === 0 ? (
            <p className="mt-3 text-sm text-zinc-600">No action items captured.</p>
          ) : (
            <div className="mt-4 space-y-3">
              {actionItems.map((item, index) => (
                <label
                  className="meeting-action-item flex cursor-pointer gap-3 rounded-lg border border-zinc-200 p-3 transition hover:bg-zinc-50"
                  key={`${item.task}-${index}`}
                >
                  <input
                    checked={Boolean(checkedItems[index])}
                    className="mt-1 h-4 w-4 rounded border-zinc-300 text-teal-700 focus:ring-teal-600"
                    onChange={(event) =>
                      setCheckedItems((currentItems) => ({
                        ...currentItems,
                        [index]: event.target.checked,
                      }))
                    }
                    type="checkbox"
                  />
                  <span>
                    <span className="block text-sm font-medium text-zinc-900">
                      {item.task}
                    </span>
                    <span className="mt-1 block text-xs text-zinc-500">
                      {item.owner || "Unassigned"}
                    </span>
                  </span>
                </label>
              ))}
            </div>
          )}
        </div>

        <div className="meeting-panel decisions-panel rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
          <div className="meeting-section-title"><span className="meeting-section-icon violet">◇</span><div><p>AGREED TOGETHER</p><h2>Decisions</h2></div></div>
          {summaryData.summary.decisions.length === 0 ? (
            <p className="mt-3 text-sm text-zinc-600">No decisions captured.</p>
          ) : (
            <ul className="mt-3 space-y-2 text-sm leading-6 text-zinc-700">
              {summaryData.summary.decisions.map((decision) => (
                <li className="flex gap-2" key={decision}>
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-zinc-500" />
                  <span>{decision}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>
    </div>
  );
}

function EmailSummaryPanel({ meetingId }: { meetingId: string }) {
  const { showError, showSuccess } = useToast();
  const [email, setEmail] = useState("");
  const [sending, setSending] = useState(false);
  const [formError, setFormError] = useState("");

  const emailError = useMemo(() => validateEmail(email), [email]);
  const canSend = !emailError && !sending;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError("");

    if (emailError) {
      setFormError(emailError);
      return;
    }

    setSending(true);
    try {
      await sendMeetingSummaryEmail(meetingId, email.trim());
      setEmail("");
      showSuccess("Summary email sent.");
    } catch (requestError) {
      const message =
        requestError instanceof ApiError
          ? requestError.detail
          : "Unable to send summary email.";
      setFormError(message);
      showError(message);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="meeting-panel email-panel rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="meeting-section-title"><span className="meeting-section-icon violet">↗</span><div><p>SHARE THE RECAP</p><h2>Email summary</h2></div></div>
      <form className="mt-4 space-y-3" onSubmit={handleSubmit}>
        <label className="block">
          <span className="sr-only">Recipient email</span>
          <input
            className="h-11 w-full rounded-lg border border-zinc-300 bg-white px-3 text-sm outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
            onChange={(event) => {
              setEmail(event.target.value);
              setFormError("");
            }}
            placeholder="name@example.com"
            type="email"
            value={email}
          />
        </label>
        {formError ? (
          <div className="meeting-form-error rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            {formError}
          </div>
        ) : null}
        <button
          className="h-11 w-full rounded-lg bg-zinc-950 px-4 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-300"
          disabled={!canSend}
          type="submit"
        >
          {sending ? "Sending..." : "Send summary"}
        </button>
      </form>
    </div>
  );
}

function TranscriptOnlyMeeting({
  transcriptData,
}: {
  transcriptData: MeetingTranscriptResponse;
}) {
  return (
    <div className="meeting-panel transcript-panel rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="meeting-section-title"><span className="meeting-section-icon cyan">≋</span><div><p>THE FULL RECORD</p><h2>Transcript</h2></div></div>
      <div className="mt-4 max-h-[36rem] space-y-4 overflow-y-auto pr-2">
        {transcriptData.raw_transcript_json.map((segment, index) => (
          <TranscriptRow key={`${segment.start_time}-${index}`} segment={segment} />
        ))}
      </div>
    </div>
  );
}

function validateEmail(value: string) {
  if (!value.trim()) {
    return "Enter an email address.";
  }
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
    ? ""
    : "Enter a valid email address.";
}

function TranscriptRow({ segment }: { segment: TranscriptSegment }) {
  return (
    <article className="transcript-row grid gap-2 rounded-lg border border-zinc-200 p-3 sm:grid-cols-[8rem_1fr]">
      <div>
        <p className="text-sm font-semibold text-zinc-950">{segment.speaker}</p>
        <p className="mt-1 font-mono text-xs text-zinc-500">
          {formatTimestamp(segment.start_time)} - {formatTimestamp(segment.end_time)}
        </p>
      </div>
      <p className="text-sm leading-6 text-zinc-700">{segment.text}</p>
    </article>
  );
}

function ProcessingState({ status }: { status: Meeting["status"] }) {
  return (
    <div className="processing-layout grid gap-6 lg:grid-cols-[1fr_22rem]">
      <div className="meeting-panel processing-panel rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        <div className="processing-indicator" aria-hidden="true"><span /><span /><span /><span /><span /><span /><span /></div>
        <h2 className="text-lg font-semibold">Summary is being prepared</h2>
        <p className="mt-2 text-sm leading-6 text-zinc-600">
          Current status: {status.split("_").join(" ")}. This page will update
          automatically.
        </p>
        <div className="mt-6 space-y-3">
          <Skeleton className="h-4 w-11/12" />
          <Skeleton className="h-4 w-10/12" />
          <Skeleton className="h-4 w-8/12" />
        </div>
      </div>
      <div className="meeting-panel processing-side rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        <Skeleton className="h-5 w-32" />
        <div className="mt-5 space-y-3">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      </div>
    </div>
  );
}

function FailedState({
  retrying,
  transcriptData,
  onRetry,
}: {
  retrying: boolean;
  transcriptData: MeetingTranscriptResponse | null;
  onRetry: () => void;
}) {
  return (
    <div className="flex flex-col gap-6">
      <div className="meeting-failure-panel rounded-lg border border-red-200 bg-red-50 p-5">
        <h2 className="text-lg font-semibold text-red-950">Processing failed</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-red-800">
          Something went wrong while processing this meeting. You can retry the
          transcription pipeline now.
        </p>
        <button
          className="mt-5 h-10 rounded-lg bg-red-700 px-4 text-sm font-medium text-white transition hover:bg-red-800 disabled:cursor-not-allowed disabled:bg-red-300"
          disabled={retrying}
          onClick={onRetry}
          type="button"
        >
          {retrying ? "Retrying..." : "Retry processing"}
        </button>
      </div>
      {transcriptData ? <TranscriptOnlyMeeting transcriptData={transcriptData} /> : null}
    </div>
  );
}

function ErrorPanel({ message }: { message: string }) {
  return (
    <div className="meeting-error-panel rounded-lg border border-red-200 bg-red-50 p-5 text-sm text-red-800">
      {message}
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="mt-3 h-4 w-40" />
      </div>
      <ProcessingState status="processing" />
    </div>
  );
}
