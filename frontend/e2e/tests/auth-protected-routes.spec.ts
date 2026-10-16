import { test, expect } from '@playwright/test';
import { login, logout } from '../helpers/auth';

test.describe('Authentication and Protected Routes', () => {

    test('unauthenticated user is redirected to Clerk sign-in when accessing protected route', async ({ page }) => {
        // Attempt to navigate to a protected app route
        await page.goto('/overview');

        // We expect the app to redirect us because no cookie is set
        await expect(page).toHaveURL(/.*\/sign-in/);
    });

    test('Clerk login allows access to protected routes', async ({ page }) => {
        // The helper authenticates through the real Clerk sign-in flow.
        await login(page);

        // Now navigate to a protected route
        await page.goto('/overview');

        // Expect we are genuinely on the overview page and not redirected
        await expect(page).toHaveURL(/.*\/overview/);
    });

    test('Clerk logout revokes access', async ({ page }) => {
        await login(page);

        // Validate we're allowed in initially
        await page.goto('/overview');
        await expect(page).toHaveURL(/.*\/overview/);

        // Sign out through Clerk's UI.
        await logout(page);

        // Reload the page. The backend cookie should be invalid/cleared.
        await page.goto('/overview');

        // Thus we expect a redirect to Clerk sign-in.
        await expect(page).toHaveURL(/.*\/sign-in/);
    });

    test('UI login form flow works correctly', async ({ page }) => {
        await page.goto('/login');
        await expect(page).toHaveURL(/.*\/sign-in/);
        await login(page);
        await page.goto('/overview');
        await expect(page).toHaveURL(/.*\/overview/);
    });

});
