# Architecture

## Overview

Two independently deployable apps:

- **Frontend** (`frontend/`) — Next.js App Router with TypeScript and Tailwind
  CSS. Deployed on Vercel. Talks to the backend over HTTP using
  `NEXT_PUBLIC_API_BASE_URL`.
- **Backend** (`backend/`) — FastAPI with Pydantic. Holds all secrets and
  integrations; can be deployed separately from the frontend.

## Planned integrations (not yet implemented)

| Concern | Service | Where it lives |
| --- | --- | --- |
| Tutor reasoning | Gemini API | backend |
| Speech-to-text / text-to-speech | Gnani AI | backend |
| Database | Supabase (PostgreSQL) | backend |
| Parent reports via WhatsApp | WhatsApp Business Cloud API | backend |

## Principles

- Secrets are backend-only; the browser never sees an API key.
- Dependencies and environment variables are added only when the feature
  that needs them is built.
- Small, focused files; no abstractions before they are needed.
