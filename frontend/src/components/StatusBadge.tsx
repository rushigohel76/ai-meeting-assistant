import type { MeetingStatus } from "../lib/api";
import { getStatusLabel } from "../lib/meetings";

const statusClasses: Record<MeetingStatus, string> = {
  pending: "border-amber-200 bg-amber-50 text-amber-800",
  bot_joining: "border-amber-200 bg-amber-50 text-amber-800",
  in_progress: "border-yellow-200 bg-yellow-50 text-yellow-800",
  processing: "border-yellow-200 bg-yellow-50 text-yellow-800",
  completed: "border-emerald-200 bg-emerald-50 text-emerald-800",
  failed: "border-red-200 bg-red-50 text-red-800",
};

export function StatusBadge({ status }: { status: MeetingStatus }) {
  return (
    <span
      className={[
        "inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium",
        statusClasses[status],
      ].join(" ")}
    >
      {getStatusLabel(status)}
    </span>
  );
}
