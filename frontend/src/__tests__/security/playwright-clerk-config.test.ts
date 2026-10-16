import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("Clerk Playwright configuration", () => {
    it("does not write credential material to the console", () => {
        const config = readFileSync(
            resolve(process.cwd(), "playwright.clerk.config.ts"),
            "utf8",
        );

        expect(config).not.toMatch(
            /\bconsole\s*\.\s*(?:log|info|warn|error|debug|trace)\s*\(/,
        );
    });
    it("requires real App credentials and never applies migrations during startup", () => {
        const config = readFileSync(resolve(process.cwd(), "playwright.clerk.config.ts"), "utf8");
        expect(config).not.toContain("test-pem");
        expect(config).not.toContain("alembic upgrade");
        expect(config).toContain("separate disposable database");
        expect(config).toContain("process.loadEnvFile");
        expect(config).toContain("parseEnv(fs.readFileSync(backendEnvPath");
        expect(config).not.toMatch(/process\.loadEnvFile\([^;]*backend/);
        expect(config).toContain('"GITHUB_APP_PRIVATE_KEY",');
        const diagnostic = readFileSync(resolve(process.cwd(), "e2e-clerk/diagnose-flow.spec.ts"), "utf8");
        expect(diagnostic).not.toContain("161370742");
        expect(diagnostic).not.toContain("install/callback");
        expect(diagnostic).not.toContain("Grabbed state");
    });
});
