import { Page, expect } from '@playwright/test';

/**
 * Signs in through Clerk using the dedicated E2E account configured in .env.
 */
export async function login(page: Page) {
    const email = process.env.CLERK_E2E_EMAIL;
    const password = process.env.CLERK_E2E_PASSWORD;
    if (!email || !password) {
        throw new Error('CLERK_E2E_EMAIL and CLERK_E2E_PASSWORD are required for authenticated E2E tests.');
    }

    await page.goto('/sign-in');
    await page.getByRole('textbox', { name: /email address/i }).fill(email);
    await page.getByRole('button', { name: /continue/i }).click();
    await page.getByLabel(/password/i).first().fill(password);
    const trustPrepared = page.waitForResponse(response =>
        /prepare_(second_factor|verification)/.test(new URL(response.url()).pathname) && response.status() === 200,
        { timeout: 30_000 },
    ).catch(() => null);
    await page.getByRole('button', { name: /continue/i }).click();
    // Clerk's reserved test addresses use its documented development OTP.
    if (email.includes("+clerk_test@")) {
        await page.waitForURL(/\/overview|\/dashboard|\/sign-in\/client-trust/);
        if (page.url().includes("/client-trust")) {
            if (!await trustPrepared) {
                await page.getByRole("button", { name: /resend/i }).click();
            }
            await page.getByRole("textbox", { name: "Enter verification code" }).pressSequentially("424242");
            // The OTP component submits automatically after the sixth digit.
        }
    }
    await expect(page).not.toHaveURL(/\/sign-in/);
}

/**
 * Signs out through Clerk's frontend session.
 */
export async function logout(page: Page) {
    await page.getByRole('button', { name: /log out/i }).click();
    await expect(page).toHaveURL(/\/$/);
}
