import { expect, test } from "@playwright/test";
import { signInThroughClerkUi } from "./helpers/clerk-sign-in";
import { clerkApiFetch } from "./helpers/clerk-api";

const apiUrl = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1`;
const accountEmail = process.env.CLERK_E2E_EMAIL!;
const accountPassword = process.env.CLERK_E2E_PASSWORD!;
const githubStorageState = process.env.GITHUB_E2E_STORAGE_STATE;

test("complete flow: login, install github, add repo, verify dashboard", async ({ page }) => {
    expect(
        githubStorageState,
        "Set GITHUB_E2E_STORAGE_STATE to a Playwright storage-state file for a real GitHub test account.",
    ).toBeTruthy();

    await signInThroughClerkUi(page, accountEmail, accountPassword);
    await page.goto("/overview/settings");

    const popupPromise = page.waitForEvent("popup");
    await page.getByRole("button", { name: /connect github|add another installation/i }).click();
    const installationPopup = await popupPromise;
    const callbackResponsePromise = installationPopup.waitForResponse((response) =>
        response.url().includes("/api/v1/github/install/callback"),
    );

    await expect(installationPopup).toHaveURL(/https:\/\/github\.com\/apps\//);
    for (let step = 0; step < 4; step += 1) {
        if (new URL(installationPopup.url()).origin !== "https://github.com") break;

        const installAction = installationPopup.getByRole("button", {
            name: /^(install|install and authorize|install & authorize|save|configure)$/i,
        }).first();
        if (!(await installAction.isVisible().catch(() => false))) break;
        await installAction.click({ timeout: 15_000 });
    }

    await installationPopup.waitForURL((url) => {
        const installationId = url.searchParams.get("installation_id");
        return (
            url.origin === "http://localhost:3005" &&
            url.pathname === "/github/callback" &&
            Boolean(installationId && /^\d+$/.test(installationId)) &&
            Boolean(url.searchParams.get("setup_action")) &&
            Boolean(url.searchParams.get("state"))
        );
    }, { timeout: 120_000 });

    const callbackUrl = new URL(installationPopup.url());
    const installationId = callbackUrl.searchParams.get("installation_id")!;
    const callbackResponse = await callbackResponsePromise;
    expect(callbackResponse.status()).toBe(200);
    const connection = await callbackResponse.json() as {
        installation_id: number;
        status: string;
    };
    expect(String(connection.installation_id)).toBe(installationId);
    expect(connection.status).toBe("active");
    await expect(page).toHaveURL(/\/overview\/repositories/);

    const connectionsResult = await clerkApiFetch(page, apiUrl, "/github/connections");
    expect(connectionsResult.status).toBe(200);
    const connections = JSON.parse(connectionsResult.body) as Array<{
        installation_id: number;
        status: string;
    }>;
    expect(connections.some((item) =>
        String(item.installation_id) === installationId && item.status === "active",
    )).toBe(true);

    const reposResult = await clerkApiFetch(page, apiUrl, "/repositories");
    expect(reposResult.status).toBe(200);
    const repositories = JSON.parse(reposResult.body) as Array<{
        github_repo_id: number;
        full_name: string;
    }>;
    expect(repositories.length).toBeGreaterThan(0);
    const repository = repositories[0];
    expect(repositories.filter((item) => item.github_repo_id === repository.github_repo_id)).toHaveLength(1);

    await page.goto("/overview/repositories");
    await expect(page.getByText(repository.full_name).first()).toBeVisible({ timeout: 15_000 });

    await page.goto("/overview");
    await expect(page.getByText(`Health check for ${repository.full_name}.`)).toBeVisible({ timeout: 30_000 });

    await page.getByRole("button", { name: "Log out" }).click();

    await signInThroughClerkUi(page, accountEmail, accountPassword);
    await page.goto("/overview");
    await expect(page.getByText(`Health check for ${repository.full_name}.`)).toBeVisible({ timeout: 30_000 });

    const persistedRepos = await clerkApiFetch(page, apiUrl, "/repositories");
    expect(persistedRepos.status).toBe(200);
    expect(JSON.parse(persistedRepos.body).length).toBeGreaterThan(0);
});
