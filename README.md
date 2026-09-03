# AI Reliability Engineer

The AI Reliability Engineer detects a real regression, investigates with real evidence, gets a validated AI root-cause analysis, executes a human-approved fix, and proves recovery. This is not a chatbot; it is a full, automated reliability workflow.

## Why this exists

While most "AI monitoring" demos stop at detection and anomaly alerts, this system closes the loop through verified recovery. It proves that an AI agent workflow can end with a safely executed remediation that demonstrably restores system health.

## Architecture

This project is structured as a locally-run hackathon demonstration. It uses Docker Compose for generic telemetry infrastructure and FastAPI for the core logic layer, prioritizing a fast, self-contained golden path over distributed environment scaffolding.

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

*Note: Kubernetes, cloud deployment, and microservices were deliberately out of scope for this build to keep the focus tight and optimize for hackathon demonstration speed.*

## Quick Start
Run these commands locally from a clean clone:

**1. Start the telemetry infrastructure:**
```bash
docker compose up -d
```

**2. Start the Backend:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Or .venv\Scripts\activate on Windows
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000
```

**3. Start the Simulator:**
```bash
cd simulator
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8001
```

**4. Start the Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**5. Environment Setup:**
Copy `.env.example` to `.env` in the root (or `backend/`) and populate the real variables used by the codebase:
- `DATABASE_URL`: Connection string for the local SQLite database.
- `GITHUB_TOKEN`: Target repo access token (only needs Issues: write).
- `GITHUB_REPO`: Target repository to push incident reports (e.g., owner/repo).
- `AI_API_KEY`: API key for Gemini execution.
- `RAZORPAY_KEY_ID`: Razorpay public key for live checkout.
- `RAZORPAY_KEY_SECRET`: Razorpay secret for checkout verification.
- `RAZORPAY_WEBHOOK_SECRET`: Signing secret for validating incoming Razorpay webhooks.
- `PROMETHEUS_URL`: Internal URL for the Prometheus instance.
- `LOKI_URL`: Internal URL for the Loki logging instance.

## Running the demo golden path

Use the frontend dashboard to run the full incident lifecycle. For a timed recording, see [DEMO_SCRIPT.md](DEMO_SCRIPT.md).

1. Click **"Trigger Bad Deployment"** to inject a simulated failure into the environment. 
2. Wait a moment, then click **"Run Detection Pass"** to surface the incident.
3. Open the newly detected incident from the incident list.
4. Run the investigation pipeline to gather evidence. 
5. Run the Root Cause Analysis (RCA).
6. Click **"Propose Remediation"** based on the RCA findings.
7. Enter your name and click **"Approve"** to sign off on the proposed fix.
8. Click **"Execute Remediation"** to trigger the rollback.
9. Wait for the system to settle, then click **"Run Verification"** to confirm recovery.
10. Navigate to the GitHub panel to view and optionally publish the final incident report.

## How detection works

Detection exclusively uses deterministic thresholds against real telemetry. No LLM is used for the detection phase. The system relies on a 1-minute `DETECTION_WINDOW` with deduplication and cooldown behavior. 

There are three detectors and thresholds configured by default:
- **Error Rate**: Fires if the rate exceeds `0.05` (medium severity) or `0.15` (high severity).
- **Latency (p95)**: Fires if latency exceeds `500ms` (medium) or `1500ms` (high).
- **Webhook Failure**: Fires if Razorpay webhook failure rate exceeds `0.10` (medium) or `0.25` (high).

## How evidence is collected

The system collects active signals from metrics, logs, git commits, and Razorpay webhook collectors. A core design decision limits the evidence layer to reporting an explicit separation of `observed_fact` and `hypothesis`. This layer never states a root cause directly, ensuring that data gathering remains objective for the downstream AI.

## How AI RCA works

RCA relies on a single model call utilizing a strict pydantic schema (`RCAOutput`) encompassing summary, impact, affected components, confidence, evidence, and an explicit `RemediationRecommendation`. AI output is heavily scrutinized: the system uses validation, hallucination rejection against observed facts, and bounded retries. The AI is treated as untrusted; its output is independently checked against the system's real evidence before being offered to users.

## How remediation works

Remediation uses a strict allowlist from schema configurations containing three possible types:
- `rollback_deployment`
- `restart_service`
- `restart_container`

Currently, **only `rollback_deployment` has a real execution handler** in this build. Attempting to execute `restart_service` or `restart_container` will return a 501 ("This remediation type isn't implemented in this build"). Remediations require a mandatory human-approval gate prior to execution; there is no auto-approve path.

## How verification works

Verification performs a real before-and-after comparison of the system components, applying bounded polling of the incident metrics. A `resolved` state means the detector explicitly confirmed the incident is no longer firing, whereas a `remediation_failed` result indicates the rollback was executed but system health did not recover within the designated window structure.

## Razorpay relevance

The Razorpay integration provides a test-mode webhook layer to exercise external integration failures. It encompasses real signature validation, payload idempotency, and correlation into evidence specifically for `webhook_failure` incidents. No real payment processing happens in this application, and no real credentials are required.

## GitHub integration

The backend supports real markdown report generation containing incident facts and RCA summaries, and provides real, optional GitHub issue creation. The GitHub integration degrades gracefully, meaning the core reliability workflow never fails if the GitHub API is unavailable or unconfigured.

## Security model

The codebase isolates credentials and critical paths using:
- Pure environment-based secrets (none leaked in API or UI).
- Remediation allowlists enforced at multiple system boundaries.
- Tight AI output validation to safely ignore injected nonsense.
- Complete lack of shell or subprocess exposure to AI prompts or request endpoints.
- Constant-time signature comparison for webhook validation.

The system security model is explicitly validated by `tests/test_security.py`.

## Testing

Fast unit/integration tests can be run via pytest:
```bash
pytest backend/tests/
```
Tests explicitly validating AI and E2E mechanics are protected by the `@pytest.mark.e2e` marker. They can be triggered via `pytest -m e2e` and will automatically skip rather than fail if an `AI_API_KEY` is not present, ensuring clean CI boundaries.

## Rehearsal tooling

The repository contains specific dev tooling to ensure live demonstrations are fast and flawless. A `.env.demo.example` file is included, which sets `DEMO_MODE=true` to decrease polling intervals and expose endpoints to inject traffic (**"Warm Up Traffic"**) and clear databases (**"Reset Demo Data"**). These features are heavily gated intentionally for rehearsal, non-production environments.

## Future extensions

As an optimized showcase architecture, several features were intentionally deferred and may be built in future updates:
- Actual execution handlers for `restart_service` and `restart_container`.
- Additional detector types (e.g., infrastructure saturation, complex SLI definitions). 
- Diverse failure scenario injection.
- Kubernetes-native bindings and cloud deployment.
- Semantic incident-memory retrieval (e.g., "how did we fix this last time?").
- Enterprise authentication, RBAC, and granular permissions.
- Automatic or manual retry paths following an initial remediation failure.
