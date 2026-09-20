import { test, expect } from '@playwright/test';
import { login } from '../helpers/auth';

test.describe('Overview dashboard', () => {
    test.beforeEach(async ({ page }) => {
        await login(page);
    });

    test('renders dashboard data for a monitored repository', async ({ page }) => {
        const repository = {
            id: 'repo-1',
            full_name: 'acme/service',
            private: false,
            default_branch: 'main',
            monitoring_enabled: true,
            created_at: '2024-01-01T00:00:00Z',
        };

        const dashboard = {
            repository_id: 'repo-1',
            health: {
                overall_score: 88,
                category_scores: {
                    ci_cd: 90,
                    dependencies: 70,
                    security: 92,
                    issues: 80,
                    pull_requests: 76,
                    code_quality: 84,
                },
                reasons: ['Strong release health across deploy pipelines'],
                computed_at: '2024-05-01T12:00:00Z',
                previous_score: 82,
            },
            needs_attention: {
                findings: [{
                    id: 'finding-1',
                    repository_id: 'repo-1',
                    category: 'security',
                    type: 'dependency',
                    title: 'Outdated dependency alert',
                    description: 'A dependency is behind the recommended version.',
                    severity: 'high',
                    priority: 'high',
                    status: 'open',
                    source: 'test',
                    evidence: {},
                    detected_at: '2024-05-02T09:00:00Z',
                    updated_at: '2024-05-02T09:00:00Z',
                    acknowledged_at: null,
                    resolved_at: null,
                    resolution_source: null,
                }],
                health_snapshot: null,
                reasons: ['Strong release health across deploy pipelines'],
            },
            activity_feed: [{
                source: 'github_event',
                timestamp: '2024-05-03T10:00:00Z',
                title: 'Deployment completed',
                summary: 'Production deployment completed successfully.',
                reference_id: '11111111-1111-4111-8111-111111111111',
            }],
            ai_summary: { exists: false },
            trends: {
                window_days: 30,
                health_trend: {
                    overall_delta: 7,
                    category_deltas: [{ category: 'security', delta: 8 }],
                },
                finding_velocity: {
                    categories: [{ category: 'security', detected: 1, resolved: 0 }],
                },
            },
            finding_category_counts: {
                security: 1,
                dependencies: 2,
                ci_cd: 0,
                issues: 0,
                pull_requests: 0,
                code_quality: 0,
            },
        };

        await page.route('**/api/v1/repositories', async (route) => {
            await route.fulfill({ status: 200, json: [repository] });
        });

        await page.route('**/api/v1/repositories/repo-1/dashboard', async (route) => {
            await route.fulfill({ status: 200, json: dashboard });
        });

        await page.route('**/api/v1/ai/connection', async (route) => {
            await route.fulfill({ status: 200, json: { configured: true, provider: 'gemini', model: 'gemini-2.5-flash', status: 'valid' } });
        });

        await page.route('**/api/v1/repositories/repo-1/ai-summary', async (route) => {
            if (route.request().method() === 'GET') {
                await route.fulfill({ status: 200, json: { exists: false } });
            } else {
                await route.fulfill({ status: 200, json: {
                    id: 'summary-1',
                    repository_id: 'repo-1',
                    finding_id: null,
                    analysis_type: 'repository_summary',
                    provider: 'gemini',
                    model: 'gemini-2.5-flash',
                    status: 'completed',
                    requested_at: '2024-05-03T09:00:00Z',
                    completed_at: '2024-05-03T09:30:00Z',
                    summary: 'The repository is stable, but one security dependency needs review.',
                    severity_assessment: 'medium',
                    confidence: 'high',
                    recommendations: ['Upgrade the vulnerable dependency and verify the lockfile.'],
                } });
            }
        });

        await page.goto('/overview');

        await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible();
        await expect(page.getByRole('heading', { name: 'Health score' })).toBeVisible();
        await expect(page.getByText('Needs attention')).toBeVisible();
        await expect(page.getByText('Recent activity')).toBeVisible();
        await expect(page.getByRole('heading', { name: 'Repository summary' })).toBeVisible();

        await page.getByRole('button', { name: 'Generate Summary' }).click();
        await expect(page.getByText('The repository is stable, but one security dependency needs review.')).toBeVisible();
    });

    test('shows empty states when no repository is connected', async ({ page }) => {
        await page.route('**/api/v1/repositories', async (route) => {
            await route.fulfill({ status: 200, json: [] });
        });

        await page.goto('/overview');

        await expect(page.getByText('No connected repositories yet')).toBeVisible();
    });

    test('shows dashboard and component empty states', async ({ page }) => {
        await page.route('**/api/v1/repositories', async (route) => {
            await route.fulfill({ status: 200, json: [{
                id: 'repo-empty',
                full_name: 'acme/empty',
                private: false,
                default_branch: 'main',
                monitoring_enabled: true,
                created_at: '2024-01-01T00:00:00Z',
            }] });
        });
        await page.route('**/api/v1/repositories/repo-empty/dashboard', async (route) => {
            await route.fulfill({ status: 200, json: {
                repository_id: 'repo-empty',
                health: null,
                needs_attention: { findings: [], health_snapshot: null, reasons: [] },
                activity_feed: [],
                ai_summary: { exists: false },
                trends: null,
                finding_category_counts: {},
            } });
        });
        await page.route('**/api/v1/ai/connection', async (route) => {
            await route.fulfill({ status: 200, json: { configured: true } });
        });
        await page.route('**/api/v1/repositories/repo-empty/ai-summary', async (route) => {
            await route.fulfill({ status: 200, json: { exists: false } });
        });

        await page.goto('/overview');

        await expect(page.getByText('No health score yet')).toBeVisible();
        await expect(page.getByText('Nothing needs attention')).toBeVisible();
        await expect(page.getByText('No category signals yet')).toBeVisible();
        await expect(page.getByText('No recent activity')).toBeVisible();
        await expect(page.getByText('No trend data yet')).toBeVisible();
        await expect(page.getByRole('button', { name: 'Generate Summary' })).toBeVisible();
    });

    test('shows a dashboard error state', async ({ page }) => {
        await page.route('**/api/v1/repositories', async (route) => {
            await route.fulfill({ status: 200, json: [{ id: 'repo-error', full_name: 'acme/error', monitoring_enabled: true }] });
        });
        await page.route('**/api/v1/repositories/repo-error/dashboard', async (route) => {
            await route.fulfill({ status: 500, json: { detail: 'Dashboard unavailable' } });
        });

        await page.goto('/overview');

        await expect(page.getByText('Overview is temporarily unavailable')).toBeVisible();
        await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible();
    });

    test('shows the repository summary unconfigured state', async ({ page }) => {
        await page.route('**/api/v1/repositories', async (route) => {
            await route.fulfill({ status: 200, json: [{ id: 'repo-ai', full_name: 'acme/ai', monitoring_enabled: true }] });
        });
        await page.route('**/api/v1/repositories/repo-ai/dashboard', async (route) => {
            await route.fulfill({ status: 200, json: {
                repository_id: 'repo-ai', health: null,
                needs_attention: { findings: [], health_snapshot: null, reasons: [] },
                activity_feed: [], ai_summary: { exists: false },
                trends: { window_days: 30, health_trend: { overall_delta: 0, category_deltas: [] }, finding_velocity: { categories: [] } },
                finding_category_counts: {},
            } });
        });
        await page.route('**/api/v1/repositories/repo-ai/ai-summary', async (route) => {
            await route.fulfill({ status: 200, json: { exists: false } });
        });
        await page.route('**/api/v1/ai/connection', async (route) => {
            await route.fulfill({ status: 200, json: { configured: false } });
        });

        await page.goto('/overview');
        await expect(page.getByText('Set up a valid BYOK connection')).toBeVisible();
    });

    test('shows repository summary loading and error states', async ({ page }) => {
        let releaseSummary!: () => void;
        const summaryReleased = new Promise<void>((resolve) => { releaseSummary = resolve; });

        await page.route('**/api/v1/repositories', async (route) => {
            await route.fulfill({ status: 200, json: [{ id: 'repo-ai-error', full_name: 'acme/ai-error', monitoring_enabled: true }] });
        });
        await page.route('**/api/v1/repositories/repo-ai-error/dashboard', async (route) => {
            await route.fulfill({ status: 200, json: {
                repository_id: 'repo-ai-error', health: null,
                needs_attention: { findings: [], health_snapshot: null, reasons: [] },
                activity_feed: [], ai_summary: { exists: false },
                trends: { window_days: 30, health_trend: { overall_delta: 0, category_deltas: [] }, finding_velocity: { categories: [] } },
                finding_category_counts: {},
            } });
        });
        await page.route('**/api/v1/ai/connection', async (route) => {
            await route.fulfill({ status: 200, json: { configured: true } });
        });
        await page.route('**/api/v1/repositories/repo-ai-error/ai-summary', async (route) => {
            await summaryReleased;
            await route.fulfill({ status: 500, json: { detail: 'Summary unavailable' } });
        });

        await page.goto('/overview');
        await expect(page.getByLabel('Loading repository summary')).toBeVisible();
        releaseSummary();
        await expect(page.locator('div[role="alert"].space-y-3')).toContainText('Summary unavailable');
    });
});
