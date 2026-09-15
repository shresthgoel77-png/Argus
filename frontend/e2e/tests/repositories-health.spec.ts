import { test, expect } from '@playwright/test';
import { login } from '../helpers/auth';

test.describe('Repositories Health Visualization Flow', () => {
    test.beforeEach(async ({ page }) => {
        await login(page);

        // Common mock for repositories list
        await page.route('**/api/v1/repositories', async (route) => {
            await route.fulfill({
                status: 200,
                json: [
                    {
                        id: 'repo-1',
                        github_repo_id: 101,
                        full_name: 'my-org/monitored-repo',
                        private: false,
                        monitoring_enabled: true
                    }
                ]
            });
        });

        await page.route('**/api/v1/github/connections', async (route) => {
            await route.fulfill({ status: 200, json: [{ id: 1, account_login: 'my-org' }] });
        });

        await page.route('**/api/v1/github/connections/1/repositories', async (route) => {
            await route.fulfill({ status: 200, json: [] });
        });
    });

    test('list displays health loading, populated, and not yet checked states', async ({ page }) => {
        // Mock health endpoint to return Not yet checked
        await page.route('**/api/v1/repositories/repo-1/health', async (route) => {
            await route.fulfill({ status: 404, json: null });
        });

        await page.goto('/overview/repositories');
        await expect(page.locator('text=my-org/monitored-repo')).toBeVisible();
        await expect(page.locator('text=Not yet checked')).toBeVisible();

        // Change route to populated
        await page.route('**/api/v1/repositories/repo-1/health', async (route) => {
            await route.fulfill({
                status: 200,
                json: { overall_score: 85, category_scores: {}, reasons: [], computed_at: new Date().toISOString() }
            });
        });

        // Navigate again or trigger reload to see score 85
        await page.reload();
        await expect(page.locator('text=Score: 85')).toBeVisible();
    });

    test('health detail view and manual trigger refreshes data without page reload', async ({ page }) => {
        // Initial health snapshot
        let runCount = 0;
        await page.route('**/api/v1/repositories/repo-1/health', async (route) => {
            if (runCount === 0) {
                await route.fulfill({
                    status: 200,
                    json: {
                        overall_score: 75,
                        category_scores: { security: 80, performance: 75, code_quality: 70, issues: 90, dependencies: 60, ci_cd: 50 },
                        reasons: ["Old dependencies", "Some lint warnings"],
                        computed_at: new Date().toISOString()
                    }
                });
            } else {
                await route.fulfill({
                    status: 200,
                    json: {
                        overall_score: 95,
                        category_scores: { security: 90, performance: 85, code_quality: 90, issues: 90, dependencies: 80, ci_cd: 70 },
                        reasons: ["Code quality improved"],
                        computed_at: new Date().toISOString()
                    }
                });
            }
        });

        await page.route('**/api/v1/repositories/repo-1/health/history*', async (route) => {
            await route.fulfill({
                status: 200,
                json: {
                    total: 0, items: []
                }
            });
        });

        await page.route('**/api/v1/repositories/repo-1/health-runs', async (route) => {
            // Trigger health run, wait briefly, then increment runCount so re-fetch yields new data
            await new Promise(resolve => setTimeout(resolve, 500));
            runCount++;
            await route.fulfill({
                status: 200,
                json: {}
            });
        });

        await page.goto('/overview/repositories/repo-1');

        // Verify initial state
        await expect(page.locator('text=Overall Health Score')).toBeVisible();
        await expect(page.locator('text=75').first()).toBeVisible();
        await expect(page.locator('text=Old dependencies')).toBeVisible();

        // Click trigger button
        const triggerBtn = page.locator('button:has-text("Run Health Check")');
        await triggerBtn.click();

        // Button should switch to running
        await expect(page.locator('button:has-text("Running...")')).toBeVisible();

        // Once completed, page automatically refreshes data
        await expect(page.locator('text=95').first()).toBeVisible();
        await expect(page.locator('text=Code quality improved')).toBeVisible();
        await expect(triggerBtn).toHaveText('Run Health Check'); // Back to initial text
    });
});
