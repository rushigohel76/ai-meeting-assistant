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

Frontend variables are listed in `frontend/.env.example`:

```text
VITE_API_BASE_URL
```

Never commit real `.env` files.
