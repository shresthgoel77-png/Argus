import { expect, test } from "@playwright/test";

const apiUrl = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1`;
const accountEmail = process.env.CLERK_E2E_EMAIL!;
const accountPassword = process.env.CLERK_E2E_PASSWORD!;

test("complete flow: login, install github, add repo, verify dashboard", async ({ page, context }) => {
    await page.goto("/sign-in");
    await page.getByRole("textbox", { name: /email address/i }).fill(accountEmail);
    await page.getByRole("button", { name: /continue/i }).click();
    await page.getByLabel(/password/i).first().fill(accountPassword);
    await page.getByRole("button", { name: /continue/i }).click();
    await expect(page).toHaveURL(/\/overview/);

    const stateUrl = await page.evaluate(async (apiUrl) => {
        const res = await fetch(`${apiUrl}/github/install/start`, { credentials: "include" });
        const data = await res.json();
        return data.install_url;
    }, apiUrl);

    expect(stateUrl).toContain("github.com/apps/");
    const installUrl = new URL(stateUrl);
    const state = installUrl.searchParams.get("state");
    expect(state).toBeTruthy();
    console.log("Grabbed state:", state);

    const callbackRes = await page.request.get(`${apiUrl}/github/install/callback?installation_id=161370742&setup_action=install&state=${state}`);
    expect(callbackRes.status()).toBe(200);
    console.log("GitHub install complete");

    await page.goto("/overview/settings");
    await page.waitForTimeout(2000);
    const connectionsCount = await page.locator("text=Status:").count();
    expect(connectionsCount).toBeGreaterThan(0);

    await page.goto("/overview/repositories");
    const addButton = page.getByRole("button", { name: /Add|Select|Connect/i }).first();
    if (await addButton.isVisible()) {
        await addButton.click();
        await page.waitForTimeout(2000); // give it time to persist
    }

    await page.goto("/overview");
    console.log("Checking dashboard for repository");
    await page.waitForTimeout(2000);

    const repoText = await page.locator("body").innerText();
    console.log("================= Dashboard text =================");
    console.log(repoText.substring(0, 500));
    console.log("==================================================");

    await page.getByRole("button", { name: "Log out" }).click();

    await page.goto("/sign-in");
    await page.getByRole("textbox", { name: /email address/i }).fill(accountEmail);
    await page.getByRole("button", { name: /continue/i }).click();
    await page.getByLabel(/password/i).first().fill(accountPassword);
    await page.getByRole("button", { name: /continue/i }).click();
    await expect(page).toHaveURL(/\/overview/);

    await page.waitForTimeout(2000);
    const repoText2 = await page.locator("body").innerText();
    console.log("================= Dashboard text after reconnect =================");
    console.log(repoText2.substring(0, 500));
    console.log("==================================================================");
});
