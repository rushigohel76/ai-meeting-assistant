# MOM Project Documentation

MOM is a full-stack meeting assistant. Users create an account, submit a Google Meet, Zoom, or Microsoft Teams link, and the backend asks Meeting BaaS to capture the meeting. When the recording is ready, the backend transcribes it with Deepgram, generates a structured summary with Gemini or Anthropic, stores the results, and attempts to send a summary email.

This document describes the implementation currently in this repository.

## 1. Architecture

```text
Browser (React app, normally http://localhost:5173)
        | HTTP requests, access-token authorization
        v
FastAPI backend (normally http://localhost:8000)
        | SQLAlchemy async sessions
        v
PostgreSQL

FastAPI <-> Meeting BaaS (bot creation, recording lookup, bot leave)
FastAPI <-> Deepgram (audio transcription)
FastAPI <-> Gemini or Anthropic (summary generation)
FastAPI -> Resend or configured SMTP server (email)
Meeting BaaS -> FastAPI webhook (/api/webhooks/meetingbaas)
```

The frontend is a working application, not just a configuration placeholder. It uses `VITE_API_BASE_URL` from `frontend/.env` to locate the API. The backend's `CORS_ORIGINS` setting must allow the browser origin.

## 2. Repository Layout

```text
backend/app/api/       FastAPI routes and dependencies
backend/app/core/      Settings, JWT security, rate limiting, webhook checks
backend/app/db/        Async SQLAlchemy engine and session dependency
backend/app/models/    User, meeting, transcript, and summary ORM models
backend/app/schemas/   Pydantic request and response models
backend/app/services/  Auth, meeting provider, transcription, summaries, and email
backend/alembic/       Database migrations
backend/tests/         Backend tests
frontend/src/pages/    Login, signup, password reset, dashboard, meeting detail
frontend/src/context/  Authentication and toast state
frontend/src/lib/      API client and meeting helpers
```

## 3. Backend Startup and API Routes

The FastAPI application is created in `backend/app/main.py`. It loads settings, configures CORS and rate-limit handling, then includes the API router. The backend has no separate `/api` prefix for health.

| Method | Path | Purpose | Authentication |
| --- | --- | --- | --- |
| `GET` | `/health` | Check database connectivity | Public |
| `POST` | `/api/auth/signup` | Create an account and issue tokens | Public |
| `POST` | `/api/auth/login` | Log in and issue tokens | Public; rate limited |
| `POST` | `/api/auth/refresh` | Issue a new access token using the refresh cookie | Cookie |
| `POST` | `/api/auth/logout` | Clear the refresh cookie | Public |
| `POST` | `/api/auth/password-reset/request` | Request a one-time reset code by email | Public |
| `POST` | `/api/auth/password-reset/confirm` | Verify the code and change the password | Public |
| `POST` | `/api/meetings` | Create a meeting and request a capture bot | User token |
| `GET` | `/api/meetings` | List the current user's meetings (`limit`, `offset`) | User token |
| `GET` | `/api/meetings/{meeting_id}` | Get one owned meeting | User token |
| `DELETE` | `/api/meetings/{meeting_id}` | Delete an eligible meeting; stop its active bot first | User token |
| `GET` | `/api/meetings/{meeting_id}/summary` | Get the summary and transcript for a completed meeting | User token |
| `POST` | `/api/meetings/{meeting_id}/summary/email` | Email a completed summary to the requested address | User token |
| `GET` | `/api/meetings/{meeting_id}/transcript` | Get the transcript | User token |
| `POST` | `/api/meetings/{meeting_id}/transcribe` | Queue a transcription retry/manual run | User token |
| `POST` | `/api/webhooks/meetingbaas` | Receive Meeting BaaS completion callbacks | Provider secret header |

Meeting routes verify ownership: a user cannot read, modify, or delete another user's meeting. Meeting links are validated as HTTPS Google Meet, Zoom, or Teams URLs. Meeting list and detail pages poll while a meeting is active.

## 4. Authentication

Passwords are hashed with bcrypt; the database never stores plaintext passwords. Signup and login return a short-lived JWT access token and set an HTTP-only refresh-token cookie. Access tokens last 20 minutes; refresh tokens last 7 days. The frontend keeps the access token in application memory, sends it as a Bearer token, and uses the cookie to refresh a session. API requests include credentials for cookie handling.

Signup and password-reset passwords must be at least eight characters and contain a number. Password-reset codes are stored as hashes and expire after 15 minutes. Login and refresh endpoints are rate limited.

## 5. Meeting Capture and Processing

### Create a meeting

1. The signed-in frontend submits `meeting_url` and an optional `title` to `POST /api/meetings`.
2. The backend validates the supported meeting URL and creates a database row with status `pending`.
3. The backend calls Meeting BaaS to create a bot and registers the callback URL as `${WEBHOOK_BASE_URL}/api/webhooks/meetingbaas`.
4. On success it stores the returned bot ID in the historical `recall_bot_id` column and changes the status to `bot_joining`. Provider errors mark the meeting `failed` and return an error response. Transient Meeting BaaS errors are retried up to three attempts.

The model column remains named `recall_bot_id` for compatibility, although the current integration is implemented in `services/meetingbaas.py` and uses Meeting BaaS configuration.

### Completion webhook and transcription

The webhook endpoint checks the configured shared secret against the `x-mb-secret` or `x-meeting-baas-api-key` header before trusting the body. The secret is `MEETING_BAAS_WEBHOOK_SECRET` when set, otherwise `MEETING_BAAS_API_KEY`. It accepts the completion event names `bot.completed`, `complete`, and `meeting.completed`; other events or unknown bots are ignored. Repeated callbacks for meetings already processing, completed, or failed are ignored.

For a recognized completion event, the backend marks the meeting `processing` and schedules the pipeline with FastAPI `BackgroundTasks`:

1. Fetch recording information from Meeting BaaS.
2. Reject recordings longer than `MAX_TRANSCRIPTION_AUDIO_DURATION_SECONDS` when a duration is available.
3. Send the audio URL to Deepgram with diarization, utterances, punctuation, and smart formatting enabled.
4. Store speaker-labeled transcript segments, including speaker, text, and start/end times.
5. Summarize the transcript and mark the meeting `completed`; processing failures mark it `failed`.

The authenticated `POST /api/meetings/{meeting_id}/transcribe` endpoint queues the same pipeline for manual retry. These background tasks run in the API process; the project does not currently configure a separate durable task queue or worker.

### Summarization and email

Gemini is selected when `GEMINI_API_KEY` is configured; otherwise the backend uses Anthropic. If neither key is available, summarization fails. Long transcripts are split at `MAX_SUMMARY_CHUNK_CHARS`, summarized in chunks, and merged. The model response is expected to be JSON containing `summary`, `key_points`, `action_items`, and `decisions`; malformed JSON triggers one stricter-format retry.

When summarization succeeds, MOM stores the summary and attempts to email it to the account owner. A delivery failure is logged and does not undo the completed summary. Users can also request an email to another address through the summary-email endpoint. Email is sent through SMTP when `SMTP_HOST` is configured; otherwise the Resend API is used.

## 6. Frontend

The frontend is a React and TypeScript single-page app built with Vite, React Router, and Tailwind CSS.

Current screens and behavior:

- Login and signup pages.
- Password-reset request and confirmation pages.
- Protected dashboard with meeting creation, list, filtering, search, status refresh, and eligible meeting deletion.
- Protected meeting detail page with processing status, transcript, completed summary, action items, decisions, summary email, retry, and deletion controls.
- Shared API client with Bearer-token handling, refresh-on-401 behavior, and cookie credentials.

`frontend/src/App.tsx` defines the routes. `frontend/src/context/AuthContext.tsx` manages the client authentication state; `frontend/src/lib/api.ts` contains the API calls.

## 7. Database

Database access is configured in `backend/app/db/session.py`. It creates an async SQLAlchemy engine and session factory. The health endpoint runs `SELECT 1` and returns `503` if the database is unavailable.

The PostgreSQL models in `backend/app/models/` are:

- **User:** UUID ID, unique email, password hash, optional full name, timestamps, and hashed password-reset code/expiry.
- **Meeting:** owner, meeting URL, optional title, status, provider bot ID (`recall_bot_id`), start/end timestamps, and creation timestamp.
- **Transcript:** one JSONB transcript per meeting. Transcript segments normally contain `speaker`, `text`, `start_time`, and `end_time`.
- **Summary:** one summary per meeting, with summary text and JSONB arrays for key points, action items (`task`, optional `owner`), and decisions.

Meeting status values are `pending`, `bot_joining`, `in_progress`, `processing`, `completed`, and `failed`. User-to-meeting, meeting-to-transcript, and meeting-to-summary relationships cascade on deletion.

Alembic migrations are in `backend/alembic/versions/`:

- `20260715_0001_create_users_meetings_transcripts_summaries.py` creates the core tables, status enum, indexes, and foreign keys.
- `20260819_0002_add_user_reset_otp.py` adds password-reset fields to users.

Apply migrations from the backend directory with `alembic upgrade head`.

## 8. Configuration

Backend settings are loaded by `backend/app/core/config.py` from environment variables and `.env` in the current working directory. The root `.env.example` documents the backend values. Required settings at startup are:

```text
DATABASE_URL
MEETING_BAAS_API_KEY
WEBHOOK_BASE_URL
DEEPGRAM_API_KEY
JWT_SECRET_KEY
RESEND_API_KEY
CORS_ORIGINS
```

Other supported settings include:

```text
MEETING_BAAS_BASE_URL                 # defaults to https://api.meetingbaas.com
MEETING_BAAS_WEBHOOK_SECRET           # optional; API key is used if omitted
DEEPGRAM_BASE_URL                     # defaults to https://api.deepgram.com
MAX_TRANSCRIPTION_AUDIO_DURATION_SECONDS
GEMINI_API_KEY, GEMINI_BASE_URL, GEMINI_MODEL, GEMINI_MAX_OUTPUT_TOKENS
ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, ANTHROPIC_MODEL, ANTHROPIC_MAX_OUTPUT_TOKENS
MAX_SUMMARY_CHUNK_CHARS
RESEND_BASE_URL, RESEND_FROM_EMAIL
SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_USE_TLS
FRONTEND_BASE_URL
```

Set either `GEMINI_API_KEY` or `ANTHROPIC_API_KEY` to enable summaries. Configure `SMTP_HOST` to use SMTP instead of Resend for email delivery. `WEBHOOK_BASE_URL` must be publicly reachable by Meeting BaaS for callbacks, such as a deployed URL or development tunnel. `DATABASE_URL` should use SQLAlchemy's async driver, for example:

```text
postgresql+asyncpg://postgres:postgres@localhost:5432/mom
```

Frontend configuration is in `frontend/.env.example`:

```text
VITE_API_BASE_URL=http://localhost:8000
```

Only variables prefixed with `VITE_` are exposed to the browser. Keep API keys and other secrets in the backend environment, never in frontend variables.

## 9. Run Locally

You need PostgreSQL and the external service credentials/configuration required by the backend.

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
# Edit .env with database, provider, email, JWT, CORS, and webhook values.
alembic upgrade head
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`; its database health check is `http://localhost:8000/health`.

### Frontend

In another terminal:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

The Vite development server is normally available at `http://localhost:5173`. Ensure the backend's `CORS_ORIGINS` includes that origin and `FRONTEND_BASE_URL` matches the frontend origin for refresh-cookie behavior and email links.

## 10. Known Implementation Boundaries

- Meeting status callbacks beyond the completion event names handled by the webhook are not implemented; the frontend refreshes active meetings by polling the API.
- The transcription/summarization work uses FastAPI in-process background tasks, not a persistent job queue.
- The app relies on live Meeting BaaS, Deepgram, LLM, and email-provider configuration for end-to-end processing.
- The `recall_bot_id` database/API field name is legacy terminology; the active provider client and environment configuration use Meeting BaaS.
