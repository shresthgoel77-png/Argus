import { test, expect } from '@playwright/test';
import { login } from '../helpers/auth';

test.describe('Notification Preferences Settings Flow', () => {
    test.beforeEach(async ({ page }) => {
        await login(page);
    });

    test('loads and displays current notification preferences', async ({ page }) => {
        await page.route('**/api/v1/notifications/preferences', async (route) => {
            if (route.request().method() === 'GET') {
                await route.fulfill({
                    status: 200,
                    contentType: 'application/json',
                    body: JSON.stringify({
                        email_enabled: true,
                        min_severity_email: 'high'
                    }),
                });
            } else {
                await route.continue();
            }
        });

        await page.goto('/overview/settings');

        // Check the card title
        await expect(page.locator('text=Notification Preferences')).toBeVisible();

        // Check if the toggle is set correctly
        const emailToggle = page.locator('#notification-preferences button[role="switch"]');
        await expect(emailToggle).toHaveAttribute('aria-checked', 'true');

        // Check if the select is set to high
        const severitySelect = page.locator('#notification-preferences select');
        await expect(severitySelect).toHaveValue('high');
    });

    test('toggles preferences and saves successfully', async ({ page }) => {
        // Mock GET load
        await page.route('**/api/v1/notifications/preferences', async (route) => {
            if (route.request().method() === 'GET') {
                await route.fulfill({
                    status: 200,
                    contentType: 'application/json',
                    body: JSON.stringify({
                        email_enabled: false,
                        min_severity_email: 'critical'
                    }),
                });
            } else if (route.request().method() === 'PATCH') {
                await route.fulfill({
                    status: 200,
                    contentType: 'application/json',
                    body: JSON.stringify({
                        email_enabled: true,
                        min_severity_email: 'info'
                    }),
                });
            }
        });

        await page.goto('/overview/settings');

        // Check initial state
        const emailToggle = page.locator('#notification-preferences button[role="switch"]');
        await expect(emailToggle).toHaveAttribute('aria-checked', 'false');

        // Enable toggle
        await emailToggle.click();
        await expect(emailToggle).toHaveAttribute('aria-checked', 'true');

        // Change select
        const severitySelect = page.locator('#notification-preferences select');
        await severitySelect.selectOption('info');
        await expect(severitySelect).toHaveValue('info');

        // Save
        const saveBtn = page.locator('#notification-preferences button:has-text("Save preferences")');
        await saveBtn.click();

        // The save is successful and it reflets the updated state
        await expect(emailToggle).toHaveAttribute('aria-checked', 'true');
        await expect(severitySelect).toHaveValue('info');
    });

    test('shows an error state if loading fails', async ({ page }) => {
        await page.route('**/api/v1/notifications/preferences', async (route) => {
            if (route.request().method() === 'GET') {
                await route.fulfill({
                    status: 500,
                    contentType: 'application/json',
                    body: JSON.stringify({ detail: 'Internal Server Error' })
                });
            }
        });

        await page.goto('/overview/settings');

        await expect(page.locator('text=Failed to fetch notification preferences')).toBeVisible();
    });

    test('shows an error state if saving fails', async ({ page }) => {
        let isGet = true;
        await page.route('**/api/v1/notifications/preferences', async (route) => {
            if (route.request().method() === 'GET') {
                await route.fulfill({
                    status: 200,
                    contentType: 'application/json',
                    body: JSON.stringify({
                        email_enabled: false,
                        min_severity_email: 'critical'
                    }),
                });
                isGet = false;
            } else if (route.request().method() === 'PATCH') {
                await route.fulfill({
                    status: 400,
                    contentType: 'application/json',
                    body: JSON.stringify({ detail: 'Bad request' })
                });
            }
        });

        await page.goto('/overview/settings');

        const emailToggle = page.locator('#notification-preferences button[role="switch"]');
        await emailToggle.click();

        const saveBtn = page.locator('#notification-preferences button:has-text("Save preferences")');
        await saveBtn.click();

        await expect(page.locator('text=Failed to update notification preferences')).toBeVisible();
    });
});
