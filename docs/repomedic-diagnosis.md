# RepoMedic diagnosis and targeted repairs

Date: 2026-10-16. Starting commit: `6ab98d3` (`feat(auth): enforce Clerk as sole primary auth provider`). The worktree was already heavily modified. Existing changes were retained; no reset, checkout, database reset, deployment, authentication bypass, or GitHub issue publication was performed.

## Confirmed causes

| Failure | Evidence and origin | Repair |
| --- | --- | --- |
| Repository-dependent pages fail before reaching GitHub | The configured SQLite database was at `8a4b6c7d8e9f`, while dirty Repository models selected monitoring columns added by pending `bf7431ce9a12`. After real Clerk sign-in, the dashboard's repository fetch failed; the API logged `no such column: repositories.monitoring_status`. | Tested the existing additive migration on a database snapshot, then applied it locally with a backup and record-preservation checks. |
| Findings repeatedly fetch paginated results | `d6db444` added the whole `cursors` array as an effect dependency and replaced it after every paginated response. A focused test failed before the fix: one page caused two immediate calls. | Depend on the current cursor, so recording the next page does not refetch the current page. |
| Finding status actions fail | `c84d48c` introduced a frontend PATCH to `/findings/{id}/status`; the API exposes PATCH `/findings/{id}`. | Corrected the frontend URL. |
| Finding status filter does nothing | UI sends `status`; both finding endpoints accepted `status_`. | Accept `status`, retaining `status_` compatibility. |
| Issues and PRs show empty placeholders | `7699d01` introduced both pages with static EmptyState components and no GitHub request. There was no working list to regress from in those committed pages. | Retained and checked the existing dirty repository-scoped GitHub listing routes and UI. Added repository-discovery retry and actionable upstream errors. |
| Permission failure can appear to be a clean scan | `563d970` returned `[]` on a security permission failure; `db27591` marked security as full-state, and `04548a2` connected full-state results to auto-resolution. The same error-swallowing pattern existed in dependency and branch protection analyzers. | Retained the dirty error propagation, rejected missing clients and malformed advisories, and updated stale tests that expected errors to become empty results. |
| Acknowledged/ignored findings can recur as duplicates | The upsert only looked for `open` rows. `cef419e` also removed the unique-conflict savepoint recovery. | Reuse acknowledged findings, preserve ignored findings, restore safe unique-conflict recovery, preserve issue publication metadata on rescan, and restrict auto-resolution to the completing analyzer's source. |
| Protected API requests serialize behind Clerk SDK network calls | `0825577` introduced synchronous verification in an async adapter; `e1b47b7` added a synchronous user-email lookup. Browser logs showed consecutive external calls delaying repository and finding requests. | Offload both SDK calls to the thread pool, preserving the same verification and mapping rules; 27 Clerk/identity/isolation checks pass. |
| GitHub timeout produces generic 500/CORS failure | Real Chromium requests reached installation authentication; one access-token request timed out outside the client's previous error handling. | Translate installation and repository transport failures into actionable GitHub API errors, handled inside the normal CORS path. |

## GitHub access blocker

The authenticated E2E user owns two persisted repositories: `editzomni469-bot/kari-ghar` and `editzomni469-bot/Agent-bench-`. Their GitHub installation `161370742` returned **404** from `POST /app/installations/161370742/access_tokens`. A valid installation token was therefore unavailable. This may mean the installation was removed or is inaccessible to the configured GitHub App; the observed 404 alone does not distinguish those cases.

Existing installation IDs, ownership, credentials and permissions were preserved. Reconnecting the correct GitHub App installation is required to verify successful live issue/PR lists and analyzer results. No nonempty live list, successful live scan, or real issue publication is claimed.

## Finding-to-issue workflow

A finding detail now offers a detailed deterministic preview containing its repository, severity, description, evidence, detection time, suggested next steps and verification guidance. Preview generation requires an active persisted analyzer finding with evidence and rejects a known unsuccessful assessment for an on-demand finding.

The server signs a digest of the exact title and body for 15 minutes. Publishing requires the separate approval checkbox and a request with `approved: true`. Ownership and current content are rechecked. A persisted atomic publication claim prevents concurrent/repeated posts; a finding marker checks existing open and closed issues. Rescans preserve that publication record. Uncertain network outcomes are recorded and never blindly reposted; a subsequently observed issue marker can reconcile an accepted request.

GitHub's Issues REST list also contains pull requests, so the list and duplicate lookup exclude resources with `pull_request`. See [GitHub's issues API](https://docs.github.com/en/rest/issues/issues). Clerk's reserved test email verification uses the documented development code after the verification step is prepared; see [Clerk test emails](https://clerk.com/docs/guides/development/testing/test-emails-and-phones).

## Narrow production-code changes made in this session

Backend:

- `app/auth/clerk/adapter.py`: offload synchronous SDK calls without changing authentication checks.
- `app/api/v1/findings.py`: preview/publication endpoints and public status filter.
- `app/api/v1/repositories.py`: public status filter with legacy compatibility.
- `app/schemas/finding.py`: preview and approval request contracts.
- `app/services/finding_issue_service.py`: evidence preview, approval validation and duplicate protection.
- `app/services/finding_service.py`: lifecycle-aware deduplication, source-scoped resolution and publication metadata retention.
- `app/integrations/github/client.py`: issue POST, all-state duplicate lookup, verified 404 absence and transport-error handling.
- `app/monitoring/analyzers/{security,dependency,code_quality}_analyzer.py`: reject unavailable scan contexts; retain source-backed security evidence and reject incomplete advisory data.

Frontend:

- `src/app/(app)/overview/findings/page.tsx`: cursor-effect repair.
- `src/app/(app)/overview/findings/finding-detail-dialog.tsx`: issue preview entry point.
- `src/components/repositories/finding-issue-preview.tsx`: preview, explicit approval, pending/error and result link.
- `src/components/repositories/repository-work-items.tsx`: retry failed repository discovery and keep loading visible until the GitHub request finishes.
- `src/lib/api/findings.ts`: corrected status PATCH URL.
- `src/lib/api/repository-work-items.ts`: backend error-message parsing, GitHub-access guidance and preview/publication requests.

The existing issue/PR page wiring, GitHubWorkItem schema, monitoring-status migration, category mappings, scheduling and health-score changes were already present at arrival. They were inspected and preserved, rather than replaced. Clerk signature, expiry and claim validation, webhook signature verification, BYOK and other unrelated dirty files were retained.

## Database preservation

The original database was backed up to the operating-system temporary directory before migration: `repomedic-before-migration-f51ce8c4d81c4d0a84a971f93d607886.sqlite3`.

After applying `bf7431ce9a12`, SHA-256 checks of every pre-existing column value matched across all **11 data tables**. Repository count remained **4**, finding count remained **0**. New monitoring columns and `ai_analyses.key_insights` came from the existing pending migration. The Alembic revision advanced as intended.

## Verification and limits

- Final backend checks: **187 passed**, including API contracts, ownership, permission/timeout/malformed/incomplete scan preservation, severity/evidence persistence, health deductions, lifecycle deduplication, approval, stale preview rejection, duplicate reconciliation, webhook signatures, Clerk isolation, GitHub App auth and the AI provider. Tests used an isolated SQLite database, not the existing application database. PostgreSQL execution was not performed.
- Frontend checks: **14 tests passed across 7 files** using `npm.cmd test -- --maxWorkers=1`. TypeScript and ESLint over the changed files both exited **0**. Async render assertions were made deterministic, and the multi-step pagination test has a 20-second test timeout for the observed machine contention.
- Clerk follow-up checks: **27 passed**, including signature/expiry/claims, identity mapping, provider isolation and the two new responsiveness tests. This follow-up ran after the thread-pool change.
- Real authenticated Chromium: **1 read-only test passed** against the migrated original database (4.1 minutes). It completed Clerk's normal sign-in and reserved-address verification, then captured Findings plus Issues and Pull Requests for both owned repositories. Findings returned **200** with the actual empty database result. Repository listing returned **200**. Issue and PR requests returned the real installation **404**, and the UI rendered a retry button and installation-access guidance.
- The final Network capture contains **20 API responses**. Console capture contains six expected HTTP-404 resource errors; no uncaught runtime error or CORS failure was captured in this final run. Earlier runs exposed the schema error, GitHub transport error and slow Clerk request scheduling; their logs are retained separately. The final test uses a 90-second assertion timeout to accommodate the observed external Clerk latency.
- Successful live nonempty GitHub lists and a truly empty GitHub repository remain **unverified**, because installation authentication failed. Empty/nonempty/permission/loading states are covered by isolated frontend and backend tests; they are not presented as live GitHub success.
- Full-project ESLint has unrelated pre-existing `no-explicit-any` errors at `src/lib/api/repositories.ts:105` and `src/middleware.ts:37`, plus four existing warnings. Those files were preserved.
- Existing analyzers inspect GitHub metadata, advisories, npm lockfile presence, branch protection and workflow/activity signals. They are not a general source-code vulnerability scanner. File paths are retained when supplied; line numbers are never invented. Dependabot does not supply a source line in the tested contract.
- No real GitHub issue was created. The approval and publication sequence was tested with isolated fixtures and mocked GitHub responses. Live publication still requires a valid installation and explicit approval of a concrete preview.

## Saved evidence

- [Backend regression log: 187 passed](../frontend/.diagnostics/logs/backend-final.log)
- [Clerk follow-up log: 27 passed](../frontend/.diagnostics/logs/clerk-final.log)
- [Frontend tests: 14 passed](../frontend/.diagnostics/logs/frontend-tests.log)
- [Authenticated Chromium run](../frontend/.diagnostics/logs/browser-verified.log)
- [Final Network and console capture](../frontend/.diagnostics/results/repomedic-workflows-render-88804-epository-GitHub-work-items/network.json)
- [Findings screenshot](../frontend/.diagnostics/results/repomedic-workflows-render-88804-epository-GitHub-work-items/findings.png)
- [Issues screenshot, monitored repository](../frontend/.diagnostics/results/repomedic-workflows-render-88804-epository-GitHub-work-items/issues-b6a9fb0f-d7d5-42f6-a967-f96889a9c932.png)
- [PR screenshot, monitored repository](../frontend/.diagnostics/results/repomedic-workflows-render-88804-epository-GitHub-work-items/pull-requests-b6a9fb0f-d7d5-42f6-a967-f96889a9c932.png)
- [Full-project lint limitations](../frontend/.diagnostics/logs/project-eslint.log)

Temporary timing instrumentation was removed. Only the task's temporary database copies and isolated Next.js build output were deleted. The original application's data, the pre-migration backup, existing build directories and unrelated dirty changes were retained. No code was deployed.
