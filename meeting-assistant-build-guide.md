# AI Meeting Assistant — Module-by-Module Build Guide

**How to use this doc:** Copy each module's prompt into your AI coding tool (Claude Code, Cursor, etc.) one at a time, in order. Don't skip ahead — each module assumes the previous ones exist. After each module, actually run and test it before moving to the next. Fill in the `[bracketed]` placeholders with your real values before pasting.

---

## Module 0 — Project Setup & Environment

**Goal:** Scaffold the repo, environment config, and secrets handling correctly from the start — this is where most student projects get security wrong (hardcoded API keys committed to GitHub).

**Prompt:**
```
Set up a new full-stack project with this structure:

/backend  → FastAPI (Python 3.11+)
/frontend → React + Vite + Tailwind CSS

Requirements:
1. Backend: FastAPI project with folders: app/api, app/models, app/schemas,
   app/services, app/core, app/db
2. Use pydantic-settings to load all config from environment variables —
   no hardcoded secrets anywhere in code.
3. Create a .env.example file listing every required env var with placeholder
   values (DATABASE_URL, RECALL_AI_API_KEY, DEEPGRAM_API_KEY,
   ANTHROPIC_API_KEY, JWT_SECRET_KEY, RESEND_API_KEY, CORS_ORIGINS,
   RECALL_WEBHOOK_SECRET) but make sure actual .env is in .gitignore.
4. Set up PostgreSQL connection using SQLAlchemy + Alembic for migrations.
5. Add a health check endpoint GET /health that confirms DB connection works.
6. Frontend: Vite + React + TypeScript + Tailwind, with an .env.example for
   VITE_API_BASE_URL.
7. Add a root .gitignore covering .env, __pycache__, node_modules, .venv, dist.
8. Add a README with setup instructions (how to install deps, run migrations,
   start dev servers).

Do not proceed to write any business logic yet — this module is only
scaffolding, config, and environment setup.
```

**Security checkpoint before moving on:**
- [ ] `.env` is in `.gitignore` and never committed
- [ ] No API key appears anywhere in source code, only via `os.environ` / settings object
- [ ] `.env.example` has placeholders, not real keys

---

## Module 1 — Database Schema & Models

**Goal:** Define your core data model with proper relationships and constraints before writing any feature logic.

**Prompt:**
```
Using the FastAPI + SQLAlchemy + Alembic setup from before, create the
following models in app/models:

1. User
   - id (UUID, primary key)
   - email (unique, indexed, not null)
   - hashed_password (not null — never store plaintext)
   - full_name
   - created_at, updated_at (timestamps)

2. Meeting
   - id (UUID, primary key)
   - user_id (FK → User, indexed, on delete cascade)
   - meeting_url (the Meet/Zoom link pasted by user)
   - title (nullable, optional user label)
   - status (enum: pending, bot_joining, in_progress, processing, completed, failed)
   - recall_bot_id (string, nullable — ID returned by Recall.ai)
   - started_at, ended_at (nullable timestamps)
   - created_at

3. Transcript
   - id (UUID, primary key)
   - meeting_id (FK → Meeting, one-to-one, on delete cascade)
   - raw_transcript_json (JSONB — full speaker-labeled transcript)
   - created_at

4. Summary
   - id (UUID, primary key)
   - meeting_id (FK → Meeting, one-to-one, on delete cascade)
   - summary_text
   - key_points (JSONB — array of strings)
   - action_items (JSONB — array of {task, owner})
   - decisions (JSONB — array of strings)
   - created_at

Requirements:
- All foreign keys must have proper ON DELETE CASCADE so deleting a user
  cleans up their meetings/transcripts/summaries.
- Add indexes on user_id (Meeting), meeting_id (Transcript, Summary), and
  email (User).
- Generate an Alembic migration for all of this.
- Add SQLAlchemy relationship() definitions both directions (User.meetings,
  Meeting.transcript, Meeting.summary).
- Create matching Pydantic schemas in app/schemas for request/response
  validation — never expose hashed_password in any response schema.
```

**Security checkpoint:**
- [ ] `hashed_password` is never included in any response schema
- [ ] Cascade deletes are set up (no orphaned data on user deletion — relevant for privacy/GDPR-style compliance)

---

## Module 2 — Authentication (Signup, Login, JWT)

**Goal:** Secure auth from day one — this is the module evaluators/interviewers will scrutinize most.

**Prompt:**
```
Implement authentication for the FastAPI backend using JWT.

Requirements:
1. POST /api/auth/signup
   - Accepts email, password, full_name
   - Validate email format and enforce password strength (min 8 chars,
     at least one number) using Pydantic validators
   - Hash password using bcrypt (via passlib) — never store plaintext
   - Return 409 if email already exists, with a generic error message
     (don't leak whether it's the email specifically that's taken vs
     other validation issues, to avoid user enumeration where reasonable)
   - Create the user, return a JWT access token + refresh token

2. POST /api/auth/login
   - Verify email/password against hashed password
   - Rate limit this endpoint (max 5 attempts per IP per 15 minutes) to
     prevent brute force — use slowapi or a Redis-backed limiter
   - Return generic "invalid credentials" for both wrong email and wrong
     password (don't reveal which one was wrong)
   - Return JWT access token (short-lived, 15-30 min) + refresh token
     (longer-lived, 7 days, stored as httpOnly secure cookie)

3. POST /api/auth/refresh
   - Exchanges a valid refresh token for a new access token

4. Dependency: get_current_user
   - FastAPI dependency that validates the JWT from the Authorization
     header, fetches the user, raises 401 if invalid/expired
   - Use this to protect all future endpoints

5. Security requirements:
   - JWT secret key from environment variable, never hardcoded
   - Use HS256 or RS256 signing
   - Access tokens short-lived; refresh tokens in httpOnly, secure,
     sameSite=strict cookies (not localStorage, to reduce XSS token theft risk)
   - Add CORS middleware restricted to your actual frontend origin
     (from CORS_ORIGINS env var), not wildcard *
   - All endpoints must validate/sanitize input via Pydantic — no raw
     string concatenation into SQL anywhere (SQLAlchemy ORM handles this,
     just confirm no raw SQL is used)

Write tests for signup (success + duplicate email) and login (success +
wrong password + rate limit trigger).
```

**Security checkpoint:**
- [ ] Passwords hashed with bcrypt, never plaintext, never logged
- [ ] Rate limiting active on login endpoint
- [ ] Refresh token in httpOnly cookie, not localStorage
- [ ] CORS restricted to your actual domain, not `*`

---

## Module 3 — Recall.ai Integration (Bot Joins the Meeting)

**Goal:** Let a logged-in user paste a Meet/Zoom link and have your backend send a bot into that meeting.

**Prompt:**
```
Integrate the Recall.ai API to send a bot into a meeting.

Requirements:
1. POST /api/meetings  (protected, requires authenticated user)
   - Accepts { meeting_url, title (optional) }
   - Validate meeting_url is a well-formed URL and matches known patterns
     for Google Meet / Zoom / Teams links (basic regex validation) —
     reject anything else with a 400 error
   - Create a Meeting row with status=pending
   - Call the Recall.ai API to create a bot and send it to meeting_url
     (use the RECALL_AI_API_KEY from env, never hardcode)
   - Store the returned recall_bot_id on the Meeting row, update status
     to bot_joining
   - Return the created meeting object to the frontend

2. GET /api/meetings  (protected)
   - Returns the current user's meetings only — filter by user_id from
     the JWT, never trust a user_id passed in the request body/query
   - Paginate results (limit/offset or cursor-based)

3. GET /api/meetings/{meeting_id}  (protected)
   - Returns a single meeting BUT must verify meeting.user_id matches the
     authenticated user's id — return 403/404 if not, so users can never
     view another user's meeting by guessing IDs (this is an authorization
     check, distinct from authentication — don't skip it)

4. Wrap the Recall.ai HTTP calls in a service class (app/services/recall.py)
   with proper error handling — if Recall.ai API fails or times out, set
   meeting status to 'failed' and return a clear error to the frontend
   rather than crashing.

5. Add retries with exponential backoff (max 3 attempts) for transient
   Recall.ai API failures, using a library like tenacity.
```

**Security checkpoint:**
- [ ] Every meeting-fetching endpoint checks `meeting.user_id == current_user.id` before returning data (this is the #1 place student projects leak other users' data)
- [ ] `meeting_url` is validated, not blindly trusted/passed through

---

## Module 4 — Webhook Handler (Recording Ready)

**Goal:** Receive the callback from Recall.ai when the meeting ends and audio is ready — this is a public endpoint, so it needs its own security treatment.

**Prompt:**
```
Implement a webhook endpoint to receive events from Recall.ai when a
meeting recording is ready.

Requirements:
1. POST /api/webhooks/recall  (PUBLIC endpoint, no JWT — but see security below)
   - Recall.ai will POST an event payload here when the bot's recording
     is done and includes a signature header for verification
   - Verify the webhook signature (HMAC) against RECALL_WEBHOOK_SECRET
     before trusting ANY of the payload — reject with 401 if signature
     doesn't match. This prevents anyone from spoofing fake "recording
     ready" events to your system.
   - Look up the Meeting by recall_bot_id from the payload
   - Update Meeting.status to 'processing', store ended_at
   - Trigger the transcription pipeline asynchronously (don't block the
     webhook response — Recall.ai expects a fast 200 OK; use a background
     task via FastAPI BackgroundTasks or a task queue like Celery/RQ if
     you want it more robust)
   - Log the event but never log full payload contents that might contain
     sensitive audio URLs in plaintext logs long-term — log only meeting_id
     and event type

2. Add idempotency handling: if the same webhook event arrives twice
   (webhooks can be retried by the sender), don't process it twice —
   check current meeting status before reprocessing.

3. Return a fast 200 response even if downstream processing fails (log the
   failure internally, set meeting status to 'failed', but don't make
   Recall.ai retry endlessly by returning errors for issues on your side
   that a retry won't fix).
```

**Security checkpoint:**
- [ ] Webhook signature verification is in place and rejects unsigned/invalid requests
- [ ] No sensitive data (audio URLs, tokens) written to persistent logs

---

## Module 5 — Transcription + Speaker Diarization

**Goal:** Take the recorded audio and turn it into a speaker-labeled transcript.

**Prompt:**
```
Implement the transcription pipeline using Deepgram (or AssemblyAI).

Requirements:
1. Create app/services/transcription.py with a function
   transcribe_meeting(meeting_id) that:
   - Fetches the audio URL from the Recall.ai recording data for that meeting
   - Sends it to Deepgram's API with diarization enabled
     (diarize=true parameter) and the API key from env
   - Parses the response into a clean structure: list of
     { speaker: "Speaker 1", text: "...", start_time, end_time }
   - Saves this as Transcript.raw_transcript_json linked to the meeting
   - On success, triggers the summarization step (Module 6) next
   - On failure, sets Meeting.status = 'failed', logs the error with
     enough context to debug but without leaking API keys in logs

2. This should run as a background task triggered from the webhook handler
   (Module 4), not synchronously in the request/response cycle.

3. Add basic cost/rate-limit safety: set a max audio duration you'll accept
   for processing (e.g., reject or truncate meetings longer than 3 hours)
   so a runaway meeting doesn't blow up your API costs during the demo/
   trial phase.

4. Write a small script/endpoint for manual testing: given a meeting_id,
   trigger transcription directly (useful for testing without needing a
   real live meeting every time).
```

---

## Module 6 — AI Summarization (Claude API)

**Goal:** Turn the raw transcript into a structured, useful summary.

**Prompt:**
```
Implement the summarization step using the Claude API.

Requirements:
1. Create app/services/summarization.py with summarize_meeting(meeting_id) that:
   - Fetches the Transcript for the meeting
   - Formats the speaker-labeled transcript into a clean text block
   - Sends it to the Claude API (ANTHROPIC_API_KEY from env) with a system
     prompt instructing it to return ONLY valid JSON with this exact shape:
     {
       "summary": "2-3 sentence overview",
       "key_points": ["point 1", "point 2", ...],
       "action_items": [{"task": "...", "owner": "Speaker 2 or name if known"}],
       "decisions": ["decision 1", ...]
     }
   - Parse and validate the JSON response (wrap in try/except — if the
     model returns malformed JSON, retry once with a stricter prompt
     before failing)
   - Save the result to the Summary table
   - Update Meeting.status = 'completed'
   - Trigger the email notification (Module 8)

2. Truncate/chunk very long transcripts if they exceed a safe token budget
   for a single API call — summarize in chunks and do a final merge pass
   if needed, rather than silently failing on long meetings.

3. Never send the transcript to any third-party logging service or expose
   it in error messages returned to the frontend — treat meeting content
   as sensitive user data throughout this pipeline.

GET /api/meetings/{meeting_id}/summary  (protected, ownership-checked like
Module 3) — returns the Summary + Transcript for a completed meeting.
```

---

## Module 7 — Frontend: Auth Pages

**Prompt:**
```
Build the authentication UI in React + Tailwind.

Requirements:
1. Signup page: email, password, full name fields with client-side
   validation matching backend rules (min password length etc.), clear
   error messages from API responses.
2. Login page: email, password, "invalid credentials" generic error
   display, loading state during request.
3. Store the access token in memory (React context/state), NOT
   localStorage or sessionStorage (to reduce XSS risk) — rely on the
   httpOnly refresh cookie for persistence across page reloads, and call
   /api/auth/refresh on app load to silently re-authenticate.
4. Create a ProtectedRoute wrapper component that redirects to /login if
   no valid session exists.
5. Add axios/fetch interceptor that automatically attaches the Authorization
   header and handles 401s by attempting a token refresh once before
   logging the user out.
6. Basic form validation feedback, disabled submit buttons during loading,
   toast notifications for errors.
```

---

## Module 8 — Frontend: Dashboard & Meeting Detail

**Prompt:**
```
Build the main product UI.    

Requirements:
1. Dashboard page (protected):
   - "Paste a meeting link" input + Join button → calls POST /api/meetings
   - List of past meetings (title, date, status badge: pending/in
     progress/processing/completed/failed)
   - Poll GET /api/meetings every 10-15s while any meeting is in a
     non-terminal status, so the UI updates automatically as processing
     completes (or use a simple WebSocket/SSE channel if you want it
     more real-time and have time for it)

2. Meeting detail page (protected, /meetings/:id):
   - Header: title, date, status
   - Summary card: overview text, key points as a bulleted list
   - Action items: checklist UI with task + owner
   - Decisions: bulleted list
   - Full transcript view: speaker-labeled, scrollable, with timestamps
   - Loading skeleton while status is still 'processing'
   - Error state UI if status is 'failed', with a retry button that calls
     a backend retry endpoint

3. Use Tailwind for a clean, modern look — card-based layout, status
   badges with color coding (yellow=processing, green=completed, red=failed).

4. Handle empty states (no meetings yet) with a friendly prompt to paste
   a link.
```

---

## Module 9 — Email Notification

**Prompt:**
```
Add automatic email delivery of the meeting summary once processing
completes.

Requirements:
1. app/services/email.py using Resend (or SendGrid) API, key from env.
2. Triggered at the end of Module 6's summarization step, on success only.
3. Email template: meeting title, date, summary text, key points, action
   items, and a link back to the full meeting detail page on your site.
4. Handle send failures gracefully — log them, but never let an email
   failure mark the whole meeting as 'failed' (the summary itself
   succeeded; email is a notification, not the core deliverable).
5. Don't include the full raw transcript in the email body (could be long
   and is better viewed on the dashboard) — just the structured summary.
```

---

## Module 10 — Security Hardening Pass (do this before any live demo)

**Prompt:**
```
Do a security review pass across the whole FastAPI backend:

1. Confirm every protected endpoint uses the get_current_user dependency
   and checks resource ownership (user_id match) before returning data.
2. Add input validation limits: max length on all string fields (meeting
   title, etc.) to prevent abuse.
3. Add rate limiting to all public-facing endpoints, not just login
   (signup, webhook endpoint especially).
4. Confirm all secrets are loaded from environment variables only —
   grep the codebase for any hardcoded API keys, passwords, or tokens
   and flag them.
5. Add HTTPS enforcement / secure cookie flags for production config.
6. Add a global exception handler that returns generic error messages to
   clients (never leak stack traces, internal file paths, or DB errors
   to the frontend) while logging full details server-side.
7. Confirm CORS is locked to your actual frontend domain(s), not '*'.
8. Add request size limits to prevent large payload abuse.
9. Review that no user-identifiable meeting content (transcripts,
   summaries) is ever logged in plaintext to persistent logs.

Summarize every issue found and fix them one by one.
```

---

## Module 11 — Deployment

**Prompt:**
```
Prepare this project for deployment.

Requirements:
1. Backend: Dockerfile for the FastAPI app, environment variables
   documented for the target platform (Railway/Render).
2. Add a production-ready CORS_ORIGINS, DATABASE_URL, and all secrets as
   platform environment variables (never committed).
3. Set up Alembic migrations to run automatically on deploy (or document
   the manual command).
4. Frontend: build config for Vercel, with VITE_API_BASE_URL pointing to
   the deployed backend URL.
5. Add a basic uptime health check and confirm /health responds correctly
   post-deploy.
6. Write a short DEPLOYMENT.md with exact steps to redeploy from scratch,
   useful both for your viva ("how would you deploy this in production")
   and for your own sanity later.
```

---

## Suggested Day Mapping

| Day | Modules |
|---|---|
| Day 1 | 0, 1, 2, 3 (project setup, DB, auth, Recall.ai integration) |
| Day 2 | 4, 5, 6 (webhook, transcription, summarization) |
| Day 3 | 7, 8 (frontend auth, dashboard, meeting detail) |
| Day 4 | 9, 10, 11 (email, security pass, deploy) + demo rehearsal |

Test each module live before moving to the next — don't stack unverified modules on top of each other, or debugging day 3 issues gets painful fast.
