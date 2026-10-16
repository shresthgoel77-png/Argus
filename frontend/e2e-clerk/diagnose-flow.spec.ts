import { expect, test } from "@playwright/test";
import { login } from "../e2e/helpers/auth";

// Read-only: use installations actually owned by the signed-in account.
test("loads repositories belonging to the authenticated account", async ({ page }) => {
    await login(page);
    const responsePromise = page.waitForResponse(response => new URL(response.url()).pathname === "/api/v1/repositories");
    await page.goto("/overview/repositories");
    const response = await responsePromise;
    expect(response.status()).toBe(200);
    expect(Array.isArray(await response.json())).toBe(true);
    await expect(page.getByRole("heading", { name: "Repositories", exact: true })).toBeVisible();
    await expect(page.locator("body")).not.toContainText("Internal Server Error");
    await page.goto("/overview/findings");
    await expect(page.getByRole("heading", { name: "Findings", exact: true })).toBeVisible();
});
