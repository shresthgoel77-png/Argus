import { setupClerkTestingToken } from "@clerk/testing/playwright";
import { expect, type Page } from "@playwright/test";

/** Clerk's documented test verification code for development/test instances. */
const CLERK_TEST_VERIFICATION_CODE = "424242";

/**
 * Completes legitimate Clerk second-factor / Device Trust (client-trust) steps when
 * the hosted SignIn UI requests a verification code after password entry.
 */
export async function completeClerkVerificationSteps(page: Page) {
    const codeField = page.getByRole("textbox", {
        name: /verification code|enter code|one-time code/i,
    });
    const verificationRequired = await codeField
        .waitFor({ state: "visible", timeout: 10_000 })
        .then(() => true)
        .catch(() => false);

    if (verificationRequired) {
        const resendButton = page.getByRole("button", { name: /resend.*code/i });
        if (
            (await resendButton.isVisible().catch(() => false)) &&
            (await resendButton.isEnabled().catch(() => false))
        ) {
            await resendButton.click({ timeout: 5_000 });
        }
        await codeField.fill(CLERK_TEST_VERIFICATION_CODE, { timeout: 5_000 });
        const submitButton = page.getByRole("button", { name: /continue|verify|submit/i });
        if (await submitButton.isVisible().catch(() => false)) {
            await submitButton.click({ timeout: 5_000 });
        }
    }

    await expect(page).not.toHaveURL(/\/sign-in|\/sign-up/, { timeout: 45_000 });
}

async function prepareClerkTestingPage(page: Page) {
    await page.goto("/");
    await setupClerkTestingToken({ page });
}

export async function signInThroughClerkUi(
    page: Page,
    accountEmail: string,
    accountPassword: string,
) {
    await prepareClerkTestingPage(page);
    await page.goto("/sign-in");
    await page.getByRole("textbox", { name: /email address/i }).fill(accountEmail);
    await page.getByRole("button", { name: /continue/i }).click();
    await page.getByLabel(/password/i).first().fill(accountPassword);
    await page.getByRole("button", { name: /continue/i }).click();
    await completeClerkVerificationSteps(page);
    await expect(page).not.toHaveURL(/\/sign-in/);
}

export async function signUpThroughClerkUi(
    page: Page,
    signupEmail: string,
    accountPassword: string,
) {
    await prepareClerkTestingPage(page);
    await page.goto("/sign-up");
    await page.getByRole("textbox", { name: /email address/i }).fill(signupEmail);
    await page.getByLabel(/password/i).first().fill(accountPassword);
    await page.getByRole("button", { name: /continue/i }).click();

    await completeClerkVerificationSteps(page);
    await expect(page).not.toHaveURL(/\/sign-up/);
}
