# AgentDesk — AI Multi-Agent Platform for Small Businesses

> **Final Year Project (FYP)**  
> **Team:** Mukarram Ali & Hadia Saleem  
> **Current Status:** Phase 1A — Project Foundation Completed  

---

## 1. Project Overview

**AgentDesk** is an AI-powered multi-agent platform designed for small businesses. It enables business owners to configure a unified business brain and deploy AI agents across Web Chat, WhatsApp, and Voice simulations to qualify leads, book appointments, and answer customer queries in English and Urdu.

This repository follows the approved architectural blueprint defined in [`docs/00_MASTER_DEVELOPMENT_BLUEPRINT.md`](docs/00_MASTER_DEVELOPMENT_BLUEPRINT.md) and [`AGENTS.md`](AGENTS.md).

---

## 2. Phase 1A Architecture Baseline

Phase 1A establishes the foundation for the project:

- **Frontend**: Next.js 16 (App Router), TypeScript, Tailwind CSS
- **Backend**: FastAPI, Python 3.13, Pydantic, SQLAlchemy 2 (asyncpg)
- **Infrastructure**:
  - PostgreSQL 16 with `pgvector` extension (0.8.7) enabled
  - Redis 7 for cache and asynchronous background tasks
  - Docker Compose foundation

---

## 3. Prerequisites

Ensure you have the following installed locally:

- **Python**: 3.11+ (Python 3.13 tested)
- **Node.js**: 20+ (Node.js 24 tested) & `npm`
- **Docker Desktop**: Docker Engine & Docker Compose

---

## 4. Getting Started Locally

### Step 1: Environment Configuration

Copy the example environment files:

```bash
# In project root:
cp .env.example .env

# In backend directory:
cp backend/.env.example backend/.env

# In frontend directory:
cp frontend/.env.example frontend/.env.local
```

> **Note on PostgreSQL Port:** The default configuration maps PostgreSQL to host port `5434` (`localhost:5434`) to avoid port collisions if you have a local PostgreSQL instance running on default port `5432`. You can customize this in `.env` if desired.

---

### Step 2: Start Infrastructure (Docker Compose)

Start PostgreSQL (with `pgvector`) and Redis in detached mode:

```bash
docker compose up -d
```

Verify services are running and healthy:

```bash
docker compose ps
```

Verify `pgvector` extension in PostgreSQL:

```bash
docker exec agentdesk-postgres psql -U postgres -d agentdesk -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
```

Verify Redis response:

```bash
docker exec agentdesk-redis redis-cli ping
# Expected: PONG
```

---

### Step 3: Run Backend (FastAPI)

1. Navigate to the backend directory and install dependencies:

```bash
cd backend
pip install -r requirements.txt
```

2. Run automated tests:

```bash
pytest -v
```

3. Start the FastAPI development server:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

4. Verify health endpoint:

Open in browser or curl:
- `http://127.0.0.1:8000/health` (Health & dependency check)
- `http://127.0.0.1:8000/docs` (Interactive OpenAPI Swagger UI)

Expected Health JSON output:
```json
{
  "status": "healthy",
  "app": "AgentDesk",
  "version": "0.1.0",
  "environment": "development",
  "database": {
    "status": "healthy",
    "pgvector": "enabled (v0.8.7)"
  },
  "redis": {
    "status": "healthy"
  }
}
```

---

### Step 4: Run Frontend (Next.js)

1. Navigate to the frontend directory:

```bash
cd frontend
npm install
```

2. Start the development server:

```bash
npm run dev
```

3. Open your browser at:
- `http://localhost:3000`

The landing page displays the architecture foundation status and communicates live with the FastAPI backend health endpoint.

---

## 5. Stopping Services

To stop local background services:

```bash
# Stop Docker containers:
docker compose down
```

---

## 6. Project Roadmap

- [x] **Phase 0:** Documentation & Architecture Planning
- [x] **Phase 1A:** Project Foundation (Repository, Next.js, FastAPI, PostgreSQL + pgvector, Redis)
- [ ] **Phase 2:** Authentication (Argon2id, Session/Token Management)
- [ ] **Phase 3:** Business Onboarding & Multi-Tenant Setup
- [ ] **Phase 4:** Agent Configuration
- [ ] **Phase 5:** Knowledge Base & RAG Pipeline
- [ ] **Phase 6:** AI Orchestration Engine
- [ ] **Phase 7:** Web Chat Widget
- [ ] **Phase 8:** Lead Qualification Agent
- [ ] **Phase 9:** Appointment Booking
- [ ] **Phase 10:** Google Calendar Integration
- [ ] **Phase 11:** WhatsApp Integration
- [ ] **Phase 12:** Voice Agent & Browser Simulator
- [ ] **Phase 13:** Conversation History
- [ ] **Phase 14:** Business Dashboard
- [ ] **Phase 15:** Analytics
- [ ] **Phase 16:** Security Hardening
- [ ] **Phase 17:** Testing & QA
- [ ] **Phase 18:** Deployment
- [ ] **Phase 19:** FYP Demo & Final Defense