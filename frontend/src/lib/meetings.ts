import type { Meeting, MeetingStatus } from "./api";

export const activeStatuses: MeetingStatus[] = [
  "pending",
  "bot_joining",
  "in_progress",
  "processing",
];

export function isActiveStatus(status: MeetingStatus) {
  return activeStatuses.includes(status);
}

export function getMeetingTitle(meeting: Meeting) {
  return meeting.title?.trim() || getHostname(meeting.meeting_url) || "Untitled meeting";
}

export function getStatusLabel(status: MeetingStatus) {
  const labels: Record<MeetingStatus, string> = {
    pending: "Pending",
    bot_joining: "Bot joining",
    in_progress: "In progress",
    processing: "Processing",
    completed: "Completed",
    failed: "Failed",
  };
  return labels[status];
}

export function formatDateTime(value: string | null) {
  if (!value) {
    return "Not available";
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function formatTimestamp(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.floor(seconds % 60);
  return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`;
}

function getHostname(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}
