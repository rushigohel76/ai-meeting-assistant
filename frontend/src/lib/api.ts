const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

type AuthRuntime = {
  getAccessToken: () => string | null;
  setAccessToken: (token: string | null) => void;
  refreshAccessToken: () => Promise<string | null>;
  logout: () => void;
};

let authRuntime: AuthRuntime | null = null;
let currentAccessToken: string | null = null;

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export type TokenResponse = {
  access_token: string;
  refresh_token?: string;
  token_type: string;
};

export type MeetingStatus =
  | "pending"
  | "bot_joining"
  | "in_progress"
  | "processing"
  | "completed"
  | "failed";

export type Meeting = {
  id: string;
  user_id: string;
  meeting_url: string;
  title: string | null;
  status: MeetingStatus;
  recall_bot_id: string | null;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
};

export type TranscriptSegment = {
  speaker: string;
  text: string;
  start_time: number;
  end_time: number;
};

export type Summary = {
  id: string;
  meeting_id: string;
  summary_text: string;
  key_points: string[];
  action_items: Array<{ task: string; owner: string | null }>;
  decisions: string[];
  created_at: string;
};

export type MeetingSummaryResponse = {
  summary: Summary;
  transcript: {
    id: string;
    meeting_id: string;
    raw_transcript_json: TranscriptSegment[];
    created_at: string;
  };
};

export type MeetingTranscriptResponse = MeetingSummaryResponse["transcript"];

export function configureApiAuth(runtime: AuthRuntime) {
  authRuntime = runtime;
  currentAccessToken = runtime.getAccessToken();
}

export function setApiAccessToken(token: string | null) {
  currentAccessToken = token;
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  retryOnUnauthorized = true,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }

  const accessToken = currentAccessToken ?? authRuntime?.getAccessToken();
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  if (response.status === 401 && retryOnUnauthorized && authRuntime) {
    const refreshedToken = await authRuntime.refreshAccessToken();
    if (refreshedToken) {
      currentAccessToken = refreshedToken;
      return apiRequest<T>(path, options, false);
    }

    currentAccessToken = null;
    authRuntime.logout();
  }

  if (!response.ok) {
    throw new ApiError(response.status, await getErrorDetail(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function refreshSession(): Promise<TokenResponse> {
  return rawApiRequest<TokenResponse>("/api/auth/refresh", {
    method: "POST",
  });
}

export async function loginRequest(email: string, password: string): Promise<TokenResponse> {
  return rawApiRequest<TokenResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function passwordResetRequest(email: string): Promise<{ detail: string }> {
  return rawApiRequest<{ detail: string }>("/api/auth/password-reset/request", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function passwordResetConfirm(
  email: string,
  otp: string,
  newPassword: string,
): Promise<{ detail: string }> {
  return rawApiRequest<{ detail: string }>("/api/auth/password-reset/confirm", {
    method: "POST",
    body: JSON.stringify({ email, otp, new_password: newPassword }),
  });
}

export async function signupRequest(
  email: string,
  password: string,
  fullName: string,
): Promise<TokenResponse> {
  return rawApiRequest<TokenResponse>("/api/auth/signup", {
    method: "POST",
    body: JSON.stringify({
      email,
      password,
      full_name: fullName || null,
    }),
  });
}

export async function createMeeting(meetingUrl: string, title?: string): Promise<Meeting> {
  return apiRequest<Meeting>("/api/meetings", {
    method: "POST",
    body: JSON.stringify({
      meeting_url: meetingUrl,
      title: title?.trim() || null,
    }),
  });
}

export async function listMeetings(limit = 50, offset = 0): Promise<Meeting[]> {
  return apiRequest<Meeting[]>(`/api/meetings?limit=${limit}&offset=${offset}`);
}

export async function getMeeting(meetingId: string): Promise<Meeting> {
  return apiRequest<Meeting>(`/api/meetings/${meetingId}`);
}

export async function getMeetingSummary(meetingId: string): Promise<MeetingSummaryResponse> {
  return apiRequest<MeetingSummaryResponse>(`/api/meetings/${meetingId}/summary`);
}

export async function getMeetingTranscript(meetingId: string): Promise<MeetingTranscriptResponse> {
  return apiRequest<MeetingTranscriptResponse>(`/api/meetings/${meetingId}/transcript`);
}

export async function retryMeetingTranscription(meetingId: string): Promise<{ status: string }> {
  return apiRequest<{ status: string }>(`/api/meetings/${meetingId}/transcribe`, {
    method: "POST",
  });
}

export async function sendMeetingSummaryEmail(
  meetingId: string,
  email: string,
): Promise<{ status: string }> {
  return apiRequest<{ status: string }>(`/api/meetings/${meetingId}/summary/email`, {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

async function rawApiRequest<T>(path: string, options: RequestInit): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  if (!response.ok) {
    throw new ApiError(response.status, await getErrorDetail(response));
  }

  return (await response.json()) as T;
}

async function getErrorDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") {
      return body.detail;
    }
    if (Array.isArray(body.detail)) {
      return body.detail
        .map((item: { msg?: string }) => item?.msg)
        .filter(Boolean)
        .join(", ");
    }
  } catch {
    return "Something went wrong. Please try again.";
  }

  return "Something went wrong. Please try again.";
}
