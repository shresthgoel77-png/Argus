import { test, expect } from '@playwright/test';
import { login } from '../helpers/auth';

/**
 * Tests for GitHub connection flow.
 * Note: These tests use page.route to mock backend API responses.
 * This ensures deterministic testing of UI states without relying on a real GitHub App backend.
 */
test.describe('GitHub Settings Flow', () => {
    test.beforeEach(async ({ page }) => {
        await login(page);
    });

    test('shows Connect GitHub button when no connections exist and navigates on click', async ({ page }) => {
        // Mock empty connections response
        await page.route('**/api/v1/github/connections', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify([]),
            });
        });

        // Mock install start endpoint
        const mockedInstallUrl = 'https://github.com/apps/test-app/installations/new';
        await page.route('**/api/v1/github/install/start', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ install_url: mockedInstallUrl }),
            });
        });

        await page.goto('/overview/settings');

        // Check empty state
        const connectButton = page.locator('button:has-text("Connect GitHub")');
        await expect(connectButton).toBeVisible();
        await expect(page.locator('text=No GitHub Connection')).toBeVisible();

        // Click the button and check navigation
        await connectButton.click();

        // Ensure that the page redirects to the expected URL
        await page.waitForURL((url) => url.href.includes('github.com/apps'), { timeout: 10000 });
        expect(page.url()).toContain('github.com/apps');
    });

    test('shows existing connections list when data is available', async ({ page }) => {
        // Mock populated connections response
        await page.route('**/api/v1/github/connections', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify([
                    { id: '1', account_login: 'my-org', status: 'active', installation_id: 1234 }
                ]),
            });
        });

        await page.goto('/overview/settings');

        // Verify the existing connection is shown
        await expect(page.locator('text=my-org')).toBeVisible();
        await expect(page.locator('text=Status: active')).toBeVisible();

        // Verify the 'add another' action is available
        const addAnotherButton = page.locator('button:has-text("Add another installation")');
        await expect(addAnotherButton).toBeVisible();
    });

    test('callback page shows success state when completeInstall succeeds', async ({ page }) => {
        // Mock success response for completeInstall
        await page.route('**/api/v1/github/install/callback*', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ id: '1', account_login: 'my-org', status: 'active', installation_id: 1234 }),
            });
        });

        // Use valid callback URL parameters
        await page.goto('/github/callback?installation_id=123&setup_action=install&state=dummy-state');

        // Verify loading first, then success text
        await expect(page.locator('text=Successfully connected to GitHub.')).toBeVisible({ timeout: 10000 });
    });

    test('callback page shows inline error state when completeInstall fails', async ({ page }) => {
        // Mock failure response for completeInstall
        await page.route('**/api/v1/github/install/callback*', async (route) => {
            await route.fulfill({
                status: 400,
                contentType: 'application/json',
                body: JSON.stringify({ detail: 'Invalid state' }),
            });
        });

        await page.goto('/github/callback?installation_id=123&setup_action=install&state=dummy-state');

        // Verify error text
        await expect(page.locator('text=Failed to connect to GitHub.')).toBeVisible({ timeout: 10000 });
        const returnButton = page.locator('button:has-text("Return to Settings")');
        await expect(returnButton).toBeVisible();
        await expect(returnButton).toBeEnabled();
    });
});
