import { test, expect, type Page } from '@playwright/test';
import { login } from '../helpers/auth';

const finding = {
    id: 'finding-1',
    repository_id: 'repo-1',
    category: 'security',
    type: 'vulnerability',
    title: 'Unsafe dependency',
    description: 'A dependency needs attention.',
    severity: 'high',
    source: 'test',
    evidence: {},
    status: 'open',
    detected_at: '2026-09-15T10:00:00Z',
    updated_at: '2026-09-15T10:00:00Z',
    priority: 'high',
    acknowledged_at: null,
    resolved_at: null,
    resolution_source: null,
};

async function openFinding(page: Page, options: { configured?: boolean; analysis?: object } = {}) {
    await page.route('**/api/v1/findings?*', async (route) => {
        await route.fulfill({ status: 200, json: { items: [finding], total: 1, limit: 20, offset: 0 } });
    });
    await page.route('**/api/v1/repositories', async (route) => {
        await route.fulfill({ status: 200, json: [{ id: 'repo-1', full_name: 'org/repo' }] });
    });
    await page.route('**/api/v1/ai/connection', async (route) => {
        await route.fulfill({ status: 200, json: { configured: options.configured ?? false } });
    });
    await page.route('**/api/v1/findings/finding-1/ai-analysis', async (route) => {
        await route.fulfill({ status: 200, json: options.analysis ?? { exists: false } });
    });

    await page.goto('/overview/findings');
    await page.getByRole('button', { name: 'Unsafe dependency' }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
}

test.describe('Finding AI analysis', () => {
    test.beforeEach(async ({ page }) => {
        await login(page);
    });

    test('shows the unconfigured state and links to Settings', async ({ page }) => {
        await openFinding(page);

        await expect(page.getByText('Set up a valid BYOK connection before generating an AI explanation.')).toBeVisible();
        await expect(page.getByRole('link', { name: 'Open Settings AI/BYOK' })).toHaveAttribute('href', '/overview/settings#ai-connection');
    });

    test('shows a real loading state while analysis is being generated', async ({ page }) => {
        await openFinding(page, { configured: true });
        let releaseRequest: (() => void) | undefined;
        await page.route('**/api/v1/findings/finding-1/ai-analysis', async (route) => {
            if (route.request().method() === 'POST') {
                await new Promise<void>((resolve) => { releaseRequest = resolve; });
                await route.fulfill({ status: 200, json: { id: 'analysis-1', finding_id: 'finding-1', status: 'completed', requested_at: '2026-09-16T10:00:00Z', completed_at: '2026-09-16T10:01:00Z', provider: 'gemini', model: 'test', summary: 'Summary', severity_assessment: 'medium', confidence: 0.9, recommendations: ['Upgrade it'] } });
            } else {
                await route.fulfill({ status: 200, json: { exists: false } });
            }
        });

        await page.getByRole('button', { name: 'Explain with AI' }).click();
        await expect(page.getByRole('button', { name: 'Explain with AI' })).toHaveAttribute('aria-busy', 'true');
        releaseRequest?.();
        await expect(page.getByRole('dialog').getByText('Summary', { exact: true }).last()).toBeVisible();
    });

    test('renders every field from a successful analysis', async ({ page }) => {
        await openFinding(page, {
            configured: true,
            analysis: { id: 'analysis-1', finding_id: 'finding-1', status: 'completed', requested_at: '2026-09-16T10:00:00Z', completed_at: '2026-09-16T10:01:00Z', provider: 'gemini', model: 'test', summary: 'The dependency is exposed to a known issue.', severity_assessment: 'medium', confidence: 0.9, recommendations: ['Upgrade the dependency', 'Run the security scan again'] },
        });

        await expect(page.getByText('The dependency is exposed to a known issue.')).toBeVisible();
        await expect(page.getByText('AI severity assessment')).toBeVisible();
        await expect(page.getByRole('dialog').getByText('Medium', { exact: true })).toBeVisible();
        await expect(page.getByText('0.9')).toBeVisible();
        await expect(page.getByText('Upgrade the dependency')).toBeVisible();
        await expect(page.getByText(/^Generated /)).toBeVisible();
    });

    test('shows the sanitized API error and allows retry', async ({ page }) => {
        await openFinding(page, { configured: true });
        await page.unroute('**/api/v1/findings/finding-1/ai-analysis');
        await page.route('**/api/v1/findings/finding-1/ai-analysis', async (route) => {
            if (route.request().method() === 'POST') {
                await route.fulfill({ status: 400, json: { detail: 'No valid AI connection is configured. Please complete setup in the Settings AI/BYOK section.' } });
            } else {
                await route.fulfill({ status: 200, json: { exists: false } });
            }
        });

        await page.getByRole('button', { name: 'Explain with AI' }).click();
        await expect(page.getByText('No valid AI connection is configured. Please complete setup in the Settings AI/BYOK section.')).toBeVisible();
        await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible();
    });

    test('loads a prior analysis on mount', async ({ page }) => {
        await openFinding(page, {
            configured: true,
            analysis: { id: 'analysis-1', finding_id: 'finding-1', status: 'completed', requested_at: '2026-09-16T10:00:00Z', completed_at: '2026-09-16T10:01:00Z', provider: 'gemini', model: 'test', summary: 'Previously generated explanation.', severity_assessment: 'low', confidence: 'high', recommendations: ['Review the patch'] },
        });

        await expect(page.getByText('Previously generated explanation.')).toBeVisible();
        await expect(page.getByText('Review the patch')).toBeVisible();
        await expect(page.getByRole('button', { name: 'Explain with AI' })).toHaveCount(0);
    });
});