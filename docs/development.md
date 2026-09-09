# Development Environment Setup

This document describes how to set up the local development environment for Phase 0 of RepoMedic. Currently, the project consists of a PostgreSQL database, a FastAPI backend testing DB connectivity, and a Next.js App Router frontend rendering a Tailwind-styled placeholder.

## Prerequisites
- **Python 3.10+**
- **Node.js 18+**
- **Docker** and Docker Compose

## Global Setup 
We recommend opening three separate terminal windows to run the database, backend, and frontend concurrently. All commands should be executed from the project root (`Argus og`).

## 1. Database (PostgreSQL)
Run the PostgreSQL service in the background utilizing Docker Compose:
```bash
docker compose up -d postgres
```
*(Alternative via root Makefile: `make db-up`)*

## 2. Backend (FastAPI)
The backend requires a Python virtual environment and installs dependencies from `backend/requirements.txt`.

### First-Time Setup
```bash
cd backend
python -m venv venv
```

### Running the Backend
Ensure your virtual environment is active:
- **Windows**: `venv\Scripts\activate`
- **Linux/Mac**: `source venv/bin/activate`

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```
*(Alternative via root Makefile: `make dev-backend` - assumes virtual environment active or auto-detectable depending on system)*

## 3. Frontend (Next.js)
The frontend utilizes Next.js and depends on the backend for API components.

### First-Time Setup
```bash
cd frontend
npm install
cp .env.local.example .env.local
```

### Running the Frontend
```bash
cd frontend
npm run dev
```
*(Alternative via root Makefile: `make dev-frontend`)*

## Validation
Once all three systems are running:
- Open `http://localhost:3000` to review the frontend placeholder.
- Open `http://localhost:8000/api/v1/health` to confirm the backend's database connectivity returns `"database": "connected"`.

## 4. End-to-End Testing (Playwright)
Once the database, backend, and frontend are running concurrently as described above, you can execute the E2E test suite. The E2E tests use Playwright to simulate browser flows, including programmatic dev logins and protected route bounds.

### Running Tests
```bash
cd frontend
npm run test:e2e
```
