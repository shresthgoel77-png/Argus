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

    test('opens GitHub in a secondary tab and preserves settings', async ({ page }) => {
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

        // The settings page stays open while GitHub is launched separately.
        const popupPromise = page.waitForEvent('popup');
        await connectButton.click();
        const popup = await popupPromise;

        await expect.poll(() => new URL(popup.url()).hostname).toBe('github.com');
        const popupUrl = new URL(popup.url());
        expect(
            popupUrl.pathname === '/apps/test-app/installations/new'
                || popupUrl.searchParams.get('return_to')?.includes('/apps/test-app/installations/new'),
        ).toBeTruthy();
        await expect(page).toHaveURL(/\/overview\/settings$/);
    });

    test('refreshes the connection state when settings regains focus', async ({ page }) => {
        let installationDetected = false;
        await page.route('**/api/v1/github/connections', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify(installationDetected ? [
                    { id: '1', account_login: 'my-org', status: 'active', installation_id: 1234 }
                ] : []),
            });
        });

        await page.goto('/overview/settings');
        await expect(page.locator('text=No GitHub Connection')).toBeVisible();

        installationDetected = true;
        await page.evaluate(() => window.dispatchEvent(new Event('focus')));
        await expect(page.locator('text=my-org')).toBeVisible();
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
        await page.route('**/api/v1/github/connections', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify([
                    { id: '1', account_login: 'my-org', status: 'active', installation_id: 1234 }
                ]),
            });
        });
        await page.route('**/api/v1/repositories', async (route) => {
            await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
        });
        await page.route('**/api/v1/github/connections/1/repositories', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify([
                    { github_repo_id: 101, full_name: 'my-org/project', private: false, already_added: false }
                ]),
            });
        });

        // Use valid callback URL parameters
        await page.goto('/github/callback?installation_id=123&setup_action=install&state=dummy-state');

        // Verify loading first, then success text
        await expect(page.locator('text=Successfully connected to GitHub.')).toBeVisible({ timeout: 10000 });
        await expect(page.locator('text=Available Repositories')).toBeVisible({ timeout: 10000 });
        await expect(page.locator('text=my-org/project')).toBeVisible();
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
