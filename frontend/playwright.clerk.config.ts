import { defineConfig, devices } from "@playwright/test";
import path from "path";
import fs from "fs";
import { parseEnv } from "node:util";

try {
    // Node's parser preserves multiline PEMs and existing environment overrides.
    process.loadEnvFile(path.resolve(__dirname, ".env"));
} catch { /* Required values below fail clearly if configuration is absent. */ }

const requiredEnvironment = [
    "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY",
    "CLERK_SECRET_KEY",
    "CLERK_E2E_EMAIL",
    "CLERK_E2E_PASSWORD",
    "CLERK_E2E_DATABASE_URL",
] as const;

for (const name of requiredEnvironment) {
    if (!process.env[name]) {
        throw new Error(`Clerk E2E requires ${name} to be set.`);
    }
}

const clerkPublishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY!;
const clerkSecretKey = process.env.CLERK_SECRET_KEY!;
const databaseUrl = process.env.CLERK_E2E_DATABASE_URL!;

// Read backend-only secrets into the backend child environment, never process.env.
const backendEnvPath = path.resolve(__dirname, "../backend/.env");
const backendFileEnvironment = fs.existsSync(backendEnvPath)
    ? parseEnv(fs.readFileSync(backendEnvPath, "utf8")) : {};
const databaseIdentity = (url: string) => url.startsWith("sqlite:///")
    ? path.resolve(__dirname, "../backend", url.slice("sqlite:///".length)).toLowerCase() : url;
if (backendFileEnvironment.DATABASE_URL && databaseIdentity(databaseUrl) === databaseIdentity(backendFileEnvironment.DATABASE_URL)) {
    throw new Error("Clerk E2E requires a separate disposable database, not the application database.");
}
const requiredBackendEnvironment = [
    "GITHUB_APP_ID", "GITHUB_APP_SLUG", "GITHUB_APP_PRIVATE_KEY",
    "GITHUB_APP_WEBHOOK_SECRET", "AI_CREDENTIAL_ENCRYPTION_KEY",
] as const;

const backendEnvironment: Record<string, string> = {
    ...backendFileEnvironment,
    ...Object.fromEntries(
        Object.entries(process.env).filter(([, value]) => value !== undefined),
    ),
    APP_ENV: "test",
    AUTH_PROVIDER: "clerk",
    DATABASE_URL: databaseUrl,
    CLERK_SECRET_KEY: clerkSecretKey,
    CLERK_AUTHORIZED_PARTIES: "http://localhost:3005",
};
for (const name of requiredBackendEnvironment) {
    if (!backendEnvironment[name]) throw new Error(`Clerk E2E requires ${name} to be configured.`);
}

delete backendEnvironment.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
delete backendEnvironment.CLERK_E2E_EMAIL;
delete backendEnvironment.CLERK_E2E_PASSWORD;
delete backendEnvironment.CLERK_E2E_DATABASE_URL;

const frontendEnvironment = Object.fromEntries(
    Object.entries(process.env).filter(([, value]) => value !== undefined),
) as Record<string, string>;
delete frontendEnvironment.CLERK_SECRET_KEY;
delete frontendEnvironment.CLERK_E2E_EMAIL;
delete frontendEnvironment.CLERK_E2E_PASSWORD;
delete frontendEnvironment.CLERK_E2E_DATABASE_URL;
frontendEnvironment.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY = clerkPublishableKey;
frontendEnvironment.NEXT_PUBLIC_CLERK_SIGN_IN_URL = "/sign-in";
frontendEnvironment.NEXT_PUBLIC_CLERK_SIGN_UP_URL = "/sign-up";
frontendEnvironment.NEXT_PUBLIC_API_URL = "http://localhost:8005";
frontendEnvironment.NEXT_DIST_DIR = ".next-clerk-e2e";
process.env.NEXT_PUBLIC_API_URL = "http://localhost:8005";

export default defineConfig({
    testDir: "./e2e-clerk",
    fullyParallel: false,
    forbidOnly: !!process.env.CI,
    workers: 1,
    reporter: "list",
    timeout: 180_000,
    use: {
        ...devices["Desktop Chrome"],
        baseURL: "http://localhost:3005",
        trace: "retain-on-failure",
    },
    webServer: [
        {
            command: ".\\venv\\Scripts\\python.exe -m uvicorn app.main:app --port 8005",
            cwd: "../backend",
            url: "http://localhost:8005/api/v1/health",
            reuseExistingServer: true,
            timeout: 120_000,
            env: backendEnvironment,
        },
        {
            command: "npm run dev -- -p 3005",
            url: "http://localhost:3005",
            reuseExistingServer: true,
            timeout: 120_000,
            env: frontendEnvironment,
        },
    ],
});
