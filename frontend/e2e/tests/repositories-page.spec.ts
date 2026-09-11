import { test, expect } from '@playwright/test';
import { login } from '../helpers/auth';

test.describe('Repositories Page Flow', () => {
    test.beforeEach(async ({ page }) => {
        await login(page);
    });

    test('shows empty state and links to settings when no connections exist', async ({ page }) => {
        await page.route('**/api/v1/github/connections', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify([]),
            });
        });

        await page.route('**/api/v1/repositories', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify([]),
            });
        });

        await page.goto('/overview/repositories');

        // Wait for empty state to show up
        await expect(page.locator('text=No repositories connected yet')).toBeVisible();

        // Check if the connect button brings us to github settings
        const connectButton = page.locator('a:has-text("Connect a repository")');
        await expect(connectButton).toBeVisible();
        await expect(connectButton).toHaveAttribute('href', '/overview/settings');
    });

    test('shows connections, adds a repository, and toggles monitoring', async ({ page }) => {
        // 1. Initial state (1 connection, 1 available repo, 0 monitored repos)
        const mockConnections = [{ id: '1', account_login: 'my-org', status: 'active', installation_id: 1234 }];
        const availableRepos = [
            { id: 101, github_repo_id: 101, full_name: 'my-org/core', private: true, already_added: false }
        ];

        let monitoredRepos: any[] = [];

        await page.route('**/api/v1/github/connections', async (route) => {
            await route.fulfill({ status: 200, json: mockConnections });
        });

        await page.route('**/api/v1/github/connections/1/repositories', async (route) => {
            await route.fulfill({ status: 200, json: availableRepos });
        });

        await page.route('**/api/v1/repositories', async (route) => {
            if (route.request().method() === 'GET') {
                await route.fulfill({ status: 200, json: monitoredRepos });
            } else if (route.request().method() === 'POST') {
                // Mock Add Repository
                const addedRepo = {
                    id: 'repo-1',
                    github_repo_id: 101,
                    full_name: 'my-org/core',
                    private: true,
                    monitoring_enabled: false
                };
                monitoredRepos.push(addedRepo);
                availableRepos[0].already_added = true;
                await route.fulfill({ status: 201, json: addedRepo });
            }
        });

        await page.route('**/api/v1/repositories/*', async (route) => {
            if (route.request().method() === 'PATCH') {
                const reqBody = JSON.parse(route.request().postData() || '{}');
                // Target the specific repository mock by updating it
                monitoredRepos[0].monitoring_enabled = reqBody.monitoring_enabled;
                await route.fulfill({ status: 200, json: monitoredRepos[0] });
            }
        });

        await page.goto('/overview/repositories');

        // Assert initial view load
        await expect(page.locator('text=Available Repositories')).toBeVisible();
        await expect(page.locator('text=my-org/core')).toBeVisible();

        // Ensure "Add" button exists prior to addition
        const addButton = page.locator('button:has-text("Add")').first();
        await expect(addButton).toBeVisible();

        // Simulate click
        await addButton.click();

        // Wait for refetch to display the Monitored Repositories category
        await expect(page.locator('text=Monitored Repositories')).toBeVisible();

        // The button state should transition
        await expect(addButton).toHaveText('Added');
        await expect(addButton).toBeDisabled();

        // Locate inside Monitored Repositories
        const switchButton = page.locator('button[role="switch"]');
        await expect(switchButton).toBeVisible();

        // Verify it updates on click
        await expect(switchButton).toHaveAttribute('aria-checked', 'false');
        await switchButton.click();

        await expect(switchButton).toHaveAttribute('aria-checked', 'true');
    });
});
