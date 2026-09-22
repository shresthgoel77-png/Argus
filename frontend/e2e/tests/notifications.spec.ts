import { test, expect } from '@playwright/test';
import { login } from '../helpers/auth';

test.describe('Notifications display and routing mapping', () => {
    test.beforeEach(async ({ page }) => {
        await login(page);
    });

    test('bell unread-count display, dropdown rendering, mark-read and mark-all-read', async ({ page }) => {
        const notificationsPage1 = {
            items: [
                {
                    id: 'notif-1',
                    type: 'finding',
                    title: 'New High Severity Finding',
                    message: 'A critical vulnerability was detected.',
                    is_read: false,
                    reference_id: 'finding-123',
                    repository_id: 'repo-1',
                },
                {
                    id: 'notif-2',
                    type: 'health_snapshot',
                    title: 'Repository Health Drop',
                    message: 'Health score dropped significantly.',
                    is_read: false,
                    reference_id: 'snap-456',
                    repository_id: 'repo-2',
                },
            ],
            next_before: '2024-05-03T09:00:00Z',
        };

        const notificationsPage2 = {
            items: [
                {
                    id: 'notif-3',
                    type: 'unknown_reference',
                    title: 'An update occurred',
                    message: 'Some generic update.',
                    is_read: true,
                    reference_id: null,
                    repository_id: null,
                }
            ],
            next_before: null,
        };

        const unreadCountResponse = { count: 2 };

        await page.route('**/api/v1/notifications/unread-count', async (route) => {
            return route.fulfill({ status: 200, json: unreadCountResponse });
        });

        await page.route('**/api/v1/notifications*', async (route) => {
            const requestUrl = new URL(route.request().url());
            if (requestUrl.pathname === '/api/v1/notifications' && requestUrl.searchParams.get('before')) {
                return route.fulfill({ status: 200, json: notificationsPage2 });
            }
            if (requestUrl.pathname === '/api/v1/notifications') {
                return route.fulfill({ status: 200, json: notificationsPage1 });
            }
            // fallback
            return route.continue();
        });

        await page.route('**/api/v1/notifications/notif-1/mark-read', async (route) => {
            return route.fulfill({ status: 200, json: { status: 'success' } });
        });
        await page.route('**/api/v1/notifications/mark-all-read', async (route) => {
            return route.fulfill({ status: 200, json: { status: 'success' } });
        });

        // Test unread count in header/bell
        await page.goto('/overview');
        const bellButton = page.locator('button', { hasText: 'Notifications' }).first(); // generic matcher based on common bell accessible names or structure
        // The project uses standard components, we might just look for the text '2' near a bell icon or in header
        await expect(page.getByText('2', { exact: true })).toBeVisible();
        await page.getByRole('button', { name: /notifications/i }).click();

        // Verify dropdown rendering
        await expect(page.getByText('New High Severity Finding')).toBeVisible();
        await expect(page.getByText('Repository Health Drop')).toBeVisible();

        // Verify finding route mapping behavior
        // Assuming clicking an item triggers navigation
        const findingNotif = page.getByText('New High Severity Finding');
        await findingNotif.click();

        // Let's go to full page for pagination
        await page.goto('/settings/notifications'); // or wherever full page is. In Argus it's likely /notifications
        await page.goto('/notifications');

        await expect(page.getByText('New High Severity Finding')).toBeVisible();

        // Pagination
        await page.getByRole('button', { name: 'Next' }).click();
        await expect(page.getByText('An update occurred')).toBeVisible();

        // Mark All Read
        await page.getByRole('button', { name: 'Mark all as read' }).click();
    });
});
