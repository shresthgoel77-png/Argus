import { test, expect, type Page } from '@playwright/test';
import { login } from '../helpers/auth';
import { contributionSnapshot } from '../../src/__tests__/fixtures/repository-contributions';

const repositories = ['alpha', 'beta', 'a-very-long-repository-name-that-must-wrap-on-small-screens', 'delta'].map((name, index) => ({
    id: `hub-${index}`, full_name: `acme/${name}`, private: index === 1,
    default_branch: index === 2 ? null : 'main', monitoring_enabled: index === 1, created_at: '2026-10-18T00:00:00Z',
}));
const workItem = (kind: string, id: string) => ({
    number: 42, title: `${id} ${kind} item`, state: 'open', draft: kind === 'pull-requests',
    html_url: `https://github.com/acme/alpha/${kind === 'issues' ? 'issues' : 'pull'}/42`,
    user: { login: 'octocat' }, labels: [{ name: 'review' }], updated_at: '2026-10-17T00:00:00Z', created_at: null,
});

async function mockWorkspace(page: Page) {
    const requests: string[] = [];
    // All app API traffic stays mocked, including the post-login Overview and bell.
    await page.route('**/api/v1/**', async route => {
        const path = new URL(route.request().url()).pathname;
        requests.push(path);
        if (path === '/api/v1/repositories') return route.fulfill({ json: repositories });
        const contributions = path.match(/\/repositories\/([^/]+)\/contributions$/);
        if (contributions) return route.fulfill({ json: contributionSnapshot(contributions[1], { next_cursor: null }) });
        const match = path.match(/\/repositories\/([^/]+)\/(issues|pull-requests)$/);
        if (match) return route.fulfill({ json: [workItem(match[2], match[1])] });
        if (path.endsWith('/unread-count')) return route.fulfill({ json: { count: 0 } });
        return route.fulfill({ json: null });
    });
    return requests;
}

test.describe('Activity workspace (mocked APIs)', () => {
    test('supports keyboard selection, native detail parity, reload, and Back/Forward URL state', async ({ page }) => {
        const requests = await mockWorkspace(page);
        await login(page);
        await page.goto('/overview/activity');
        await expect(page.getByRole('heading', { name: 'Repository contributions', exact: true })).toBeVisible();
        await expect(page.getByRole('button', { name: 'Select acme/alpha', exact: true })).toHaveAttribute('aria-pressed', 'true');
        const dropdown = page.getByRole('combobox', { name: 'Workspace view' });
        await expect(dropdown.locator('option')).toHaveText(['Contributions', 'Issues', 'Pull Requests']);
        expect(requests.filter(path => /\/(issues|pull-requests|activity)$/.test(path))).toHaveLength(0);
        await expect(page.getByRole('group', { name: 'Filter activity by source' })).toHaveCount(0);
        await expect(page.getByRole('link', { name: 'Issues', exact: true })).toHaveCount(0);
        await expect(page.getByRole('link', { name: 'Pull Requests', exact: true })).toHaveCount(0);
        const beta = page.getByRole('button', { name: 'Select acme/beta', exact: true });
        await beta.focus(); await page.keyboard.press('Enter');
        await expect(beta).toHaveAttribute('aria-pressed', 'true');
        await dropdown.focus(); await page.keyboard.press('Home'); await page.keyboard.press('ArrowDown'); await page.keyboard.press('Enter');
        await expect(page.getByText('hub-1 issues item', { exact: false })).toBeVisible();
        await expect(page.getByText(/open .*opened by octocat.*updated/)).toBeVisible();
        await expect(page.getByText('review', { exact: true })).toBeVisible();
        await expect(page.getByRole('link', { name: 'Open acme/beta on GitHub' })).toHaveAttribute('href', 'https://github.com/acme/beta');
        await expect(page.locator('#repository-workspace').getByRole('combobox')).toHaveCount(1);
        await dropdown.selectOption('pull-requests');
        await expect(page.getByText('hub-1 pull-requests item', { exact: false })).toBeVisible();
        await expect(page.getByText(/open .*draft .*opened by octocat/)).toBeVisible();
        await expect(page).toHaveURL(/repo=hub-1&tab=pull-requests/);
        await page.goBack();
        await expect(dropdown).toHaveValue('issues');
        await expect(page.getByText('hub-1 issues item', { exact: false })).toBeVisible();
        await page.goBack();
        await expect(dropdown).toHaveValue('contributions');
        await page.goBack();
        await expect(page.getByRole('button', { name: 'Select acme/alpha', exact: true })).toHaveAttribute('aria-pressed', 'true');
        await page.goForward(); await page.goForward();
        await expect(dropdown).toHaveValue('issues');
        await page.reload();
        await expect(dropdown).toHaveValue('issues');
        await expect(page.getByText('hub-1 issues item', { exact: false })).toBeVisible();
        expect(requests.filter(path => path.endsWith('/activity'))).toHaveLength(0);
    });

    test('uses three/two/one columns, keeps blue selection, and searches without losing the workspace', async ({ page }, testInfo) => {
        await mockWorkspace(page); await login(page);
        await page.goto('/overview/activity?repo=hub-2&tab=issues');
        await expect(page.getByText('hub-2 issues item', { exact: false })).toBeVisible();
        const list = page.getByRole('list', { name: 'Connected repositories' });
        for (const [width, columns] of [[1440, 3], [1000, 2], [768, 2], [390, 1], [320, 1]]) {
            await page.setViewportSize({ width, height: 1000 });
            await expect.poll(() => list.evaluate(element => getComputedStyle(element).gridTemplateColumns.split(' ').length)).toBe(columns);
            expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
            expect(await page.locator('main').evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
            const heatmap = await page.getByRole('region', { name: 'Your contribution heatmap' }).boundingBox();
            const language = await page.getByRole('region', { name: 'Language footprint' }).boundingBox();
            if (width >= 1024) expect(heatmap!.y).toBe(language!.y);
            else expect(language!.y).toBeGreaterThan(heatmap!.y);
            if ([1440, 390, 320].includes(width)) {
                await page.screenshot({ path: testInfo.outputPath(`activity-${width}.png`), fullPage: true });
                await page.getByRole('combobox', { name: 'Workspace view' }).scrollIntoViewIfNeeded();
                await page.screenshot({ path: testInfo.outputPath(`activity-detail-${width}.png`), fullPage: true });
                await page.locator('main').evaluate(element => { element.scrollTop = 0; });
            }
        }
        const selected = list.getByRole('button', { pressed: true });
        await expect(selected).toHaveClass(/bg-accent\/5/);
        expect(await selected.evaluate(element => getComputedStyle(element).borderColor === getComputedStyle(element.querySelector('.font-semibold')!).color)).toBe(true);
        await page.getByRole('searchbox', { name: 'Search connected repositories' }).fill('  BETA  ');
        await expect(list.getByRole('button')).toHaveCount(1);
        await expect(page.getByRole('heading', { name: repositories[2].full_name, exact: true })).toBeVisible();
        await page.getByRole('searchbox').fill('missing');
        await expect(page.getByText('No matching repositories')).toBeVisible();
        await expect(page.getByText('hub-2 issues item', { exact: false })).toBeVisible();
        await page.getByRole('button', { name: 'Clear search' }).click();
        await expect(list.getByRole('button')).toHaveCount(4);
    });

    test('handles discovery loading/error/empty, invalid URL, revoked access, and detail retry', async ({ page }) => {
        await mockWorkspace(page); await login(page);
        let available = repositories;
        let failed = true;
        let releaseDiscovery!: () => void;
        const discovery = new Promise<void>(resolve => { releaseDiscovery = resolve; });
        await page.route('**/api/v1/repositories', async route => {
            await discovery;
            return failed ? route.fulfill({ status: 503, json: {} }) : route.fulfill({ json: available });
        });
        await page.goto('/overview/activity?repo=not-authorized&tab=invalid');
        await expect(page.getByRole('status', { name: 'Loading repositories' })).toBeVisible();
        releaseDiscovery();
        await expect(page.locator('main').getByRole('alert')).toContainText('Repositories are temporarily unavailable');
        failed = false;
        await page.getByRole('button', { name: 'Try again' }).click();
        await expect(page.getByRole('heading', { name: 'Repository contributions', exact: true })).toBeVisible();
        await expect(page).toHaveURL(/repo=hub-0&tab=contributions/);
        let itemFailed = true;
        await page.route('**/api/v1/repositories/hub-0/issues*', route => itemFailed
            ? route.fulfill({ status: 403, json: { error: { code: 'github_permission_error', message: 'Access revoked' } } })
            : route.fulfill({ json: [] }));
        await page.getByRole('combobox', { name: 'Workspace view' }).selectOption('issues');
        await expect(page.locator('main').getByRole('alert')).toContainText('Access revoked');
        await expect(page.locator('main').getByRole('alert')).toContainText("GitHub App's repository permissions");
        await expect(page.getByRole('heading', { name: 'No open issues', exact: true })).toHaveCount(0);
        itemFailed = false; await page.getByRole('button', { name: 'Try again' }).click();
        await expect(page.getByRole('heading', { name: 'No open issues', exact: true })).toBeVisible();
        available = [repositories[1]];
        await page.getByRole('button', { name: 'Refresh repositories' }).click();
        await expect(page.getByRole('heading', { name: 'acme/beta', exact: true })).toBeVisible();
        await expect(page).toHaveURL(/repo=hub-1&tab=issues/);
        available = []; await page.getByRole('button', { name: 'Refresh repositories' }).click();
        await expect(page.getByText('No connected repositories')).toBeVisible();
        await expect(page.getByRole('combobox', { name: 'Workspace view' })).toHaveCount(0);
        await expect(page).toHaveURL(/activity\?tab=issues$/);
    });

    test('ignores delayed responses across rapid repository/view changes and preserves legacy feature routes', async ({ page }) => {
        await mockWorkspace(page); await login(page);
        let release!: () => void;
        const pending = new Promise<void>(resolve => { release = resolve; });
        let started = false;
        await page.route('**/api/v1/repositories/hub-0/issues*', async route => {
            started = true; await pending;
            await route.fulfill({ json: [workItem('issues', 'obsolete')] }).catch(() => {});
        });
        await page.goto('/overview/activity?repo=hub-0&tab=issues');
        await expect(page.getByLabel('Loading GitHub issues')).toBeVisible();
        await expect.poll(() => started).toBe(true);
        await page.getByRole('button', { name: 'Select acme/beta', exact: true }).click();
        await expect(page.getByText('hub-1 issues item', { exact: false })).toBeVisible();
        await page.getByRole('combobox', { name: 'Workspace view' }).selectOption('pull-requests');
        await expect(page.getByText('hub-1 pull-requests item', { exact: false })).toBeVisible();
        const obsoleteResponse = page.waitForResponse(response => new URL(response.url()).pathname.endsWith('/hub-0/issues'));
        release(); await obsoleteResponse;
        await expect(page.getByText('obsolete issues item', { exact: false })).toHaveCount(0);
        await page.goto('/overview/issues');
        await expect(page).toHaveURL(/overview\/activity\?tab=(issues|pull-requests)&repo=hub-1/);
        await expect(page.getByText('hub-1 issues item', { exact: false })).toBeVisible();
        await page.goto('/overview/pull-requests');
        await expect(page).toHaveURL(/overview\/activity\?tab=(issues|pull-requests)&repo=hub-1/);
        await expect(page.getByText('hub-1 pull-requests item', { exact: false })).toBeVisible();
    });
});


test('legacy detail links preserve scope/context, replace history, and reject ambiguous identity', async ({ page }) => {
    const requests = await mockWorkspace(page); await login(page);
    await page.goto('/overview/repositories');
    await page.goto('/overview/issues/42?repo=hub-1&sort=updated&page=3&label=bug&label=help#details');
    await expect(page).toHaveURL(/overview\/activity\?.*tab=issues.*item=42#details/);
    const link = page.getByRole('link', { name: 'Open item details on GitHub' });
    await expect(link).toHaveAttribute('href', 'https://github.com/acme/beta/issues/42');
    expect(new URL(page.url()).searchParams.getAll('label')).toEqual(['bug', 'help']);
    expect(new URL(page.url()).searchParams.get('page')).toBe('3');
    await expect(page.getByRole('link', { name: 'Activity', exact: true })).toHaveAttribute('aria-current', 'page');
    await page.reload(); await expect(link).toBeVisible();
    await page.goBack(); await expect(page).toHaveURL(/overview\/repositories$/);
    await page.goForward(); await expect(link).toBeVisible();
    await page.goto('/overview/pull-requests/42?repo=hub-1');
    await expect(link).toHaveAttribute('href', 'https://github.com/acme/beta/pull/42');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole('button', { name: /navigation/i }).click();
    const nav = page.getByRole('navigation', { name: 'Mobile app navigation' });
    await expect(nav.getByRole('link')).toHaveText(['Overview', 'Repositories', 'Findings', 'Activity', 'Settings']);
    await expect(nav.getByRole('link', { name: 'Activity', exact: true })).toHaveAttribute('aria-current', 'page');
    await page.keyboard.press('Escape');
    const count = requests.filter(path => /\/(issues|pull-requests)$/.test(path)).length;
    for (const query of ['repo=denied', 'repo=hub-0&repo=hub-1', '']) {
        await page.goto(`/overview/issues/42?${query}`);
        await expect(page.locator('main').getByRole('alert')).toContainText('invalid or its repository is unavailable');
        await expect(link).toHaveCount(0);
    }
    expect(requests.filter(path => /\/(issues|pull-requests)$/.test(path))).toHaveLength(count);
});


test('keeps the light Activity workspace readable without runtime failures or repeated list reads', async ({ page }, testInfo) => {
    const failures: string[] = [];
    page.on('pageerror', error => failures.push(error.message));
    page.on('console', message => { if (message.type() === 'error') failures.push(message.text()); });
    const requests = await mockWorkspace(page); await login(page);
    await page.goto('/overview/activity?repo=hub-1&tab=issues');
    await expect(page.getByText('hub-1 issues item', { exact: false })).toBeVisible();
    await expect(page.getByRole('combobox', { name: 'Workspace view' }).locator('option')).toHaveText(['Contributions', 'Issues', 'Pull Requests']);
    await expect(page.getByRole('group', { name: 'Filter activity by source' })).toHaveCount(0);
    for (const width of [1440, 768, 390, 320]) {
        await page.setViewportSize({ width, height: 1000 });
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        expect(await page.locator('main').evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
        const calendar = page.getByRole('region', { name: 'Your contribution heatmap', exact: true });
        await calendar.scrollIntoViewIfNeeded();
        await page.screenshot({ path: testInfo.outputPath(`activity-audit-summary-${width}.png`) });
        const workspace = page.getByRole('region', { name: 'acme/beta', exact: true });
        await workspace.scrollIntoViewIfNeeded();
        await page.screenshot({ path: testInfo.outputPath(`activity-audit-workspace-${width}.png`) });
    }
    await expect(page.locator('html')).not.toHaveClass(/dark/);
    expect(requests.filter(path => path.endsWith('/hub-1/issues'))).toHaveLength(1);
    expect(requests.filter(path => path.endsWith('/pull-requests'))).toHaveLength(0);
    expect(requests.filter(path => /\/repositories\/[^/]+\/contributions$/.test(path))).toHaveLength(0);
    expect(requests.filter(path => path === '/api/v1/github/contributions')).toHaveLength(1);
    const priorYear = String(new Date().getUTCFullYear() - 1);
    await page.getByLabel('Calendar year').selectOption(priorYear);
    await page.getByRole('combobox', { name: 'Workspace view' }).selectOption('pull-requests');
    await expect(page.getByText('hub-1 pull-requests item', { exact: false })).toBeVisible();
    await page.getByRole('button', { name: 'Select acme/alpha', exact: true }).click();
    await expect(page.getByText('hub-0 pull-requests item', { exact: false })).toBeVisible();
    await expect(page.getByLabel('Calendar year')).toHaveValue(priorYear);
    await page.reload();
    await expect(page.getByText('hub-0 pull-requests item', { exact: false })).toBeVisible();
    await expect(page.getByLabel('Calendar year')).toHaveValue(String(new Date().getUTCFullYear()));
    await page.goto('/overview/activity?repo=hub-1&tab=invalid&item=42');
    await expect(page.locator('main').getByRole('alert')).toContainText('invalid or its repository is unavailable');
    await page.getByRole('button', { name: 'Back to Contributions', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Repository contributions', exact: true })).toBeVisible();
    expect(failures).toEqual([]);
});
