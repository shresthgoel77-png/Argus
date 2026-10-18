import { test, expect, type Page } from '@playwright/test';
import { login } from '../helpers/auth';

const checkedAt = '2026-10-18T08:00:00Z';
const finding = {
    id: 'layout-finding', repository_id: 'layout-repo', category: 'security', type: 'dependency',
    title: 'Review vulnerable dependency', description: 'A dependency requires review.', severity: 'high',
    source: 'security_monitor', status: 'open', priority: 'high', evidence: {},
    detected_at: checkedAt, updated_at: checkedAt, acknowledged_at: null, resolved_at: null, resolution_source: null,
};
const repository = { id: 'layout-repo', full_name: 'test/layout', monitoring_enabled: true, private: false, default_branch: 'main', created_at: checkedAt };
const dashboard = {
    repository_id: repository.id,
    health: {
        overall_score: 62, category_scores: { code_quality: 0, security: 49, dependencies: 80, issues: 50, pull_requests: 100 },
        computed_at: checkedAt, previous_score: 70, reasons: [],
        coverage: { assessed_categories: ['code_quality', 'security', 'dependencies', 'issues', 'pull_requests'], excluded_categories: { ci_cd: { status: 'unavailable', reason: 'No workflow history.' } } },
    },
    monitoring_status: 'partial_failure', last_monitoring_at: checkedAt,
    monitoring_checks: {
        code_quality: { status: 'success', checked_at: checkedAt, error_message: null },
        dependency: { status: 'success', checked_at: checkedAt, error_message: null },
        security: { status: 'success', checked_at: checkedAt, error_message: null },
        ci_cd: { status: 'unavailable', checked_at: checkedAt, error_message: 'No workflow history.' },
    },
    finding_category_counts: { code_quality: 2, security: 1, dependencies: 0, ci_cd: 0 },
    needs_attention: { findings: [finding], reasons: [], health_snapshot: null },
    activity_feed: [
        { source: 'finding_detected', timestamp: checkedAt, title: 'Dependency detected', summary: 'Security finding recorded.', reference_id: 'event-1' },
        { source: 'health_changed', timestamp: '2026-10-17T08:00:00Z', title: 'Health recorded', summary: 'An earlier assessment.', reference_id: 'event-2' },
    ],
    ai_summary: { exists: false },
    trends: { window_days: 30, health_trend: { overall_delta: -8, category_deltas: [{ category: 'security', delta: -12 }, { category: 'code_quality', delta: 0 }] }, finding_velocity: { categories: [] } },
};
const failedSummary = { id: 'layout-summary', finding_id: null, provider: 'test', model: 'test', status: 'failed', requested_at: checkedAt, completed_at: checkedAt, summary: null, error_message: 'Test provider unavailable.' };

async function mockOverview(page: Page) {
    await page.route('**/api/v1/repositories', route => route.fulfill({ json: [repository, { ...repository, id: 'layout-other', full_name: 'test/other', monitoring_enabled: false }] }));
    await page.route('**/api/v1/repositories/layout-repo/dashboard', route => route.fulfill({ json: dashboard }));
    await page.route('**/api/v1/repositories/layout-other/dashboard', route => route.fulfill({ json: { ...dashboard, repository_id: 'layout-other', health: null, last_recorded_health: dashboard.health, monitoring_status: 'blocked', monitoring_checks: { security: { status: 'blocked', checked_at: null, error_message: 'Access unavailable.' } }, needs_attention: { findings: [], reasons: [], health_snapshot: null }, finding_category_counts: {}, trends: null, activity_feed: [] } }));
    await page.route('**/api/v1/ai/connection', route => route.fulfill({ json: { configured: true } }));
    await page.route('**/api/v1/repositories/*/ai-summary', route => route.fulfill({ json: route.request().method() === 'GET' ? failedSummary : { ...failedSummary, status: 'completed', summary: 'Retried summary.', error_message: null } }));
}

test.describe('Overview layout and state regressions (mocked APIs)', () => {
    test.beforeEach(async ({ page }) => {
        await login(page);
        await mockOverview(page);
    });

    test('preserves hierarchy, proportional scores, issue approval, and finding navigation', async ({ page }, testInfo) => {
        await page.setViewportSize({ width: 1440, height: 1100 });
        let issuePosts = 0;
        await page.route('**/api/v1/findings/layout-finding/issue-preview', route => route.fulfill({ json: { repository: 'test/layout', title: 'Mock issue', body: 'Mock issue body', preview_token: 'mock-token' } }));
        await page.route('**/api/v1/findings/layout-finding/issue', async route => {
            expect(route.request().postDataJSON()).toEqual({ approved: true, preview_token: 'mock-token' });
            issuePosts++;
            await route.fulfill({ json: { number: 123, html_url: 'https://example.com/mock-issue', title: 'Mock issue' } });
        });
        await page.route('**/api/v1/findings/layout-finding', route => route.fulfill({ json: finding }));
        await page.goto('/overview');
        const health = page.getByRole('region', { name: 'Health score', exact: true });
        const attention = page.getByRole('region', { name: 'Needs attention', exact: true });
        const category = page.getByRole('region', { name: 'Category intelligence', exact: true });
        const trend = page.getByRole('region', { name: 'Trend overview', exact: true });
        const activity = page.getByRole('region', { name: 'Recent activity', exact: true });
        const assessment = page.getByRole('region', { name: 'Assessment status', exact: true });
        await expect(attention.getByText('Source: security monitor')).toBeVisible();
        await expect(attention.getByText(/Detected/)).toBeVisible();
        await expect(page.getByText('AI summary failed: Test provider unavailable.')).toBeVisible();
        await expect(page.getByRole('button', { name: 'Preview Automated Fix', exact: true })).toBeDisabled();
        await expect(page.getByText(/Automated fix preview is unavailable/)).toBeVisible();
        const boxes = await Promise.all([health, attention, category, trend, activity, assessment].map(item => item.boundingBox()));
        const [h, a, c, t, r, b] = boxes.map(box => box!);
        expect(h.x + h.width).toBeLessThanOrEqual(a.x + 1);
        expect(a.width / h.width).toBeGreaterThan(2.7);
        expect(Math.abs(c.width - t.width)).toBeLessThan(2);
        expect(Math.abs(t.width - r.width)).toBeLessThan(2);
        expect(c.y).toBe(t.y); expect(t.y).toBe(r.y);
        expect(b.y).toBeGreaterThan(r.y + r.height);
        for (const [label, score, color] of [['Code Quality', 0, 'destructive'], ['Security', 49, 'destructive'], ['Dependencies', 80, 'success'], ['Issues', 50, 'warning']] as const) {
            const bar = trend.getByRole('progressbar', { name: `${label} score`, exact: true });
            await expect(bar).toHaveAttribute('aria-valuenow', String(score));
            await expect(bar.locator('div')).toHaveAttribute('style', `width: ${score}%;`);
            await expect(bar.locator('div')).toHaveClass(new RegExp(`bg-${color}`));
        }
        await expect(trend.getByRole('progressbar', { name: 'CI/CD score' })).toHaveCount(0);
        await expect(trend.getByText('Δ -12')).toBeVisible();
        await expect(category.getByRole('link', { name: /CI\/CD/ })).toContainText('Findings unavailable');
        await expect(category.getByRole('link', { name: /Dependencies/ })).toContainText('0 open findings');
        await expect(activity.locator('p.font-medium')).toHaveText(['Dependency detected', 'Health recorded']);
        await page.screenshot({ path: testInfo.outputPath('desktop.png'), fullPage: true });
        await page.getByRole('button', { name: 'Auto-Generate GitHub Issue', exact: true }).click();
        const create = page.getByRole('button', { name: 'Create approved issue on GitHub', exact: true });
        await expect(create).toBeDisabled(); expect(issuePosts).toBe(0);
        await page.getByRole('checkbox').check(); await create.click();
        await expect(page.getByRole('link', { name: 'View issue #123 on GitHub' })).toHaveAttribute('href', 'https://example.com/mock-issue');
        expect(issuePosts).toBe(1);
        await attention.getByRole('link', { name: finding.title, exact: true }).click();
        await expect(page).toHaveURL(/\/overview\/findings\/layout-finding$/);
        await expect(page.getByRole('heading', { name: finding.title, exact: true })).toBeVisible();
    });

    test('stacks on mobile without overflow and clears repository-specific state on switching', async ({ page }, testInfo) => {
        await page.goto('/overview');
        await expect(page.getByText(finding.title, { exact: true })).toBeVisible();
        for (const width of [390, 320]) {
            await page.setViewportSize({ width, height: 844 });
            const sections = await Promise.all(['Health score', 'Needs attention', 'Category intelligence', 'Trend overview', 'Recent activity', 'Assessment status'].map(name => page.getByRole('region', { name, exact: true }).boundingBox()));
            for (let index = 1; index < sections.length; index++) expect(sections[index]!.y).toBeGreaterThan(sections[index - 1]!.y);
            expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
            await page.screenshot({ path: testInfo.outputPath(`mobile-${width}.png`), fullPage: true });
        }
        await page.getByRole('combobox', { name: 'Select repository' }).selectOption('layout-other');
        await expect(page.getByText('Last recorded score', { exact: true })).toBeVisible();
        await expect(page.getByText('Historical', { exact: true })).toBeVisible();
        await expect(page.getByRole('progressbar')).toHaveCount(0);
        await expect(page.getByRole('button', { name: 'Retry assessment', exact: true }).first()).toBeDisabled();
        await expect(page.getByText('No active findings available')).toBeVisible();
        await expect(page.getByText(finding.title, { exact: true })).toHaveCount(0);
        await expect(page.getByRole('region', { name: 'Assessment status', exact: true })).toContainText('Access unavailable.');
        await page.getByRole('combobox', { name: 'Select repository' }).selectOption('layout-repo');
        await expect(page.getByText(finding.title, { exact: true })).toBeVisible();
        await page.getByRole('region', { name: 'Category intelligence', exact: true }).getByRole('link', { name: /Security/ }).click();
        await expect(page).toHaveURL(/\/overview\/findings\?category=security$/);
    });

    test('retains retry controls and rejects obsolete dashboard responses while loading', async ({ page }) => {
        let refreshes = 0;
        await page.route('**/api/v1/repositories/layout-repo/refresh', async route => {
            refreshes++;
            await route.fulfill(refreshes === 1 ? { status: 503, json: { detail: 'Test retry failed.' } } : { json: { correlation_id: 'mock', status: 'partial_failure', checks: dashboard.monitoring_checks } });
        });
        await page.goto('/overview');
        const retry = page.getByRole('region', { name: 'Health score', exact: true }).getByRole('button', { name: 'Retry assessment', exact: true });
        await retry.click();
        await expect(page.getByRole('alert').filter({ hasText: 'The assessment could not be retried.' })).toBeVisible();
        await retry.click();
        await expect(page.getByRole('alert').filter({ hasText: 'The assessment could not be retried.' })).toHaveCount(0);
        await expect(retry).toBeEnabled(); expect(refreshes).toBe(2);
        await page.getByRole('button', { name: 'Try again', exact: true }).click();
        await expect(page.getByText('Retried summary.', { exact: true })).toBeVisible();
        let release!: () => void;
        const held = new Promise<void>(resolve => { release = resolve; });
        await page.route('**/api/v1/repositories/layout-repo/dashboard', async route => { await held; await route.fulfill({ json: dashboard }); });
        await page.getByRole('combobox', { name: 'Select repository' }).selectOption('layout-other');
        await expect(page.getByText('Historical', { exact: true })).toBeVisible();
        await page.getByRole('combobox', { name: 'Select repository' }).selectOption('layout-repo');
        await expect(page.getByLabel('Loading overview')).toBeVisible();
        await expect(page.getByRole('combobox', { name: 'Select repository' })).toBeEnabled();
        await page.getByRole('combobox', { name: 'Select repository' }).selectOption('layout-other');
        await expect(page.getByText('Historical', { exact: true })).toBeVisible();
        const lateResponse = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v1/repositories/layout-repo/dashboard');
        release();
        await lateResponse;
        await expect(page.getByText('Historical', { exact: true })).toBeVisible();
        await expect(page.getByText(finding.title, { exact: true })).toHaveCount(0);
    });

    test('shows successful checks and pending analysis, and disables assessment retry while running', async ({ page, browser }) => {
        let running = false;
        await page.route('**/api/v1/repositories/layout-repo/dashboard', route => route.fulfill({ json: {
            ...dashboard, monitoring_status: running ? 'running' : 'success',
            health: running ? null : { ...dashboard.health, category_scores: { ...dashboard.health.category_scores, ci_cd: 90 }, coverage: { assessed_categories: ['code_quality', 'security', 'dependencies', 'ci_cd', 'issues', 'pull_requests'], excluded_categories: {} } },
            last_recorded_health: running ? dashboard.health : null,
            monitoring_checks: { security: { status: running ? 'pending' : 'success', checked_at: running ? null : checkedAt, error_message: null } },
        } }));
        await page.route('**/api/v1/repositories/layout-repo/ai-summary', route => route.fulfill({ json: { ...failedSummary, status: 'pending', completed_at: null, error_message: null } }));
        await page.goto('/overview');
        await expect(page.getByRole('region', { name: 'Assessment status', exact: true })).toContainText('Assessment status: success');
        await expect(page.getByRole('region', { name: 'Assessment status', exact: true }).getByRole('term')).toContainText('success');
        await expect(page.getByText('AI summary is still in progress.')).toBeVisible();
        await expect(page.getByText(/^Requested /)).toBeVisible();
        running = true;
        await page.reload();
        await expect(page.getByRole('heading', { name: 'Assessment status: running', exact: true })).toBeVisible();
        await expect(page.getByRole('button', { name: 'Retry assessment', exact: true }).first()).toBeDisabled();
        await expect(page.getByRole('region', { name: 'Assessment status', exact: true }).getByRole('term')).toContainText('pending');
        await expect(page.getByText('Historical', { exact: true })).toBeVisible();
        await expect(page.getByRole('progressbar')).toHaveCount(0);
        const anonymous = await browser.newContext({ storageState: { cookies: [], origins: [] } });
        try {
            const anonymousPage = await anonymous.newPage();
            await anonymousPage.goto('/overview');
            await expect(anonymousPage).toHaveURL(/\/sign-in/);
        } finally { await anonymous.close(); }
    });
});
