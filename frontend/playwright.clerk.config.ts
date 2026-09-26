import { defineConfig, devices } from "@playwright/test";
import fs from "fs";
import path from "path";

try {
    const envPath = path.resolve(__dirname, ".env");
    const envContent = fs.readFileSync(envPath, "utf8");
    for (const line of envContent.split("\n")) {
        if (line.includes("=")) {
            const parts = line.split("=");
            const key = parts[0].trim();
            const val = parts.slice(1).join("=").trim().replace(/"/g, '');
            process.env[key] = val;
            if (key === 'CLERK_SECRET_KEY') console.log("Playwright SK loaded:", val.substring(0, 15) + "...");
        }
    }
} catch (e) { }

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

const backendEnvironment: Record<string, string> = {
    ...Object.fromEntries(
        Object.entries(process.env).filter(([, value]) => value !== undefined),
    ),
    APP_ENV: "test",
    AUTH_PROVIDER: "clerk",
    DATABASE_URL: databaseUrl,
    CLERK_SECRET_KEY: clerkSecretKey,
    CLERK_AUTHORIZED_PARTIES: "http://localhost:3005",
    GITHUB_APP_ID: process.env.GITHUB_APP_ID || "12345",
    GITHUB_APP_SLUG: process.env.GITHUB_APP_SLUG || "clerk-e2e-test",
    GITHUB_APP_PRIVATE_KEY: process.env.GITHUB_APP_PRIVATE_KEY || "test-pem",
    GITHUB_APP_WEBHOOK_SECRET: process.env.GITHUB_APP_WEBHOOK_SECRET || "test-secret",
    AI_CREDENTIAL_ENCRYPTION_KEY:
        process.env.AI_CREDENTIAL_ENCRYPTION_KEY ||
        "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
};
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
            command: ".\\venv\\Scripts\\python.exe -m alembic upgrade head && .\\venv\\Scripts\\python.exe -m uvicorn app.main:app --port 8005",
            cwd: "../backend",
            url: "http://localhost:8005/api/v1/health",
            reuseExistingServer: false,
            timeout: 120_000,
            env: backendEnvironment,
        },
        {
            command: "npm run dev -- -p 3005",
            url: "http://localhost:3005",
            reuseExistingServer: false,
            timeout: 120_000,
            env: frontendEnvironment,
        },
    ],
});