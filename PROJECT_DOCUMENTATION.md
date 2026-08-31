# MOM Project Documentation

This document explains the full-stack scaffold that has been created so far: what each part does, how the frontend and backend connect, how configuration works, how the database layer is structured, and what happens when the app runs.

At this stage, the project contains only scaffolding, configuration, database models, migrations, schemas, and a health check. No business logic has been added yet.

## 1. High-Level Architecture

The project has two main applications:

```text
MOM/
  backend/   FastAPI API server
  frontend/  React + Vite + Tailwind web app
```

The intended runtime flow is:

```text
Browser
  |
  | opens frontend at http://localhost:5173
  v
React frontendt
  |
  | calls API using VITE_API_BASE_URL
  v
FastAPI backend at http://localhost:8000
  |
  | reads/writes data through SQLAlchemy
  v
PostgreSQL database
```

Right now, the frontend does not yet call backend business APIs. It only reads and displays the configured backend URL. The backend exposes health, auth, meeting, webhook, and transcription-trigger endpoints.

## 2. Backend Overview

The backend is in:

```text
backend/
```

It uses:

- FastAPI for the API server
- Pydantic Settings for environment-based configuration
- SQLAlchemy async ORM for database models and sessions
- Alembic for database migrations
- PostgreSQL as the database
- asyncpg as the PostgreSQL async driver

Backend source layout:

```text
backend/app/
  api/       API route definitions
  core/      application configuration
  db/        database base class and session setup
  models/    SQLAlchemy ORM models
  schemas/   Pydantic request/response schemas
  services/  future business/service logic
  main.py    FastAPI application entry point
```

## 3. Backend Startup Flow

The backend starts from:

```text
backend/app/main.py
```

When the server starts:

1. `get_settings()` loads environment variables using `pydantic-settings`.
2. A FastAPI app is created with the title `MOM API`.
3. CORS middleware is configured from `CORS_ORIGINS`.
4. API routes are included from `app.api.router`.

The main app currently includes:

```text
GET /health
POST /api/auth/signup
POST /api/auth/login
POST /api/auth/refresh
POST /api/meetings
GET /api/meetings
GET /api/meetings/{meeting_id}
GET /api/meetings/{meeting_id}/summary
POST /api/meetings/{meeting_id}/transcribe
POST /api/webhooks/recall
```

## 4. Environment Configuration

Backend environment variables are listed in:

```text
.env.example
```

Required backend variables:

Summarization uses Gemini when `GEMINI_API_KEY` is set. Anthropic settings are only a fallback.

```text
DATABASE_URL
MEETING_BAAS_API_KEY
MEETING_BAAS_BASE_URL
MEETING_BAAS_WEBHOOK_SECRET
WEBHOOK_BASE_URL
DEEPGRAM_API_KEY
DEEPGRAM_BASE_URL
MAX_TRANSCRIPTION_AUDIO_DURATION_SECONDS
ANTHROPIC_API_KEY
ANTHROPIC_BASE_URL
ANTHROPIC_MODEL
ANTHROPIC_MAX_OUTPUT_TOKENS
GEMINI_API_KEY
GEMINI_BASE_URL
GEMINI_MODEL
GEMINI_MAX_OUTPUT_TOKENS
MAX_SUMMARY_CHUNK_CHARS
JWT_SECRET_KEY
RESEND_API_KEY
RESEND_BASE_URL
RESEND_FROM_EMAIL
FRONTEND_BASE_URL
CORS_ORIGINS
```

The backend loads these through:

```text
backend/app/core/config.py
```

Important detail:

- Secrets are not hardcoded in the code.
- Real `.env` files are ignored by git.
- `.env.example` contains placeholders only.

Example backend database URL:

```text
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mom
```

The `+asyncpg` part matters because the backend uses SQLAlchemy's async engine.

`RECALL_AI_BASE_URL` defaults to:

```text
https://us-east-1.recall.ai/api/v1
```

Override it if your Recall.ai workspace uses a different region.

## 5. Database Connection

Database setup is in:

```text
backend/app/db/session.py
```

It creates:

- an async SQLAlchemy engine
- an async session factory
- a `get_db()` dependency for FastAPI routes

Routes that need the database can request a session like this:

```python
async def route(db: AsyncSession = Depends(get_db)):
    ...
```

The health check already uses this pattern.

## 6. Health Check Endpoint

The health check route is in:

```text
backend/app/api/health.py
```

Endpoint:

```text
GET /health
```

What it does:

1. FastAPI receives the request.
2. The route asks for a database session using `get_db()`.
3. The backend runs:

```sql
SELECT 1
```

4. If PostgreSQL responds, the API returns:

```json
{
  "status": "ok",
  "database": "ok"
}
```

5. If the database connection fails, it returns HTTP `503 Service Unavailable`.

This confirms the backend is running and can reach the database.

## 7. SQLAlchemy Models

The database models are in:

```text
backend/app/models/
```

Current models:

```text
User
Meeting
Transcript
Summary
```

### User

Represents an application user.

Fields:

- `id`: UUID primary key
- `email`: unique, indexed, required
- `hashed_password`: required
- `full_name`: optional
- `created_at`: timestamp
- `updated_at`: timestamp

Important security rule:

Plaintext passwords should never be stored. The database stores only `hashed_password`.

Relationship:

```text
User.meetings
```

A user can have many meetings.

### Meeting

Represents a meeting submitted by a user.

Fields:

- `id`: UUID primary key
- `user_id`: foreign key to `users.id`
- `meeting_url`: Meet/Zoom link pasted by the user
- `title`: optional user label
- `status`: meeting processing status
- `recall_bot_id`: optional ID returned by Recall.ai
- `started_at`: optional timestamp
- `ended_at`: optional timestamp
- `created_at`: timestamp

Statuses:

```text
pending
bot_joining
in_progress
processing
completed
failed
```

Relationships:

```text
Meeting.user
Meeting.transcript
Meeting.summary
```

A meeting belongs to one user. A meeting can have one transcript and one summary.

### Transcript

Stores the full transcript for a meeting.

Fields:

- `id`: UUID primary key
- `meeting_id`: foreign key to `meetings.id`
- `raw_transcript_json`: JSONB speaker-labeled transcript data
- `created_at`: timestamp

Relationship:

```text
Transcript.meeting
```

This is one-to-one with `Meeting`.

### Summary

Stores the generated meeting summary.

Fields:

- `id`: UUID primary key
- `meeting_id`: foreign key to `meetings.id`
- `summary_text`: full summary text
- `key_points`: JSONB array of strings
- `action_items`: JSONB array of `{task, owner}`
- `decisions`: JSONB array of strings
- `created_at`: timestamp

Relationship:

```text
Summary.meeting
```

This is one-to-one with `Meeting`.

## 8. Delete Behavior

Foreign keys use `ON DELETE CASCADE`.

That means:

```text
Delete User
  -> deletes that user's Meetings
     -> deletes each Meeting's Transcript
     -> deletes each Meeting's Summary
```

This prevents orphaned meeting, transcript, or summary records.

## 9. Database Migration

The migration file is:

```text
backend/alembic/versions/20260715_0001_create_users_meetings_transcripts_summaries.py
```

It creates:

- `users` table
- `meetings` table
- `transcripts` table
- `summaries` table
- `meeting_status` PostgreSQL enum
- indexes for email, meeting user ID, transcript meeting ID, and summary meeting ID
- cascade foreign keys

To apply the migration:

```bash
cd backend
alembic upgrade head
```

To roll it back:

```bash
cd backend
alembic downgrade -1
```

## 10. Pydantic Schemas

Schemas are in:

```text
backend/app/schemas/
```

Schemas are used for request and response validation.

Current schema files:

```text
user.py
meeting.py
transcript.py
summary.py
```

Important password behavior:

- `UserCreate` accepts `password`.
- `UserUpdate` can accept `password`.
- `UserRead` does not expose `password`.
- `UserRead` does not expose `hashed_password`.

This keeps password hashes out of API responses.

## 11. Frontend Overview

The frontend is in:

```text
frontend/
```

It uses:

- React
- TypeScript
- Vite
- Tailwind CSS

Main frontend files:

```text
frontend/src/main.tsx
frontend/src/App.tsx
frontend/src/index.css
frontend/vite.config.ts
frontend/tailwind.config.js
```

## 12. Frontend Startup Flow

The browser loads:

```text
frontend/index.html
```

That file loads:

```text
frontend/src/main.tsx
```

`main.tsx` mounts the React app into:

```html
<div id="root"></div>
```

The rendered app is:

```text
frontend/src/App.tsx
```

Right now, `App.tsx` reads:

```text
import.meta.env.VITE_API_BASE_URL
```

and displays the configured API base URL.

## 13. Frontend Environment Configuration

Frontend environment example:

```text
frontend/.env.example
```

Required frontend variable:

```text
VITE_API_BASE_URL=http://localhost:8000
```

Vite only exposes frontend environment variables that start with `VITE_`.

When the frontend later calls the backend, it should use:

```text
VITE_API_BASE_URL
```

Example future request:

```ts
fetch(`${import.meta.env.VITE_API_BASE_URL}/health`)
```

## 14. How Frontend And Backend Connect

In development:

```text
Frontend: http://localhost:5173
Backend:  http://localhost:8000
```

The frontend knows where the backend is because of:

```text
frontend/.env
```

with:

```text
VITE_API_BASE_URL=http://localhost:8000
```

The backend allows requests from the frontend because of:

```text
CORS_ORIGINS=http://localhost:5173
```

in the backend `.env`.

So the connection works like this:

```text
React app
  reads VITE_API_BASE_URL
  sends HTTP request to backend

FastAPI backend
  checks CORS settings
  handles request
  uses database if needed
  sends JSON response

React app
  receives JSON
  updates UI
```

## 15. How To Run Everything Locally

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
```

Edit `backend/.env` with real values.

Then run:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

Backend URL:

```text
http://localhost:8000
```

Health check:

```text
http://localhost:8000/health
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Frontend URL:

```text
http://localhost:5173
```

## 16. Current Request Flow Example

The one complete backend flow right now is the health check.

```text
Browser or API client
  |
  | GET http://localhost:8000/health
  v
FastAPI app
  |
  | routes request through app.api.router
  v
health_check()
  |
  | gets AsyncSession from get_db()
  v
PostgreSQL
  |
  | runs SELECT 1
  v
FastAPI response
```

Success response:

```json
{
  "status": "ok",
  "database": "ok"
}
```

Failure response:

```json
{
  "detail": "Database connection failed"
}
```

with HTTP status `503`.

## 17. Authentication And Meeting Bot Flow

Authentication now uses JWT access tokens and refresh tokens.

Auth endpoints:

```text
POST /api/auth/signup
POST /api/auth/login
POST /api/auth/refresh
```

Meeting bot endpoints:

```text
POST /api/meetings
GET /api/meetings
GET /api/meetings/{meeting_id}
POST /api/meetings/{meeting_id}/transcribe
POST /api/webhooks/recall
```

All meeting endpoints are protected with `get_current_user`, which validates the JWT access token from the `Authorization: Bearer ...` header and loads the user from the database.

Creating a meeting works like this:

```text
Frontend
  |
  | POST /api/meetings
  | Authorization: Bearer ACCESS_TOKEN
  | { meeting_url, title }
  v
FastAPI
  |
  | validates the URL is Google Meet, Zoom, or Microsoft Teams
  | creates Meeting(status=pending)
  v
Recall.ai service
  |
  | POST /bot/
  | Authorization: Token RECALL_AI_API_KEY
  v
Recall.ai
  |
  | returns bot id
  v
FastAPI
  |
  | stores recall_bot_id
  | updates Meeting(status=bot_joining)
  v
Frontend receives created meeting
```

If Recall.ai fails or times out, the backend marks the meeting as `failed` and returns a clear `502` error instead of crashing.

The Recall integration is wrapped in:

```text
backend/app/services/recall.py
```

It uses exponential backoff retries with a maximum of 3 attempts for transient failures.

Recall.ai recording-ready webhooks are handled by:

```text
backend/app/api/webhooks.py
```

This endpoint is public because Recall.ai must be able to call it without a user JWT, but it is still protected by HMAC signature verification. The backend verifies `webhook-id`, `webhook-timestamp`, and `webhook-signature` against `RECALL_WEBHOOK_SECRET` using the raw request body before parsing or trusting the payload.

When a valid `recording.done` or `bot.done` webhook arrives:

```text
Recall.ai
  |
  | POST /api/webhooks/recall
  | signed with webhook headers
  v
FastAPI
  |
  | verifies HMAC signature before JSON parsing
  | finds Meeting by recall_bot_id
  | skips duplicates if already processing/completed/failed
  | sets status=processing and ended_at
  v
Background task
  |
  | runs the transcription pipeline
```

The webhook handler logs only the event type and meeting id. It does not log the full webhook payload because future payloads may contain sensitive recording or transcript URLs.

The transcription pipeline is implemented in:

```text
backend/app/services/transcription.py
```

It works like this:

```text
Meeting status is processing
  |
  | fetch fresh Recall.ai bot recording data
  | extract media_shortcuts.audio_mixed.data.download_url
  | reject audio longer than MAX_TRANSCRIPTION_AUDIO_DURATION_SECONDS
  v
Deepgram
  |
  | POST /v1/listen
  | Authorization: Token DEEPGRAM_API_KEY
  | diarize=true, utterances=true, punctuate=true
  v
Backend
  |
  | parses speaker-labeled utterances
  | saves Transcript.raw_transcript_json
  | runs the summarization pipeline
```

The saved transcript structure is:

```json
[
  {
    "speaker": "Speaker 1",
    "text": "Example sentence.",
    "start_time": 0.0,
    "end_time": 2.4
  }
]
```

For manual testing without waiting for a live webhook, call:

```text
POST /api/meetings/{meeting_id}/transcribe
Authorization: Bearer ACCESS_TOKEN
```

This endpoint verifies the authenticated user owns the meeting, then queues transcription as a background task.

The summarization pipeline is implemented in:

```text
backend/app/services/summarization.py
```

It works like this:

```text
Transcript.raw_transcript_json
  |
  | format as "Speaker N: text"
  | chunk if longer than MAX_SUMMARY_CHUNK_CHARS
  v
Configured LLM provider
  |
  | Gemini: POST /v1beta/models/{GEMINI_MODEL}:generateContent
  | Anthropic fallback: POST /v1/messages
  | system prompt requires JSON only
  v
Backend
  |
  | parses and validates JSON
  | retries once with stricter JSON instructions if malformed
  | saves Summary
  | sets Meeting.status=completed
  | sends summary email notification
```

The protected completed-meeting endpoint is:

```text
GET /api/meetings/{meeting_id}/summary
Authorization: Bearer ACCESS_TOKEN
```

It returns both the `Summary` and `Transcript` after verifying the authenticated user owns the meeting.

## 18. What Has Not Been Built Yet

The following pieces are intentionally not implemented yet:

- additional Recall.ai webhook handling for bot status changes
- frontend auth screens
- frontend meeting creation/list/detail screens
- API calls from frontend to backend

The current project is ready for those features to be added on top of a clean foundation.

## 19. Suggested Next Build Steps

A practical next order would be:

1. Handle additional Recall.ai bot status webhooks and update meeting status over time.
2. Add transcript review/editing workflows if needed.
3. Add frontend summary views.
4. Add frontend auth screens.
5. Add frontend screens for meetings, transcripts, summaries, and action items.
6. Connect the frontend to the auth and meeting APIs.
