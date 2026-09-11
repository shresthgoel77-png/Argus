import { test, expect } from '@playwright/test';
import { login, logout } from '../helpers/auth';

test.describe('Authentication and Protected Routes', () => {

    test('unauthenticated user is redirected to /login when accessing protected route', async ({ page }) => {
        // Attempt to navigate to a protected app route
        await page.goto('/overview');

        // We expect the app to redirect us because no cookie is set
        await expect(page).toHaveURL(/.*\/login/);
    });

    test('programmatic login allows access to protected routes', async ({ page }) => {
        // Note: We use the helper to establish the session without touching the UI
        await login(page);

        // Now navigate to a protected route
        await page.goto('/overview');

        // Expect we are genuinely on the overview page and not redirected
        await expect(page).toHaveURL(/.*\/overview/);
    });

    test('programmatic logout revokes access', async ({ page }) => {
        await login(page);

        // Validate we're allowed in initially
        await page.goto('/overview');
        await expect(page).toHaveURL(/.*\/overview/);

        // Now log out through the backend programmatic helper
        await logout(page);

        // Reload the page. The backend cookie should be invalid/cleared.
        await page.reload();

        // Thus we expect a redirect to login
        await expect(page).toHaveURL(/.*\/login/);
    });

    test('UI login form flow works correctly', async ({ page }) => {
        // This test actually walks the real UI as per requirements
        await page.goto('/login');

        // Submit the dev login form (assumes there is a submit button)
        // Based on standard dev-login conventions from Prompts 1-6
        const submitButton = page.locator('button:has-text("Continue as dev user")');
        await expect(submitButton).toBeVisible();
        await submitButton.click();

        // Wait for the redirect to overview
        await page.waitForURL(/.*\/overview/, { timeout: 10000 });
        await expect(page).toHaveURL(/.*\/overview/);
    });

});
