# MOM

Full-stack scaffold with a FastAPI backend and a React + Vite + Tailwind CSS frontend. This repository currently contains scaffolding, configuration, database setup, and health checks only.

For a fuller explanation of how the frontend, backend, database, models, migrations, and environment setup work together, see [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md).

## Structure

```text
backend/
  app/
    api/
    core/
    db/
    models/
    schemas/
    services/
  alembic/
frontend/
  src/
```

## Backend Setup

Requires Python 3.11+ and PostgreSQL.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
```

Edit `backend/.env` with real values. `DATABASE_URL` must use the async SQLAlchemy driver, for example:

```text
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mom
```

Run migrations:

```bash
alembic upgrade head
```

Start the API server:

```bash
uvicorn app.main:app --reload
```

The health check endpoint is available at:

```text
GET http://localhost:8000/health
```

It returns success only when the API can connect to PostgreSQL.

## Local Webhook Testing

Meeting BaaS cannot reach `localhost` directly when it sends bot lifecycle webhooks. For local development, expose the backend with ngrok or a similar tunnel:

```bash
ngrok http 8000
```

Set `WEBHOOK_BASE_URL` in `backend/.env` to the public HTTPS forwarding URL, without a trailing path:

```text
WEBHOOK_BASE_URL=https://your-ngrok-url.ngrok-free.app
```

Bot creation will send Meeting BaaS this callback URL:

```text
https://your-ngrok-url.ngrok-free.app/api/webhooks/meetingbaas
```

## Frontend Setup

Requires Node.js 18+.

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

The Vite dev server starts at:

```text
http://localhost:5173
```

Set `VITE_API_BASE_URL` in `frontend/.env` to the backend URL.

## Environment Variables

Backend variables are listed in `.env.example`:

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

Frontend variables are listed in `frontend/.env.example`:

```text
VITE_API_BASE_URL
```

Never commit real `.env` files.
