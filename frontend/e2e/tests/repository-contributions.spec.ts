import { test, expect, type Page } from '@playwright/test';
import { login } from '../helpers/auth';
import { contributionEvent, contributionSnapshot } from '../../src/__tests__/fixtures/repository-contributions';

const repositories = ['alpha', 'beta', 'a-very-long-repository-name-that-wraps-on-mobile'].map((name, index) => ({
    id: `contrib-${index}`, full_name: `acme/${name}`, private: index === 1, default_branch: 'main', monitoring_enabled: false, created_at: '2026-01-01',
}));
async function shell(page: Page) {
    const requests: string[] = [];
    await page.route('**/api/v1/**', route => {
        const path = new URL(route.request().url()).pathname;
        requests.push(path);
        if (path === '/api/v1/repositories') return route.fulfill({ json: repositories });
        if (/\/(issues|pull-requests)$/.test(path)) return route.fulfill({ json: [] });
        return route.fulfill({ json: path.endsWith('/unread-count') ? { count: 0 } : null });
    });
    return requests;
}

test('shows consistent metrics, UTC month groups, proportional diffs and a readable mobile chart; deduplicates pages and recovers failures', async ({ page }, testInfo) => {
    const requests = await shell(page);
    let failedPage = true;
    await page.route('**/repositories/*/contributions?*', route => {
        const url = new URL(route.request().url());
        const id = url.pathname.split('/').at(-2)!;
        if (url.searchParams.has('cursor')) {
            expect(url.searchParams.get('start')).toBe('2026-07-21');
            expect(url.searchParams.get('end')).toBe('2026-10-18');
            if (failedPage) return route.fulfill({ status: 503, json: {} });
            return route.fulfill({ json: contributionSnapshot(id, { items: [contributionEvent(2), contributionEvent(3)], next_cursor: null }) });
        }
        return route.fulfill({ json: contributionSnapshot(id, { items: [contributionEvent(1, { message: `Improve bounded history rendering\n\n${'A long message with clear details. '.repeat(18)}${'unbroken'.repeat(50)}` }), contributionEvent(2)] }) });
    });
    await login(page);
    await page.goto('/overview/activity?repo=contrib-2&tab=contributions');
    const view = page.getByRole('region', { name: 'Repository contributions', exact: true });
    await expect(view.getByText('Complete history for this window.', { exact: true })).toBeVisible();
    await expect(view).toContainText('Jul 21, 2026 – Oct 18, 2026 · UTC');
    await expect(view).toContainText('Default branch: main · snapshot fffffff');
    await expect(view.getByLabel('Additions: 24', { exact: true })).toHaveText('+24');
    await expect(view.getByRole('img', { name: '3 commits; daily peak 1', exact: true })).toBeVisible();
    expect(await view.evaluate(element => {
        const metrics = element.querySelector('[aria-label="Repository contribution metrics"]')!;
        const timeline = element.querySelector('[aria-label="Contribution timeline"]')!;
        const frequency = element.querySelector('svg[role="img"]')!.closest('section')!;
        return !!(metrics.compareDocumentPosition(timeline) & Node.DOCUMENT_POSITION_FOLLOWING)
            && !!(timeline.compareDocumentPosition(frequency) & Node.DOCUMENT_POSITION_FOLLOWING);
    })).toBe(true);
    const diff = view.getByRole('img', { name: '8 additions, 2 deletions; proportions within this commit', exact: true }).first();
    expect(await diff.locator('span').evaluateAll(elements => elements.map(element => element.getAttribute('style')))).toEqual(['width: 80%;', 'width: 20%;']);
    await view.getByRole('button', { name: 'Load more commits' }).click();
    await expect(view.getByRole('alert')).toContainText('More commits could not be loaded');
    await expect(view.getByText('Improve bounded history rendering', { exact: true })).toBeVisible();
    failedPage = false;
    await view.getByRole('button', { name: 'Retry loading commits' }).click();
    await expect(view.getByRole('heading', { name: 'September 2026', exact: true })).toBeVisible();
    await expect(view.getByText('Commit 2', { exact: true })).toHaveCount(1);
    await expect(view.getByText('Showing 3 of 3 retrieved commits.', { exact: true })).toBeVisible();
    expect(requests.filter(path => /\/(issues|pull-requests|activity)$/.test(path))).toHaveLength(0);
    await view.getByText('Full commit message', { exact: true }).click();
    await expect(view.getByRole('link', { name: /View commit.*on GitHub/ }).first()).toHaveAttribute('rel', 'noopener noreferrer');
    for (const width of [1440, 768, 390, 320]) {
        await page.setViewportSize({ width, height: 1000 });
        await view.scrollIntoViewIfNeeded();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        expect(await page.locator('main').evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
        const chart = view.getByRole('img', { name: '3 commits; daily peak 1', exact: true });
        const box = await chart.boundingBox();
        expect(box!.width).toBeLessThan(width);
        expect(box!.height).toBe(160);
        await view.getByRole('heading', { name: 'Repository contributions', exact: true }).evaluate(element => element.scrollIntoView({ block: 'start' }));
        await page.screenshot({ path: testInfo.outputPath(`contributions-summary-${width}.png`) });
        await view.getByRole('heading', { name: 'Commit timeline', exact: true }).evaluate(element => element.scrollIntoView({ block: 'start' }));
        await page.screenshot({ path: testInfo.outputPath(`contributions-timeline-${width}.png`) });
    }
    await view.getByText('Full commit message', { exact: true }).click();
    await view.getByRole('region', { name: 'Contribution timeline', exact: true }).screenshot({ path: testInfo.outputPath('contributions-compact-timeline-320.png') });
    await view.getByText('Daily commit counts', { exact: true }).click();
    await expect(view.getByRole('table')).toContainText('Window counts · UTC · total 3');
});

test('keeps partial fields independent, distinguishes pending and zero, and restarts expired pagination', async ({ page }) => {
    await shell(page);
    let mode: 'partial' | 'pending' | 'zero' = 'partial';
    let expired = true;
    await page.route('**/repositories/*/contributions?*', route => {
        const url = new URL(route.request().url());
        const id = url.pathname.split('/').at(-2)!;
        if (url.searchParams.has('cursor') && expired) return route.fulfill({ status: 409, json: { detail: 'Snapshot expired' } });
        const data = contributionSnapshot(id);
        if (mode === 'partial') {
            data.status = 'partial'; data.reason = 'scan_limit'; data.history_complete = false;
            data.metrics = { ...data.metrics!, additions: null, deletions: null, distinct_authors: null, unknown_author_commits: 1 };
            data.items[0] = contributionEvent(1, { message: 'Fields unavailable', author: { name: null, login: null }, additions: null, deletions: null, html_url: null });
        } else if (mode === 'pending') {
            data.status = 'pending'; data.history_complete = false; data.metrics = null; data.frequency = []; data.items = []; data.next_cursor = null; data.retry_after_seconds = 30;
        } else {
            data.metrics = { commit_count: 0, additions: 0, deletions: 0, distinct_authors: 0, known_authors: 0, unknown_author_commits: 0 };
            data.frequency = data.frequency.map(bucket => ({ ...bucket, commits: 0 })); data.items = []; data.next_cursor = null;
        }
        return route.fulfill({ json: data });
    });
    await login(page); await page.goto('/overview/activity');
    const view = page.getByRole('region', { name: 'Repository contributions', exact: true });
    await expect(view).toContainText('Partial history · limited to 500 commits');
    await expect(view.getByRole('img', { name: /3 retrieved commits; daily peak 1/ })).toBeVisible();
    await expect(view).toContainText('Author unavailable');
    await expect(view.getByLabel('Additions: Unavailable', { exact: true })).toBeVisible();
    await view.getByRole('button', { name: 'Load more commits' }).click();
    await expect(view.getByRole('alert')).toContainText('This snapshot expired');
    await expect(view.getByText('Fields unavailable', { exact: true })).toBeVisible();
    mode = 'pending'; expired = false;
    await view.getByRole('button', { name: 'Reload contributions' }).click();
    await expect(view).toContainText('Timeline pending');
    await expect(view.getByRole('alert')).toHaveCount(0);
    await expect(view).toContainText('Try again in 30 seconds');
    await expect(view.getByText('No commits in this period.', { exact: true })).toHaveCount(0);
    mode = 'zero'; await view.getByRole('button', { name: 'Refresh contributions' }).click();
    await expect(view.getByText('No commits in this period.', { exact: true })).toBeVisible();
    await expect(view.getByLabel('Additions: 0', { exact: true })).toHaveText('+0');
    await expect(view.getByRole('img', { name: '0 commits; daily peak 0', exact: true })).toBeVisible();
});

test('isolates delayed Contributions across repository/view switches and fetches only the active detail', async ({ page }) => {
    await shell(page);
    const reads: string[] = [];
    let release!: () => void;
    const delayed = new Promise<void>(resolve => { release = resolve; });
    await page.route('**/repositories/*/contributions?*', async route => {
        const id = new URL(route.request().url()).pathname.split('/').at(-2)!;
        reads.push(id);
        if (id === 'contrib-0') await delayed;
        await route.fulfill({ json: contributionSnapshot(id, { items: [contributionEvent(1, { message: `${id} commit` })], next_cursor: null }) }).catch(() => {});
    });
    await login(page); await page.goto('/overview/activity?repo=contrib-0&tab=issues');
    await expect(page.getByRole('heading', { name: 'No open issues', exact: true })).toBeVisible();
    expect(reads).toHaveLength(0);
    const dropdown = page.getByRole('combobox', { name: 'Workspace view' });
    await dropdown.selectOption('contributions');
    await expect(page.getByLabel('Loading contribution metrics', { exact: true })).toBeVisible();
    await expect.poll(() => reads).toContain('contrib-0');
    await page.getByRole('button', { name: 'Select acme/beta', exact: true }).click();
    await expect(page.getByText('contrib-1 commit', { exact: true })).toBeVisible();
    await dropdown.selectOption('pull-requests');
    await expect(page.getByRole('heading', { name: 'No open pull requests', exact: true })).toBeVisible();
    release();
    await expect(page.getByText('contrib-0 commit', { exact: true })).toHaveCount(0);
    await expect(page.getByRole('region', { name: 'Repository contributions', exact: true })).toHaveCount(0);
    await page.getByRole('button', { name: 'Select acme/alpha', exact: true }).click();
    expect(reads).not.toContain('contrib-2');
    await dropdown.selectOption('contributions');
    await expect(page.getByText('contrib-0 commit', { exact: true })).toBeVisible();
    await expect(page.getByText('contrib-1 commit', { exact: true })).toHaveCount(0);
});
