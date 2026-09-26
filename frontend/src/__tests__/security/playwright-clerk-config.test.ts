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
});
