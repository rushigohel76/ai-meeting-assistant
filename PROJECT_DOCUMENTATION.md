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

Right now, the frontend does not yet call backend business APIs. It only reads and displays the configured backend URL. The backend currently exposes one working endpoint: `GET /health`.

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
```

## 4. Environment Configuration

Backend environment variables are listed in:

```text
.env.example
```

Required backend variables:

```text
DATABASE_URL
RECALL_AI_API_KEY
DEEPGRAM_API_KEY
ANTHROPIC_API_KEY
JWT_SECRET_KEY
RESEND_API_KEY
CORS_ORIGINS
RECALL_WEBHOOK_SECRET
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

## 17. What Has Not Been Built Yet

The following pieces are intentionally not implemented yet:

- user signup/login endpoints
- password hashing service
- JWT authentication logic
- meeting creation endpoint
- Recall.ai integration
- Deepgram integration
- Anthropic summary generation
- Resend email sending
- frontend forms and screens for real workflows
- API calls from frontend to backend

The current project is ready for those features to be added on top of a clean foundation.

## 18. Suggested Next Build Steps

A practical next order would be:

1. Add password hashing and authentication utilities.
2. Add user signup and login endpoints.
3. Add JWT access token creation and validation.
4. Add protected meeting creation/listing endpoints.
5. Connect the frontend to the auth and meeting APIs.
6. Add Recall.ai bot join flow. 
7. Add transcript processing and summary generation.
8. Add frontend screens for meetings, transcripts, summaries, and action items.

