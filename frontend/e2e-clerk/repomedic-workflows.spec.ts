import fs from "node:fs";
import { expect, test } from "@playwright/test";
import { login } from "../e2e/helpers/auth";

test("renders authenticated findings and real repository GitHub work items", async ({ page }, testInfo) => {
    const network: { path: string; status: number; body: unknown }[] = [];
    const consoleErrors: string[] = [];
    page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()); });
    page.on("pageerror", error => consoleErrors.push(error.message));
    page.on("response", async response => {
        const url = new URL(response.url());
        if (url.pathname.startsWith("/api/v1/") && !url.pathname.includes("auth")) {
            network.push({ path: url.pathname, status: response.status(), body: await response.json().catch(() => null) });
        }
    });
    try {
        await login(page);
        await page.goto("/overview/findings");
        await expect(page.getByRole("heading", { name: "Findings", exact: true })).toBeVisible();
        await expect(page.getByLabel("Loading findings")).toHaveCount(0);
        await page.screenshot({ path: testInfo.outputPath("findings.png"), fullPage: true });
        for (const kind of ["issues", "pull-requests"] as const) {
            const repositoriesResponse = page.waitForResponse(r => new URL(r.url()).pathname === "/api/v1/repositories");
            await page.goto(`/overview/${kind}`);
            const response = await repositoriesResponse;
            expect(response.status()).toBe(200);
            const repositories = await response.json() as { id: string; full_name: string }[];
            if (!repositories.length) {
                await expect(page.getByText("No repositories connected")).toBeVisible();
            }
            for (const repository of repositories) {
                const path = `/api/v1/repositories/${repository.id}/${kind}`;
                let request = network.findLast(entry => entry.path === path);
                if (await page.getByLabel("Select repository").inputValue() !== repository.id) {
                    const loaded = page.waitForResponse(r => new URL(r.url()).pathname === path);
                    await page.getByLabel("Select repository").selectOption(repository.id);
                    const upstream = await loaded;
                    request = { path, status: upstream.status(), body: await upstream.json() };
                } else if (!request) {
                    await expect.poll(() => network.some(entry => entry.path === path)).toBe(true);
                    request = network.findLast(entry => entry.path === path);
                }
                expect(request).toBeTruthy();
                if (request!.status === 200) {
                    const items = request!.body as { title: string; html_url: string }[];
                    if (items.length) {
                        await expect(page.getByRole("heading", { name: new RegExp(items[0].title.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) })).toBeVisible();
                        await expect(page.getByRole("link", { name: "View on GitHub" }).first()).toHaveAttribute("href", items[0].html_url);
                    } else {
                        await expect(page.getByText(`No open ${kind === "issues" ? "issues" : "pull requests"}`, { exact: true })).toBeVisible();
                    }
                } else {
                    await expect(page.locator("section").getByRole("alert")).toBeVisible();
                    await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
                }
                await page.screenshot({ path: testInfo.outputPath(`${kind}-${repository.id}.png`), fullPage: true });
            }
        }
    } finally {
        fs.writeFileSync(testInfo.outputPath("network.json"), JSON.stringify({ network, consoleErrors }, null, 2));
        console.info("RepoMedic Network evidence:", JSON.stringify(network.map(({path, status}) => ({path, status}))));
        await testInfo.attach("api-responses.json", { body: JSON.stringify(network, null, 2), contentType: "application/json" });
        await testInfo.attach("console-errors.json", { body: JSON.stringify(consoleErrors, null, 2), contentType: "application/json" });
    }
});
