# Clerk E2E suite

This suite is deliberately separate from `frontend/e2e` and its development-adapter configuration. It starts the frontend with Clerk enabled and the backend with `AUTH_PROVIDER=clerk`; it uses a dedicated disposable database. The ordinary E2E command does not read or require any Clerk credentials.

## Clerk test instance

Use a dedicated Clerk development or staging instance, never production credentials. In the Clerk instance:

- Enable email-and-password sign-up and sign-in.
- Use Clerk's documented test-email convention (`+clerk_test`) so generated signup addresses do not require access to a real inbox. If the signup UI requests email verification, the suite enters Clerk's documented test code `424242`.
- Configure the session token template to include an `email` claim, because the backend's verified identity mapping consumes that claim.
- Add `http://localhost:3005` (Clerk E2E frontend) and your normal dev origin as authorized parties.
- Create a persistent E2E account for the sign-in test. Use an email address on the same test domain as the instance and a password permitted by its password policy.
- If Device Trust is enabled, the UI sign-in flow may require a verification code on new browsers. The suite completes that step with Clerk's documented development test code `424242`.
- For the GitHub flow, configure the GitHub App's **Setup URL** as `http://localhost:3005/github/callback` for this local suite. Put the matching App ID, slug, and complete multiline PEM private key in `backend/.env` (or export them in the shell).
- Set `GITHUB_E2E_STORAGE_STATE` to a Playwright storage-state file for a real GitHub account authorized to install/configure this App and select repositories. Keep the state file outside source control. Create it interactively with `npx playwright codegen --save-storage=<path-outside-repo> https://github.com/login` and sign in in the opened browser.

## Required environment

Set these values in the shell or CI secrets store. Do not commit them to `.env` files or source control:

| Variable | Purpose |
| --- | --- |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Publishable key for the dedicated test instance |
| `CLERK_SECRET_KEY` | Secret key for that same test instance; used only by the backend |
| `CLERK_E2E_EMAIL` | Persistent, pre-created test account email |
| `CLERK_E2E_PASSWORD` | Password for the persistent test account |
| `CLERK_E2E_DATABASE_URL` | Disposable database URL reserved for this suite |

The backend also accepts its normal required application settings from the environment. GitHub App ID, slug, and private key must be real values for the App under test; the config does not substitute fake GitHub credentials.

## Run

From `frontend`:

```powershell
npm run test:e2e:clerk
```

The command fails immediately with the missing variable name when required configuration is absent. It applies Alembic migrations to `CLERK_E2E_DATABASE_URL`; never point that variable at a production or shared database.

The ordinary development-adapter suite remains:

```powershell
npm run test:e2e
```

## CI secrets

The independent `clerk-e2e` job in `.github/workflows/e2e.yml` requires these repository or environment secrets. Configure the GitHub App Setup URL to the workflow's local callback path (`http://localhost:3005/github/callback`). The workflow writes the storage-state JSON to the runner's temporary directory, never into the checkout. It runs on pushes, manual runs, and pull requests from the same repository; fork pull requests skip it because GitHub does not expose repository secrets there:

- `CLERK_TEST_PUBLISHABLE_KEY`
- `CLERK_TEST_SECRET_KEY`
- `CLERK_E2E_EMAIL`
- `CLERK_E2E_PASSWORD`
- `GITHUB_APP_ID`
- `GITHUB_APP_SLUG`
- `GITHUB_APP_PRIVATE_KEY`
- `GITHUB_E2E_STORAGE_STATE_JSON` for a dedicated GitHub test account authorized to install/configure the App and select repositories

The CI job maps these secrets to the local variable names above and uses its own ephemeral PostgreSQL database. The `main-e2e` job does not receive Clerk secrets or Clerk environment variables.