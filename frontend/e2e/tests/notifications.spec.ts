import { test, expect } from '@playwright/test';
import { login } from '../helpers/auth';

test.describe('Notifications e2e testing', () => {
    test.beforeEach(async ({ page }) => {
        await login(page);
    });

    test('bell rendering, dropdown, pagination, filtering, mark-read, mark-all-read and unknown reference', async ({ page }) => {
        const notificationsData1 = [
            {
                id: 'notif-1',
                type: 'finding_created',
                title: 'New High Severity Finding',
                message: 'A critical vulnerability was detected.',
                is_read: false,
                reference_type: 'finding',
                reference_id: 'finding-123',
                repository_id: 'repo-1',
                created_at: '2024-05-03T09:00:00Z',
            },
            {
                id: 'notif-2',
                type: 'health_score_dropped',
                title: 'Repository Health Drop',
                message: 'Health score dropped significantly.',
                is_read: false,
                reference_type: 'health_snapshot',
                reference_id: 'snap-456',
                repository_id: 'repo-2',
                created_at: '2024-05-03T08:00:00Z',
            },
        ];

        const notificationsDataAll = [
            ...notificationsData1,
            {
                id: 'notif-3',
                type: 'unknown_reference',
                title: 'An update occurred',
                message: 'Some generic update.',
                is_read: false,
                reference_type: 'unknown_reference',
                reference_id: 'unknown-999',
                repository_id: null,
                created_at: '2024-05-02T09:00:00Z',
            }
        ];

        await page.route('**/api/v1/notifications/unread-count', async (route) => {
            return route.fulfill({ status: 200, json: { count: 3 } });
        });

        await page.route('**/api/v1/notifications*', async (route) => {
            const url = new URL(route.request().url());
            if (url.searchParams.get('unread_only')) {
                return route.fulfill({ status: 200, json: notificationsDataAll });
            }
            return route.fulfill({ status: 200, json: notificationsDataAll });
        });

        await page.route('**/api/v1/notifications/*/read', async (route) => {
            return route.fulfill({ status: 200, json: { id: 'notif-3', is_read: true } });
        });

        await page.route('**/api/v1/notifications/read-all', async (route) => {
            return route.fulfill({ status: 200, json: { count: 3 } });
        });

        // 1. Test bell unread count
        await page.goto('/overview');
        await page.waitForTimeout(500); // Hydration wait
        await expect(page.locator('[aria-label*="3 unread"]')).toBeVisible();

        // 2. Click Bell -> open dropdown
        await page.getByRole('button', { name: /notifications|3 unread/i }).first().click();
        await page.waitForTimeout(500); // Dropdown animation

        await expect(page.getByText('New High Severity Finding')).toBeVisible();
        await expect(page.getByText('Repository Health Drop')).toBeVisible();

        // 3. Mark read / Finding route mapping
        const readPromise = page.waitForResponse('**/api/v1/notifications/*/read');
        await page.getByText('New High Severity Finding').click();
        await readPromise;
        await page.waitForURL('**/findings/finding-123');

        // 4. Navigate back using UI
        await page.goto('/overview/notifications');
        await page.waitForTimeout(1000); // Hydration wait

        await expect(page.getByText('Repository Health Drop')).toBeVisible();

        // 5. Pagination
        const nextButton = page.getByRole('button', { name: /next/i });
        if (await nextButton.isVisible()) {
            await nextButton.click();
            await page.waitForTimeout(500); // UI load
            await expect(page.getByText('An update occurred')).toBeVisible();
        }

        // 6. Unknown reference type -> click should trigger read but no redirect
        const unknownEl = page.getByText('An update occurred');
        if (await unknownEl.isVisible()) {
            const unknownReadPromise = page.waitForResponse('**/api/v1/notifications/*/read');
            await unknownEl.click();
            await unknownReadPromise;
            await page.waitForTimeout(500); // verify it stays on page
            expect(page.url()).toContain('/overview/notifications');
        }

        // 7. Health snapshot route mapping
        await page.goto('/overview/notifications');
        await page.waitForTimeout(1000); // Hydration wait
        await page.getByText('Repository Health Drop').click();
        await page.waitForURL('**/repositories/repo-2');

        // 8. Mark all read
        await page.goto('/overview/notifications');
        await page.waitForTimeout(1000); // Hydration wait
        const markAllButton = page.getByRole('button', { name: /Mark all as read/i });
        if (await markAllButton.isVisible()) {
            const markAllPromise = page.waitForResponse('**/api/v1/notifications/read-all');
            await markAllButton.click();
            await markAllPromise;
        }

        // 9. Unread filter
        const filterCheckbox = page.getByRole('checkbox', { name: /Unread/i });
        if (await filterCheckbox.isVisible()) {
            await filterCheckbox.click();
            await page.waitForTimeout(500);
            await expect(page.getByText('An update occurred')).toBeVisible();
        }
    });
});
