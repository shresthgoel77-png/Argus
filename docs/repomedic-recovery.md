# RepoMedic targeted recovery and verification

Date: 2026-10-16. Starting/current HEAD: `6ab98d3`. This report describes only the additional recovery work after the diagnosis-only session. Previous repairs, unrelated dirty files, untracked migration and original data were retained. No external settings, credentials, installations, issues or PRs were created or changed. No application scan or migration was run.

## Current outcome

| Workflow | Status | Evidence and limits |
| --- | --- | --- |
| Root/sign-in HTTP 500 | PASS | Fresh real GETs to `http://localhost:3000/` and `/sign-in` return 200 with HTML. This is HTTP verification, not authenticated browser verification. |
| Clerk authentication boundary | PASS | Fresh unauthenticated Findings/Issues/PR API requests return 401 `not_authenticated`; authentication was not bypassed. |
| Recovery and assessment regressions | PASS | 221 backend tests, 21 frontend tests, TypeScript and changed-file ESLint pass. GitHub writes in these tests are mocked and use a separate disposable database. |
| Full-project ESLint | FAIL | Existing errors remain at `src/lib/api/repositories.ts:105` and `src/middleware.ts:37`; two existing warnings. These files were preserved. |
| Findings live assessment | BLOCKED | Original database has zero findings; affected repository remains queued with no recorded assessment. No safe correct-account GitHub installation/session was available to run a real scan. |
| Issues live UI/list | BLOCKED | Installation 161370742 remains inaccessible to App 5306913. Public cross-checks show zero open issues on both affected repositories, but do not verify RepoMedic's authenticated workflow. |
| PR live UI/list | BLOCKED | Same installation/session blocker; public cross-checks show zero open PRs. No active PR repository was substituted from another user. |
| Finding-to-issue live preview | BLOCKED | No real verified finding exists locally. Approval, duplicate protection, uncertain outcomes and assessment/evidence rejection were checked with isolated fixtures; nothing was published. |
| Authenticated visible browser | BLOCKED | Fresh browser inventory is `{apps: [], browsers: []}`; selecting localhost reports 'No browser is available'. User reports an existing manually authenticated browser, but it is not exposed to the tools. |

## Confirmed causes and fixes

The GitHub credentials are valid: fresh App-JWT GET `/app` returns 200 for App `5306913`, `argus-og`. GET `/app/installations` returns exactly installation `171410834` on `SGdev-44`, with no next page. The configured App cannot see stored installation `161370742`. GET of that installation returns upstream 404, now mapped by the actual client to 409 `github_installation_unavailable` with same-account reconnect instructions. This check uses App metadata GET, creates no installation token, and is not an authenticated RepoMedic API/browser request. Removal versus ownership by another App remains unknown. The ID was not replaced with 171410834.

Connection upsert previously reassigned cross-user ownership. Rebinding a saved repository previously occurred before access validation. Reconnection now carries the existing owned connection ID in signed state, verifies matching App/account/type, suspension, permissions and access to all saved repositories, then updates only that connection's installation association while preserving connection/repository IDs and history. Cross-user reassignment is rejected before remote calls. New personal-account connections require a verified linked GitHub identity from Clerk. New organization ownership cannot be proved by the existing identity contract, so unverified new organization connections fail closed; existing owned organization connections can reconnect to the same account. No broad OAuth architecture was added.

Preview previously allowed a missing assessment. It now requires a successful relevant assessment, an assessed condition/source and identifying evidence. An unrelated successful age scan cannot authorize an unassessed webhook condition. Webhook-originated findings remain stored but are not automatically advertised as verified previews.

CI previously skipped unknown/missing conclusions as though no failure existed. Missing workflow/run IDs, in-progress or unknown conclusions now return unavailable before synchronization. Stale issue/PR responses are fully validated before persistence, and successful reconciliation targets only the scanner's source and stale type. Webhook findings are retained. A newly added failure-injection test reproduced partial auto-resolution when the second transition failed: one row remained resolved. Full-state synchronization now uses a savepoint and deferred commits; that test and lifecycle regressions pass. Notifications are deferred until successful synchronization.

Upstream permission denial is now HTTP 403 `github_permission_error`; upstream credential rejection is HTTP 502 `github_auth_error`, distinct from Clerk HTTP 401 and local repository ownership HTTP 404. Missing-installation authentication uses a separate actionable 409. Frontend messages follow these distinctions.

## The localhost Internal Server Error

This was caused by the agent's startup command, not a database or credential change. The first frontend was started with `--hostname 127.0.0.1`, while the configured/public origin was `localhost:3000`. Clerk rewrites use the browser origin; Next builds its initial URL from the explicitly configured hostname. These origins differed, so Next treated the rewrite as an external proxy to its own server. The log recorded `Failed to proxy http://localhost:3000/sign-in` / `/dashboard`, `ECONNRESET`, and HTTP 500.

Only the agent-started frontend was stopped and restarted with:

```powershell
npm.cmd run dev -- --hostname localhost -p 3000
```

Both `/` and `/sign-in` then returned HTTP 200; the log recorded 200 in 6.4s and 3.8s respectively. Later checks after restoring generated config also returned 200. No authentication source code, secrets or environment files were changed for this startup fix. The already existing dev script remains unchanged. The local frontend and backend were left running for manual verification, without migrations, scans or scheduler startup. The backend was restarted after the final production-code changes.

## New evidence and actual checks

- [Fresh local HTTP and authentication-boundary responses](../frontend/.diagnostics/recovery/startup-verification.json).
- [Fresh GitHub App/installation/public list checks](../frontend/.diagnostics/recovery/api-evidence.json). Its earlier frontend 500 is retained as before-fix evidence; `startup-verification.json` contains the resolved current response.
- [Final backend: 221 passed](../frontend/.diagnostics/recovery/backend-final.log).
- [Final frontend: 21 tests across 9 files passed](../frontend/.diagnostics/recovery/frontend-tests-final.log).
- [TypeScript: exit 0, no incremental writes](../frontend/.diagnostics/recovery/typecheck-final.log).
- [Changed-file ESLint: exit 0](../frontend/.diagnostics/recovery/lint-targeted-final.log); [final E2E configuration lint: exit 0](../frontend/.diagnostics/recovery/lint-e2e-final.log).
- [Project ESLint: two existing errors/two warnings](../frontend/.diagnostics/recovery/lint-project.log).
- [Reconciliation rollback failure before repair](../frontend/.diagnostics/recovery/atomic-before.log), [focused lifecycle checks after repair: 74 passed](../frontend/.diagnostics/recovery/atomic-after.log).
- [Initial baseline: 66 passed](../frontend/.diagnostics/recovery/baseline-backend.log).
- [Initial broken frontend startup log](../frontend/.diagnostics/recovery/frontend-live.log); [corrected localhost startup log](../frontend/.diagnostics/recovery/frontend-live-localhost.log); [restarted backend log](../frontend/.diagnostics/recovery/backend-live-final.log).

The final backend command selected recovery, connection/repository/finding services, lifecycle, finding-issue/work-item APIs, scheduled monitoring, GitHub client/App auth, issue/PR/security/dependency/quality analyzers, health, Clerk validation/isolation, and webhook tests. It ran with both DATABASE_URL and TEST_DATABASE_URL pointing to an OS-temp disposable SQLite file, never the application test.db. Python syntax parsing of changed files passed. No PostgreSQL execution or live race test was performed. One existing transaction teardown warning remains.

Intermediate checks exposed an encoding error introduced in a test edit (corrected), one mistakenly named nonexistent test selection (corrected), and old generic-404/permission-code expectations (replaced by precise assertions). Final results above are actual runs after the fixes, not those unsuccessful attempts. Node's actual E2E parser was additionally checked in memory: it successfully parsed the configured RSA key for App 5306913 without printing it. No E2E credential login helper was executed in this session.

## Browser access and historical evidence

No new browser screenshot, authenticated Network capture or browser console capture is claimed. Browser inventory is empty. Connector Chrome/IAB launch is unavailable; Playwright's bundled/default Chrome executable paths were absent. The installed system Chrome attempt timed out; the visible launch attempt was rejected by Windows OS error 225 ('file contains a virus or potentially unwanted software'). No security protection was bypassed or disabled.

The existing screenshots and network.json under `frontend/.diagnostics/results/repomedic-workflows-render-88804-epository-GitHub-work-items/` are historical, from the previous authenticated run. They are not verification of this patch.

To connect the user's existing signed-in Chrome profile, follow [official browser-extension setup](https://learn.chatgpt.com/docs/chrome-extension): desktop Settings > Computer Use > Google Chrome, ensure Manage and its toggle are enabled, use the extension in the signed-in profile, then select @Chrome or mention the localhost tab. Grant localhost access when prompted. No credentials, cookies or tokens should be sent to the agent. A separate built-in browser would not inherit the existing Chrome session.

## Preservation

The original database SHA-256 remains `6b51911d1cda52ea00f562590e02f2e3de8eb403f7d76153fb1e5fc76689986c`, matching before work. Counts remain 4 users, 4 repositories, 2 connections, 0 findings and 3 health snapshots; revision remains bf7431ce9a12. No migration, scan, record update, ownership change, credential rotation or external publication was performed.

Of 749 baseline files, 720 remain byte-for-byte unchanged, 29 are the intended existing files listed below, and none are missing. The untracked migration and previous diagnosis report are unchanged. Next-generated tsconfig and next-env changes were restored to their exact saved originals, retaining prior user changes. Runtime output in `frontend/.next-recovery/` is an untracked generated build directory, not source to commit. No Git settings were changed. See [preservation checks](../frontend/.diagnostics/recovery/worktree-preservation.json).

## Every changed source/test file

Paths below identify this session's edits, including files already dirty or untracked before arrival. The three new tests are explicitly described as new. The old report was not overwritten.

| File | Reason |
| --- | --- |
| [`backend/app/api/v1/github.py`](../backend/app/api/v1/github.py) | Bind the reconnect target to the signed install-start/callback flow after ownership checks. |
| [`backend/app/integrations/github/client.py`](../backend/app/integrations/github/client.py) | Distinguish an inaccessible installation during metadata/token authentication from a missing repository. |
| [`backend/app/integrations/github/exceptions.py`](../backend/app/integrations/github/exceptions.py) | Separate missing installations (409), upstream permissions (403), upstream credentials (502), and Clerk authentication (401). |
| [`backend/app/integrations/github/install_state.py`](../backend/app/integrations/github/install_state.py) | Sign the existing connection ID into reconnect state without changing the TTL/signature checks. |
| [`backend/app/monitoring/analyzers/issue_analyzer.py`](../backend/app/monitoring/analyzers/issue_analyzer.py) | Validate the full issue response before atomically reconciling only repository-scan stale-issue findings. |
| [`backend/app/monitoring/analyzers/pull_request_analyzer.py`](../backend/app/monitoring/analyzers/pull_request_analyzer.py) | Apply the same complete-response/source/type constraints to stale PR findings. |
| [`backend/app/services/finding_issue_service.py`](../backend/app/services/finding_issue_service.py) | Require successful relevant assessment, assessed condition/source and identifying evidence before preview/publication. |
| [`backend/app/services/finding_lifecycle_service.py`](../backend/app/services/finding_lifecycle_service.py) | Allow full-state reconciliation to defer auto-resolution commits; preserve standalone defaults. |
| [`backend/app/services/finding_service.py`](../backend/app/services/finding_service.py) | Use one savepoint/commit for full-state upserts/resolutions, defer notifications, and retain source/type scoping. |
| [`backend/app/services/github_connection_service.py`](../backend/app/services/github_connection_service.py) | Reject cross-user reassignment; verify App/account/permissions/repository access before preserving-ID reconnect. Verify Clerk-linked personal identities for new accounts. |
| [`backend/app/services/repository_service.py`](../backend/app/services/repository_service.py) | Verify target installation metadata, matching account and repository access before modifying existing associations. |
| [`backend/app/services/scheduled_monitoring_service.py`](../backend/app/services/scheduled_monitoring_service.py) | Reject missing workflow/run IDs and incomplete or unknown conclusions before CI reconciliation; record workflow evidence. |
| [`backend/tests/conftest.py`](../backend/tests/conftest.py) | Remove substring-based deletion of test.db and explicitly refuse the application database. |
| [`backend/tests/integration/api/v1/test_finding_issue_workflow.py`](../backend/tests/integration/api/v1/test_finding_issue_workflow.py) | Use a successful relevant assessment in verified finding fixtures. |
| [`backend/tests/integration/api/v1/test_repository_github_work_items.py`](../backend/tests/integration/api/v1/test_repository_github_work_items.py) | Require exact permission HTTP 403 and github_permission_error. |
| [`backend/tests/integration/services/test_github_connection_service.py`](../backend/tests/integration/services/test_github_connection_service.py) | Replace unsafe reassignment/identity-replacement expectations with preservation/rejection assertions and realistic metadata. |
| [`backend/tests/integration/services/test_repository_service.py`](../backend/tests/integration/services/test_repository_service.py) | Provide verified target-installation metadata to existing rebind tests. |
| [`backend/tests/integration/test_github_api.py`](../backend/tests/integration/test_github_api.py) | Provide complete verified installation contracts; mock identity proof only in isolated route tests. |
| [`backend/tests/unit/test_github_client.py`](../backend/tests/unit/test_github_client.py) | Assert the dedicated installation error rather than a generic missing-resource error. |
| [`backend/tests/unit/test_issue_analyzer.py`](../backend/tests/unit/test_issue_analyzer.py) | Assert complete-response/source-scoped synchronization instead of per-item writes. |
| [`backend/tests/unit/test_pull_request_analyzer.py`](../backend/tests/unit/test_pull_request_analyzer.py) | Assert the corresponding PR synchronization contract. |
| [`frontend/e2e-clerk/diagnose-flow.spec.ts`](../frontend/e2e-clerk/diagnose-flow.spec.ts) | Remove hard-coded installation callback/state logging and live resource mutations; assert owned repository API success. |
| [`frontend/playwright.clerk.config.ts`](../frontend/playwright.clerk.config.ts) | Parse real multiline backend credentials into the backend child only; remove fake key defaults and automatic migrations; refuse the application DB. |
| [`frontend/src/__tests__/security/playwright-clerk-config.test.ts`](../frontend/src/__tests__/security/playwright-clerk-config.test.ts) | Check credentials, secret isolation, database isolation, no automatic migration, and no hard-coded installation mutation. |
| [`frontend/src/app/(app)/github/callback/page.tsx`](../frontend/src/app/(app)/github/callback/page.tsx) | Display actionable server errors and avoid logging signed callback state. |
| [`frontend/src/app/(app)/overview/settings/github-callback-processor.tsx`](../frontend/src/app/(app)/overview/settings/github-callback-processor.tsx) | Use the signed callback flow, display failures, and reject installation-ID-only callbacks. |
| [`frontend/src/app/(app)/overview/settings/github-settings-card.tsx`](../frontend/src/app/(app)/overview/settings/github-settings-card.tsx) | Offer Reconnect for the selected existing connection; do not show an unconditional green connected indicator. |
| [`frontend/src/lib/api/github.ts`](../frontend/src/lib/api/github.ts) | Carry the selected connection ID into install-start and propagate safe callback errors. |
| [`frontend/src/lib/api/repository-work-items.ts`](../frontend/src/lib/api/repository-work-items.ts) | Distinguish Clerk sign-in, local ownership, GitHub credentials, permissions and installation errors. |
| [`backend/tests/integration/test_recovery_integrity.py`](../backend/tests/integration/test_recovery_integrity.py) | New focused reconnect, account-proof, invalid CI/evidence, rollback, preservation and error-mapping regressions. |
| [`frontend/src/__tests__/overview/work-item-errors.test.ts`](../frontend/src/__tests__/overview/work-item-errors.test.ts) | New distinct authentication/authorization/installation error guidance tests. |
| [`frontend/src/__tests__/overview/github-reconnect.test.tsx`](../frontend/src/__tests__/overview/github-reconnect.test.tsx) | New selected-existing-connection reconnect UI regression. |

This new report (`docs/repomedic-recovery.md`) and the JSON/log artifacts in `frontend/.diagnostics/recovery/` record the repair and evidence. `changed-files.json` provides the same source/test manifest in machine-readable form. Generated runtime build files are separate from this source/test list.

## Manual actions and post-access verification

1. Connect the existing browser as described above. Keep the existing owning Clerk account; do not switch to another user's installation to pass checks.
2. As `editzomni469-bot`, inspect GitHub Settings > Applications > Installed GitHub Apps and find the exact [Argus-OG App](https://github.com/apps/argus-og), ID 5306913. If absent, that account owner must authorize its installation. The agent has not installed anything. Refer to [GitHub's installed-App instructions](https://docs.github.com/en/apps/using-github-apps/reviewing-and-modifying-installed-github-apps).
3. Inspect repository selection: include both `kari-ghar` and `Agent-bench-`. Required permissions are Issues write; Pull requests, Contents, Actions, Administration and vulnerability alerts read. Do not guess an installation ID or use 171410834, which is a different account and local owner. If this App cannot be installed on that account, the App owner must review its installation eligibility; no setting was changed here.
4. In RepoMedic Settings choose **Reconnect editzomni469-bot**. The signed callback must refer to the same owned connection/account; the server verifies repositories and permissions before updating it. A failure leaves existing records untouched. If the GitHub redirect is misconfigured, the App owner should inspect its Setup URL against the existing frontend callback routes; changing it requires explicit authorization.
5. Once correct installation access and the owning authenticated browser are verified, approve one known repository scan. Inspect real file/line evidence when supplied, severity, persisted findings, complete-check status and health history. An empty queue or old score of 100 is insufficient proof of a successful scan.
6. Compare actual scoped issue/PR API results to GitHub for empty and active accessible repositories. Public checks currently show both affected repositories have no open issues or PRs; no active data was invented.
7. Preview a real assessed finding, verify the approval gate and existing-issue marker behavior without publishing. Real issue creation requires separate explicit approval of a concrete preview.
8. Check fresh browser Network/console/screenshots, and repeat read-only database preservation checks. Failed/incomplete scan preservation is currently proven by isolated tests, not a failure injected into the user's live data.
