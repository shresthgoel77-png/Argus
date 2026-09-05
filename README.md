# 🛡️ AI Reliability Engineer

> **A closed-loop, automated reliability workflow: Detect, Investigate, Root-Cause, Auto-Remediate, and Verify.**

The AI Reliability Engineer detects a real regression, investigates with real evidence, gets a validated AI root-cause analysis, executes a human-approved fix, and proves recovery. This is **not** a chatbot; it is a full, automated reliability engineering workflow.

## ✨ Why this exists

While most "AI monitoring" demos stop at detection and anomaly alerts, this system **closes the loop** through verified recovery. It proves that an AI agent workflow can end with a safely executed remediation that demonstrably restores system health.

---

## 🏗️ Architecture & Component Responsibilities

This project prioritizes a fast, self-contained **golden path** optimized for hackathon demonstration. It uses Docker Compose for generic telemetry infrastructure and FastAPI for the core logic layer.

```text
+-------------------+       +-----------------------+       +-------------------+
|                   |       |                       |       |                   |
|  Frontend (Next)  |<----->|  Backend Core         |<----->|  Simulator App    |
|                   |       |  (FastAPI)            |       |  (FastAPI)        |
+-------------------+       +-----------------------+       +-------------------+
                               |              ^                        |
                               v              |                        v
                        +-------------+ +-------------+         +-------------+
                        | AI/Gemini   | | Prometheus /|         | Internal DB |
                        | GitHub API  | | Loki / DB   |<--------| (Telemetry) |
                        +-------------+ +-------------+         +-------------+
```

### 📁 Project Structure

- **`/frontend`** (Next.js 15, React 19, Tailwind v4): The modern, reactive dashboard for operators to oversee the incident lifecycle, review evidence, and approve auto-remediations.
- **`/backend`** (FastAPI, SQLite, google-genai): The core orchestration layer. Manages thresholds, collects telemetry, calls the Gemini LLM for RCA, and handles human-in-the-loop remediation and verification.
- **`/simulator`** (FastAPI): Injects synthetic workloads, generates failures (latency, errors), and simulates webhook integrations (like Razorpay) for the backend to monitor.
- **`/infrastructure`**: Contains Docker Compose configuration for a local `Prometheus` and `Loki` telemetry stack.

*(Note: Kubernetes, cloud deployment, and microservices were deliberately out of scope for this build to keep the focus tight and optimize for demonstration speed.)*

---

## 🔄 End-to-End Workflow

The system facilitates a completely observable lifecycle for every incident:

1. **Failure Injection**: Inject a simulated failure via the dashboard into the environment (e.g., bad deployment, external API outage).
2. **Detection**: Deterministic thresholds trigger an incident based on real telemetry (no LLM).
3. **Investigation & Evidence Collection**: The system autonomously gathers metrics, logs, git commits, and webhook data. It keeps observations strictly objective (facts vs. hypothesis).
4. **AI Root Cause Analysis (RCA)**: Google Gemini analyzes the collected evidence. Its output is heavily validated against real facts to reject hallucinations.
5. **Human Approval**: The AI proposes a remediation (e.g., `rollback_deployment`). A human must explicitly sign off on the UI.
6. **Remediation Execution**: The backend executes the approved fix (e.g., initiating a rollback script).
7. **Verification**: The system actively polls metrics *after* remediation to mathematically prove the incident is no longer firing.
8. **Reporting & Recovery**: An automated Root Cause markdown report is generated and can be pushed as a real GitHub Issue.

---

## 🧠 AI Utilization & Safeguards

The AI (Gemini) is treated as untrusted. Output is independently checked against the system's real evidence before being offered to users.

- **Strict Pydantic Schemas**: LLM responses must strictly adhere to the `RCAOutput` schema (summary, impact, affected components, confidence, evidence, remediation).
- **Hallucination Rejection**: Any claim made by the AI must map logically to the gathered evidence.
- **Bounded Retries**: If the AI schema fails validation, the system automatically asks the model to correct itself within a bounded limit.
- **No Direct Execution**: The LLM *cannot* directly mutate the system. It only proposes remediations from a strict allowlist.

---

## 🔌 Core Integrations

- **Razorpay**: Provides a test-mode webhook layer to exercise external integration failures. Uses real signature validation (HMAC), payload idempotency, and correlation to test webhook outage detection. No real payments are processed.
- **GitHub**: Supports real markdown report generation containing incident facts and RCA summaries. Optionally creates real GitHub issues. Fails gracefully if not configured.
- **Google Gemini**: Powers the Root Cause Analysis engine.

---

## 🚀 Quick Start / Setup

### ⚙️ Prerequisites
- Docker & Docker Compose
- Python 3.10+
- Node.js 20+

### 1. Environment Setup

Copy `.env.example` to `.env` in the root (or `backend/`) and populate the core variables:

```ini
# Core Configuration
DATABASE_URL=sqlite:///./app.db         # Local SQLite DB
AI_API_KEY=your_gemini_api_key          # Gemini Execution

# Telemetry
PROMETHEUS_URL=http://localhost:9090
LOKI_URL=http://localhost:3100

# Optional Integrations
GITHUB_TOKEN=your_github_token          # Issue write access
GITHUB_REPO=owner/repo                  # Target repo to push reports
RAZORPAY_KEY_ID=test_...                # Razorpay public key
RAZORPAY_KEY_SECRET=...                 # Razorpay secret
RAZORPAY_WEBHOOK_SECRET=your_secret     # Webhook signing secret
```

### 2. Start Services

Open separate terminal windows/tabs for the following commands from a clean clone:

**A. Telemetry Infrastructure:**
```bash
cd infrastructure
docker compose up -d
```

**B. Simulator System:**
```bash
cd simulator
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8001
```

**C. Core Backend:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000
```

**D. Frontend Dashboard:**
```bash
cd frontend
npm install
npm run dev
```

---

## 🎯 Running the Demo Golden Path

Access the main dashboard at `http://localhost:3000` to run the incident lifecycle.

1. Click **"Trigger Bad Deployment"** (or other failure scenario) to inject failure into the backend infrastructure simulator.
2. Click **"Run Detection Pass"** (surfaces the incident based on the 1-minute `DETECTION_WINDOW` thresholds like Error Rate or Latency).
3. Open the newly detected incident.
4. Click **"Run Investigation"** to construct the chronological evidence timeline.
5. Click **"Run Root Cause Analysis"** to prompt Gemini for its validated findings.
6. Click **"Propose Remediation"**.
7. Provide an explicit sign-off in the **Approval** step.
8. Click **"Execute Remediation"**. The system executes the rollback.
9. Wait for the system to settle, then click **"Run Verification"** to confirm recovery via telemetry.
10. Review the final generated report via the GitHub integration panel.

### 🎭 Rehearsal tooling
To ensure hackathon or live demonstrations are snappy, setting `DEMO_MODE=true` inside a `.env` file exposes endpoints to immediately inject traffic ("Warm Up Traffic") and securely flush databases ("Reset Demo Data"), while bypassing standard cooldown delays.

---

## 🧪 Testing

Comprehensive unit and integration tests are strictly separated into two domains:

```bash
# Run all standard backend unit tests (no AI required)
pytest backend/tests/

# Run End-to-End simulation tests explicitly covering AI / Gemini execution
pytest backend/tests/ -m e2e
```
*Note: Back-end tests protected by the E2E marker fail gracefully or skip if the `AI_API_KEY` is not present, maintaining green core CI boundaries.*

---

## 🛡️ Security Model

The system protects against runaway agents and credential spraying:
- **Pure Environment Variables**: Secrets exist only in environment variables; zero leakages onto APIs or the UI.
- **Remediation Allowlist**: The LLM cannot invent scripts. It must choose from `rollback_deployment`, `restart_service`, or `restart_container`.
- **Validation-first**: Complete lack of shell/subprocess exposure to AI prompts or request endpoints.
- **Cryptographic Validation**: Constant-time signature comparison for webhook validation prevents timing attacks.
*(This model is continuously verified by `tests/test_security.py`)*

---

## 🚧 Design Decisions & Limitations

As an optimized showcase architecture, several features were intentionally deferred for speed and scope:

- **Handler Execution**: Currently, only `rollback_deployment` has an actual underlying execution layer. Attempting to run `restart_service` results in a polite 501 ("Not Implemented").
- **Local SQLite**: Optimizing for setup speed means relying on local `.db` files rather than Postgres.
- **Single-Node**: Telemetry points locally; kubernetes/multi-node scaling bindings are deferred.
- **Human-in-the-Middle limitation**: The system deliberately forces human approval for remediation. Future versions might offer automated fallback recovery policies.

---
