import { test, expect } from '@playwright/test';
import { login } from '../helpers/auth';

test.describe('Activity page', () => {
    test.beforeEach(async ({ page }) => {
        await login(page);
    });

    test('renders mixed-source activity and handles source filtering, pagination, and bot-interaction expansion', async ({ page }) => {
        const repository = {
            id: 'repo-1',
            full_name: 'acme/service',
            private: false,
            default_branch: 'main',
            monitoring_enabled: true,
            created_at: '2024-01-01T00:00:00Z',
        };

        const page1 = {
            items: [
                {
                    source: 'github_event',
                    timestamp: '2024-05-03T10:00:00Z',
                    title: 'Deployment completed',
                    summary: 'Production deployment completed successfully.',
                    reference_id: 'gh-1',
                },
                {
                    source: 'bot_interaction',
                    timestamp: '2024-05-03T09:00:00Z',
                    title: 'Bot interaction: ci_status',
                    summary: 'completed: Is CI passing?',
                    reference_id: 'bot-1',
                    details: {
                        intent: 'ci_status',
                        status: 'completed',
                        skip_reason: null,
                        response_text: 'Yes, CI is passing.',
                        requester_github_login: 'tester',
                        question_text: 'Is CI passing?',
                    }
                }
            ],
            next_before: '2024-05-03T09:00:00Z',
        };

        const page2 = {
            items: [
                {
                    source: 'finding_detected',
                    timestamp: '2024-05-02T09:00:00Z',
                    title: 'Outdated dependency',
                    summary: 'high finding detected',
                    reference_id: 'finding-1',
                }
            ],
            next_before: null,
        };

        const filteredPage = {
            items: [
                {
                    source: 'bot_interaction',
                    timestamp: '2024-05-03T09:00:00Z',
                    title: 'Bot interaction: ci_status',
                    summary: 'completed: Is CI passing?',
                    reference_id: 'bot-1',
                    details: {
                        intent: 'ci_status',
                        status: 'completed',
                        skip_reason: null,
                        response_text: 'Yes, CI is passing.',
                        requester_github_login: 'tester',
                        question_text: 'Is CI passing?',
                    }
                }
            ],
            next_before: null,
        };

        await page.route('**/api/v1/repositories', async (route) => {
            await route.fulfill({ status: 200, json: [repository] });
        });

        await page.route('**/api/v1/repositories/repo-1/activity*', async (route) => {
            const url = new URL(route.request().url());
            const source = url.searchParams.get('source');
            const before = url.searchParams.get('before');

            if (source === 'bot_interaction') {
                return route.fulfill({ status: 200, json: filteredPage });
            }

            if (before === '2024-05-03T09:00:00Z') {
                return route.fulfill({ status: 200, json: page2 });
            }

            return route.fulfill({ status: 200, json: page1 });
        });

        await page.goto('/overview/activity');

        // Verify mixed-source rendering
        await expect(page.getByText('Deployment completed', { exact: true })).toBeVisible();
        await expect(page.getByText('Production deployment completed successfully.')).toBeVisible();

        // Verify expanding bot interaction
        await page.getByLabel('Toggle details').click();

        // Ensure expanded details are shown
        await expect(page.getByText('Is CI passing?')).toBeVisible();
        await expect(page.getByText('Question')).toBeVisible();
        await expect(page.getByText('Response')).toBeVisible();
        await expect(page.getByText('Yes, CI is passing.')).toBeVisible();

        // Verify pagination
        await page.getByRole('button', { name: 'Next', exact: true }).click();
        await expect(page.getByText('Outdated dependency')).toBeVisible();
        await expect(page.getByText('high finding detected')).toBeVisible();
        await expect(page.getByRole('button', { name: 'Previous', exact: true })).toBeEnabled();

        // Verify source filtering
        await page.getByRole('button', { name: 'Bot Interactions' }).click();

        // Deployment completed should be hidden since we filtered
        await expect(page.getByText('Deployment completed')).not.toBeVisible();
        await expect(page.getByText('Bot interaction: ci_status')).toBeVisible();
    });
});
