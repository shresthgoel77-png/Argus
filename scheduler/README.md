# Argus Scheduler Worker

This is a minimal, standalone Cloudflare Worker (cron trigger) whose sole job is to call the Argus backend on a schedule.

## Local Development & Testing

1. Ensure you have Node.js and npm installed.
2. Install Cloudflare Wrangler globally or run via `npx`:
   ```bash
   npm install -g wrangler
   ```
3. Copy `.env.example` to `.dev.vars` and fill in the values:
   ```bash
   cp .env.example .dev.vars
   ```
   > **Note:** `.dev.vars` is ignored by git to protect your secrets.

4. Test locally using Wrangler:
   ```bash
   wrangler dev --test-scheduled
   ```
   Once `wrangler dev` is running, you can simply press **`s`** in the terminal to manually trigger the scheduled event.

## Secrets Management

`SCHEDULER_SHARED_SECRET` is required for production and must match the backend's expected header.

**Never store this secret in `wrangler.toml` or in source control.**

To configure it for production deployment:
```bash
wrangler secret put SCHEDULER_SHARED_SECRET
# Paste your secret when prompted
```

*Note: If you rotate this secret, you must update it in both the backend configuration and here (by running the secret put command again).*

## Deployment

Deploy to Cloudflare (Free Tier):
```bash
wrangler deploy
```

The backend URL is set via an environment variable. If deploying to production, ensure you supply the correct target via the dashboard or add `BACKEND_URL` securely to your workers env.
