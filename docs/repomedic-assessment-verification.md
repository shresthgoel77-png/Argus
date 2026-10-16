# RepoMedic assessment recovery — 2026-10-16

Backend recovery is implemented and exercised against the existing application database. **End-to-end UI verification remains blocked**, so the overall task is not marked complete. Browser Use lists the existing Chrome `/overview` tab but rejects page observation with a saved localhost permission/managed-policy denial. No alternate browser, credential extraction, or browser-permission workaround was attempted. This is not evidence of a RepoMedic networking defect.

## Proven failure paths

The application uses FastAPI `BackgroundTasks` for monitoring enablement. It has no durable local queue, consumer, retry table, or dead-letter store. The separate scheduler calls the protected internal monitoring endpoint; this local environment has no configured scheduler shared secret. Initial assessment does not depend on that scheduler.

The existing `bf7431ce9a12` migration backfills enabled repositories to `queued` with `{}` checks without creating executable work. The selected `SGdev-44/Agent-bench-demo` row had that exact state, `last_monitoring_at=NULL`, and no recorded webhook events. Startup had no recovery path. The PATCH enablement path also excludes already-queued repositories from new task scheduling. Merely loading the dashboard cannot execute the backfilled work. The migration was not edited or rerun.

Webhook processing runs event-specific analyzers, rather than a complete initial assessment. Repository discovery/subscription persists repository metadata; enabling monitoring schedules the initial assessment. The full assessment changes status to running, runs six deterministic checks, persists each check and its findings, computes health only if every required check succeeds, and records a terminal status/timestamp. It does not call AI.

The selected repository's stored score of 100 is dated **2026-10-14 21:47:46**, before assessment-status evidence was introduced. The legacy health code calculated 100 from an empty findings list without requiring successful checks. The stored snapshot has no evidence proving a complete assessment. Dashboard current health was already gated on successful assessment, while activity projected historical snapshots and `needs_attention`/AI context still read the old snapshot as current. Historical activity is retained; current attention health and AI context now follow the assessment status.

AI was investigated separately using the selected repository owner's saved BYOK connection. Key decryption succeeded, the Gemini provider resolved, and the configured `gemini-3.6-flash` [model metadata lookup](https://ai.google.dev/api/models) returned HTTP 200 with generation support. An actual repository-summary generation request returned **HTTP 503** and `AIProviderUnavailableError`. No raw key, headers, generated content, or decrypted secret was logged. This verifies a current upstream generation failure; it does not establish the cause of every historical failed summary. No provider, key, model, timeout, or BYOK settings were changed. The probe did not create an AI analysis record.

## Minimal production changes

| File | Additional change in this attempt |
|---|---|
| [main.py](../backend/app/main.py) | Schedule recovery of persisted queued assessments without blocking server startup. Test-client startup does not scan the application database. |
| [scheduled_monitoring_service.py](../backend/app/services/scheduled_monitoring_service.py) | Resume enabled queued repositories through the existing runner; atomically claim queued work so competing startup/request runners cannot both claim it. Continue recovery after one repository fails. |
| [needs_attention_service.py](../backend/app/services/needs_attention_service.py) | Require a successful current assessment before exposing historical health as current attention health/reasons. |
| [repository_summary_context_builder.py](../backend/app/services/repository_summary_context_builder.py) | Include assessment status and explicitly distinguish missing current health from a healthy repository. |

No frontend production source, schema, authentication, session, installation, connection, webhook, dependency, or BYOK configuration was changed.

Tests changed: [new initial-assessment recovery tests](../backend/tests/unit/test_initial_assessment_recovery.py), [summary context](../backend/tests/unit/services/test_repository_summary_context_builder.py), [attention service](../backend/tests/unit/services/test_needs_attention_service.py), [dashboard integration](../backend/tests/integration/api/v1/test_repositories_dashboard_integration.py), [AI service fixtures](../backend/tests/services/test_ai_analysis_service.py), and [AI API fixtures](../backend/tests/integration/api/v1/test_repositories_ai_summary.py). The last two repair stale test fixtures to accept the existing model argument and current typed response fields; production AI contracts were preserved.

## Actual execution and evidence

The backend was restarted normally with `venv\Scripts\python.exe -B -m uvicorn app.main:app --host 127.0.0.1 --port 8000`. The existing frontend was left running. No application migration or database reset was run.

Startup recovered both previously enabled queued repositories. The selected repository entered `running` and finished **`partial_failure` at 2026-10-16 14:07:52 UTC**. The other queued repository, `editzomni469-bot/Agent-bench-`, also finished partial failure because its unchanged installation 161370742 remains inaccessible. No installation association was replaced.

For the selected repository:

| Check | Actual result |
|---|---|
| Installation authentication | GitHub returned 201 for the existing installation's access token. No GitHub resource was published or modified. |
| Issues / PRs | GitHub reads returned 200. Fresh calls through the owned repository route functions validated **1 open issue, 0 open PRs**. These were direct backend function calls, not authenticated browser HTTP requests. |
| Dependency | Succeeded; root `package.json` is absent and repository access was separately confirmed. No missing-lockfile finding was fabricated. |
| Code quality | Succeeded; **one medium `missing_branch_protection` finding** persisted with `default_branch: main` evidence. |
| Security | GitHub returned **403: Dependabot alerts are disabled for this repository**. No security configuration was changed. |
| CI | Unavailable: GitHub has no workflow-run history. No clean CI result was fabricated. |
| Health | Unavailable because required security/CI evidence is incomplete. No new complete health snapshot was written. |

Live backend dashboard composition returns partial failure, a completed assessment timestamp, `code_quality: 1`, no current health/attention snapshot, and activity containing the new finding plus the dated historical score. AI context no longer claims that legacy 100 is current health. Actual browser rendering remains unverified.

Validation: **201 backend tests passed**, including startup recovery, atomic claim eligibility, terminal failure persistence, real analyzer/findings/health persistence with mocked GitHub transport, AI success/failure persistence, BYOK, Clerk validation, ownership, webhook signatures, work items, and incomplete-scan integrity. Tests used a disposable OS-temp database, not `backend/test.db`. All **21 frontend tests** and TypeScript `--noEmit --incremental false` passed. Changed Python files passed syntax parsing. Existing deprecation warnings remain. No PostgreSQL concurrency run was performed.

Fresh HTTP checks: frontend `/` and `/sign-in` returned **200**; backend `/` returned **200**; unauthenticated `/api/v1/repositories` returned **401**. These do not prove that the current browser session is authenticated.

Local evidence is under `C:\Users\shres\AppData\Local\Temp\repomedic-assessment-36psz4rw`: `before.log`, `final-checks.log`, `backend-live.log`, `backend-final.log`, and `verification.json`. Original changed-file bytes and an original database backup are retained there. Intermediate test failures are retained; the final run is the 201-pass run.

## Preservation and remaining verification

Of 732 baseline source/worktree files hashed, only the nine existing source/test files listed above changed; the recovery test and this report are new. Unrelated dirty worktree content was retained. The active migration is unchanged.

Database comparison against the backup confirms that users, GitHub connections, AI connections/encrypted credentials, AI analyses, webhook events, health history, bot interactions, notification preferences, notifications, and Alembic revision are unchanged. Normal assessment execution updated only status/check/timestamp fields on the two enabled queued repositories and inserted the selected repository's single verified finding. No existing records were deleted.

Remaining external requirements: security evidence needs repository Dependabot availability, CI evidence needs real workflow-run history, and AI generation needs an available provider response. None was manufactured or enabled automatically. Recovery covers queued work; interrupted running assessments still require an owner-authorized refresh through the existing workflow.

The user's before observations describe a loaded authenticated overview with queued status, no current score/signals, old score-100 activity, and a failed AI summary. **No after-browser observation, authenticated Network capture, console result, repository-selection check, or settings re-test is claimed.** The user was asked to refresh the existing signed-in overview and confirm the new state. Until local UI evidence is available, verification remains incomplete.
