import { expect, test, type Page } from "@playwright/test";

const apiUrl = "http://localhost:8000/api/v1";
const accountEmail = process.env.CLERK_E2E_EMAIL!;
const accountPassword = process.env.CLERK_E2E_PASSWORD!;

async function signIn(page: Page) {
    await page.goto("/sign-in");
    await page.getByRole("textbox", { name: /email address/i }).fill(accountEmail);
    await page.getByRole("button", { name: /continue/i }).click();
    await page.getByLabel(/password/i).first().fill(accountPassword);
    await page.getByRole("button", { name: /continue/i }).click();
    await expect(page).not.toHaveURL(/\/sign-in/);
}

async function getCurrentUser(page: Page) {
    return page.request.get(`${apiUrl}/auth/me`);
}

test("denies protected routes without a Clerk session", async ({ page }) => {
    await page.goto("/overview");
    await expect(page).toHaveURL(/\/sign-in/);
});

test("signs up through Clerk and provisions a stable internal user", async ({ page }) => {
    const [, emailDomain] = accountEmail.split("@");
    const signupEmail = `clerk-e2e-${Date.now()}+clerk_test@${emailDomain}`;

    await page.goto("/sign-up");
    await page.getByRole("textbox", { name: /email address/i }).fill(signupEmail);
    await page.getByLabel(/password/i).first().fill(accountPassword);
    await page.getByRole("button", { name: /continue/i }).click();
    const verificationCode = page.getByLabel(/verification code/i);
    const needsVerification = await verificationCode
        .waitFor({ state: "visible", timeout: 5_000 })
        .then(() => true)
        .catch(() => false);
    if (needsVerification) {
        await verificationCode.fill("424242");
        await page.getByRole("button", { name: /verify|continue/i }).click();
    }
    await expect(page).not.toHaveURL(/\/sign-up/);

    await page.goto("/overview");
    await expect(page.getByRole("button", { name: "Log out" })).toBeVisible();

    const firstResponse = await getCurrentUser(page);
    expect(firstResponse.status()).toBe(200);
    const firstUser = await firstResponse.json();
    expect(firstUser.email).toBe(signupEmail);
    expect(firstUser.id).toBeTruthy();

    await page.reload();
    const persistedResponse = await getCurrentUser(page);
    expect(persistedResponse.status()).toBe(200);
    expect((await persistedResponse.json()).id).toBe(firstUser.id);
});

test("signs in with Clerk and persists the session across reloads", async ({ page }) => {
    await signIn(page);
    await page.goto("/overview");
    await expect(page.getByRole("button", { name: "Log out" })).toBeVisible();

    const firstResponse = await getCurrentUser(page);
    expect(firstResponse.status()).toBe(200);
    const firstUser = await firstResponse.json();
    expect(firstUser.email.toLowerCase()).toBe(accountEmail.toLowerCase());

    await page.reload();
    await expect(page.getByRole("button", { name: "Log out" })).toBeVisible();
    const persistedResponse = await getCurrentUser(page);
    expect(persistedResponse.status()).toBe(200);
    expect((await persistedResponse.json()).id).toBe(firstUser.id);
});

test("rejects an expired Clerk session token", async ({ page, request }) => {
    test.setTimeout(240_000);
    await signIn(page);

    const sessionToken = await page.evaluate(async () => {
        const clerk = (window as Window & {
            Clerk?: { session?: { getToken: () => Promise<string | null> } | null };
        }).Clerk;
        return clerk?.session?.getToken() ?? null;
    });
    expect(sessionToken).toBeTruthy();

    const payload = JSON.parse(
        Buffer.from(sessionToken!.split(".")[1], "base64url").toString("utf8"),
    ) as { exp?: number };
    expect(payload.exp).toBeTruthy();
    const delay = payload.exp! * 1000 - Date.now() + 1_000;
    expect(delay).toBeLessThanOrEqual(180_000);
    if (delay > 0) await page.waitForTimeout(delay);

    const expiredResponse = await request.get(`${apiUrl}/auth/me`, {
        headers: { Authorization: `Bearer ${sessionToken}` },
    });
    expect(expiredResponse.status()).toBe(401);
});

test("sign-out invalidates the Clerk session in the frontend and backend", async ({ page }) => {
    await signIn(page);
    await page.goto("/overview");
    await expect(page.getByRole("button", { name: "Log out" })).toBeVisible();
    expect((await getCurrentUser(page)).status()).toBe(200);

    await page.getByRole("button", { name: "Log out" }).click();
    await expect(page).toHaveURL(/\/$/);

    await page.goto("/overview");
    await expect(page).toHaveURL(/\/sign-in/);
    expect((await getCurrentUser(page)).status()).toBe(401);
});