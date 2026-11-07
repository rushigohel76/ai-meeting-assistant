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
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"all" | "active" | "completed" | "failed">("all");

  const hasActiveMeetings = useMemo(
    () => meetings.some((meeting) => isActiveStatus(meeting.status)),
    [meetings],
  );
  const completedCount = meetings.filter((meeting) => meeting.status === "completed").length;
  const activeCount = meetings.filter((meeting) => isActiveStatus(meeting.status)).length;
  const filteredMeetings = meetings.filter((meeting) => {
    const matchesSearch = `${getMeetingTitle(meeting)} ${meeting.meeting_url}`
      .toLowerCase()
      .includes(search.trim().toLowerCase());
    const matchesFilter = filter === "all"
      || (filter === "active" && isActiveStatus(meeting.status))
      || meeting.status === filter;
    return matchesSearch && matchesFilter;
  });

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
    <AppLayout variant="dashboard">
      <section className="dashboard-page">
        <div className="dashboard-heading">
          <div>
            <p className="dashboard-eyebrow"><span className="dashboard-eyebrow-dot" /> YOUR WORKSPACE</p>
            <h1>Good to see you<span>.</span></h1>
            <p className="dashboard-subtitle">All your conversations, organized and ready to move work forward.</p>
          </div>
          <div className="dashboard-date"><span className="dashboard-date-icon">◷</span>{new Intl.DateTimeFormat(undefined, { weekday: "long", month: "long", day: "numeric" }).format(new Date())}</div>
        </div>

        <div className="dashboard-stats">
          <article className="dashboard-stat dashboard-stat-primary">
            <div className="dashboard-stat-icon">◉</div>
            <div><span>Total meetings</span><strong>{loadingMeetings ? "—" : meetings.length}</strong></div>
            <small>Captured in your workspace</small>
          </article>
          <article className="dashboard-stat">
            <div className="dashboard-stat-icon dashboard-stat-icon-cyan">⌁</div>
            <div><span>In progress</span><strong>{loadingMeetings ? "—" : activeCount}</strong></div>
            <small>{activeCount ? "MOM is working on these" : "Nothing processing right now"}</small>
          </article>
          <article className="dashboard-stat">
            <div className="dashboard-stat-icon dashboard-stat-icon-violet">✦</div>
            <div><span>Ready to revisit</span><strong>{loadingMeetings ? "—" : completedCount}</strong></div>
            <small>Meetings with completed notes</small>
          </article>
        </div>

        <section className="dashboard-capture">
          <div className="capture-ornament" aria-hidden="true"><span /><span /><span /><span /><span /><span /><span /></div>
          <div className="capture-heading">
            <div className="capture-icon" aria-hidden="true">＋</div>
            <div>
              <p className="capture-eyebrow">START A NEW CAPTURE</p>
              <h2>Bring the conversation in.</h2>
              <p>Drop a meeting link and MOM will take care of the notes.</p>
            </div>
          </div>
          <form className="capture-form" onSubmit={handleCreateMeeting}>
            <label className="capture-link-field">
              <span className="sr-only">Meeting link</span>
              <span className="capture-link-icon" aria-hidden="true">↗</span>
              <input onChange={(event) => setMeetingUrl(event.target.value)} placeholder="Paste a Google Meet, Zoom, or Teams link" type="url" value={meetingUrl} />
            </label>
            <label className="capture-title-field">
              <span className="sr-only">Meeting title</span>
              <input onChange={(event) => setTitle(event.target.value)} placeholder="Name this meeting (optional)" type="text" value={title} />
            </label>
            <button disabled={creating} type="submit"><span>{creating ? "Connecting..." : "Capture meeting"}</span><span aria-hidden="true">↗</span></button>
          </form>
          {formError && <div className="dashboard-error" role="alert">{formError}</div>}
          <div className="capture-trust"><span>●</span> Your meeting stays private to your workspace</div>
        </section>

        <section className="dashboard-meetings">
          <div className="meetings-heading">
            <div>
              <p className="dashboard-eyebrow">YOUR LIBRARY</p>
              <h2>Recent meetings <span>{meetings.length}</span></h2>
            </div>
            {hasActiveMeetings && <span className="auto-update"><i /> Live updates on</span>}
          </div>
          <div className="meetings-toolbar">
            <div className="meeting-filters" role="group" aria-label="Filter meetings">
              {(["all", "active", "completed", "failed"] as const).map((item) => (
                <button aria-pressed={filter === item} className={filter === item ? "selected" : ""} key={item} onClick={() => setFilter(item)} type="button">
                  {item === "all" ? "All meetings" : item === "active" ? "In progress" : item === "completed" ? "Completed" : "Needs attention"}
                </button>
              ))}
            </div>
            <label className="meeting-search"><span aria-hidden="true">⌕</span><span className="sr-only">Search meetings</span><input onChange={(event) => setSearch(event.target.value)} placeholder="Search meetings" type="search" value={search} /></label>
          </div>

          {loadingMeetings ? <MeetingListSkeleton /> : meetings.length === 0 ? <EmptyMeetings /> : filteredMeetings.length === 0 ? (
            <div className="meetings-no-results">No meetings match this view. Try another filter or search.</div>
          ) : (
            <div className="meeting-list">
              {filteredMeetings.map((meeting) => (
                <Link className="meeting-row" key={meeting.id} to={`/meetings/${meeting.id}`}>
                  <span className="meeting-row-mark" aria-hidden="true">◈</span>
                  <span className="meeting-row-main">
                    <strong>{getMeetingTitle(meeting)}</strong>
                    <small><span>{formatDateTime(meeting.created_at)}</span><i />{getMeetingHost(meeting.meeting_url)}</small>
                  </span>
                  <StatusBadge status={meeting.status} />
                  <span className="meeting-row-arrow" aria-hidden="true">↗</span>
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
    <div className="dashboard-empty">
      <div className="dashboard-empty-mark" aria-hidden="true">⌁</div>
      <h3>No meetings yet</h3>
      <p>
        Paste a meeting link above and MOM will send a bot to capture the conversation.
      </p>
    </div>
  );
}

function MeetingListSkeleton() {
  return (
    <div className="meeting-list">
      {[0, 1, 2].map((item) => (
        <div className="dashboard-skeleton" key={item}>
          <div />
          <div />
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

function getMeetingHost(value: string) {
  try {
    return new URL(value).hostname.replace(/^www\./, "");
  } catch {
    return "Meeting";
  }
}
