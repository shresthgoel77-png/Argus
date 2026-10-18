import { test, expect } from '@playwright/test';
import { login } from '../helpers/auth';

const repos = ['alpha', 'beta', 'empty', 'unavailable'].map((name, index) => ({
    id: `metadata-${index}`, full_name: `acme/${name}`, private: index === 1,
    monitoring_enabled: false, default_branch: 'main', created_at: '2026-10-18T00:00:00Z',
}));
const details = (index: number) => ({
    repository_id: repos[index].id, metadata_status: 'available', primary_language_status: index === 2 ? 'none' : 'known',
    primary_language: index === 2 ? null : index === 3 ? 'Python' : 'TypeScript',
    description: 'Repository description from authorized GitHub metadata. '.repeat(5), topics: ['developer-tools', 'testing'],
    stars: 0, forks: 2, open_issues_and_pull_requests: 7, updated_at: '2026-10-18T00:00:00Z',
    languages_status: 'available', language_bytes: index === 2 ? {} : { TypeScript: 750, CSS: 250 }, fetched_at: '2026-10-18T00:00:00Z',
});

test('keeps primary-repository and byte denominators distinct, isolates failed metadata, and preserves count during search', async ({ page }, testInfo) => {
    let failed = true;
    const workItemLists: string[] = [];
    await page.route('**/api/v1/**', async route => {
        const path = new URL(route.request().url()).pathname;
        if (/\/(issues|pull-requests)$/.test(path)) workItemLists.push(path);
        if (path === '/api/v1/repositories') return route.fulfill({ json: repos });
        const match = path.match(/metadata-(\d)\/activity-metadata$/);
        if (match) {
            const index = Number(match[1]);
            return index === 3 && failed ? route.fulfill({ status: 403, json: { detail: 'Access unavailable' } }) : route.fulfill({ json: details(index) });
        }
        return route.fulfill({ json: path.endsWith('/unread-count') ? { count: 0 } : null });
    });
    await login(page); await page.goto('/overview/activity');
    const footprint = page.getByRole('region', { name: 'Language footprint', exact: true });
    await expect(footprint).toContainText('4 connected repositories');
    await expect(footprint).toContainText('Partial coverage: 3/4');
    await expect(footprint.getByRole('listitem').filter({ hasText: 'TypeScript' })).toContainText('2 repos · 50.0%');
    await expect(footprint.getByRole('listitem').filter({ hasText: 'No primary language' })).toContainText('1 repo · 25.0%');
    await expect(footprint.getByRole('listitem').filter({ hasText: 'Unknown' })).toContainText('1 repo · 25.0%');
    const alpha = page.getByRole('button', { name: 'Select acme/alpha', exact: true });
    await expect(alpha).toContainText('Stars: 0'); await expect(alpha).toContainText('Forks: 2');
    await expect(alpha).toContainText('Open issues + PRs: 7');
    await expect(alpha).toContainText('TypeScript 75.0%'); await expect(alpha).toContainText('CSS 25.0%');
    await expect(alpha).toContainText('developer-tools'); await expect(alpha).toContainText('Updated');
    await expect(alpha.locator('.line-clamp-2')).toHaveCSS('-webkit-line-clamp', '2');
    const unknown = page.getByRole('button', { name: 'Select acme/unavailable', exact: true });
    await expect(unknown).toContainText('Primary language unknown'); await expect(unknown).toContainText('Stars: unavailable');
    await expect(page.getByRole('button', { name: 'Select acme/empty', exact: true })).toContainText('No language bytes reported');
    expect(workItemLists).toEqual([]);
    for (const width of [1440, 390, 320]) {
        await page.setViewportSize({ width, height: 1000 });
        expect(await page.locator('main').evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
        await footprint.scrollIntoViewIfNeeded(); await page.screenshot({ path: testInfo.outputPath(`footprint-${width}.png`) });
        await alpha.scrollIntoViewIfNeeded(); await page.screenshot({ path: testInfo.outputPath(`metadata-${width}.png`) });
    }
    await page.getByRole('searchbox').fill('beta');
    await expect(page.getByRole('list', { name: 'Connected repositories' }).getByRole('button')).toHaveCount(1);
    await expect(footprint).toContainText('4 connected repositories');
    await expect(footprint.getByRole('listitem').filter({ hasText: 'TypeScript' })).toContainText('2 repos · 50.0%');
    failed = false; await page.getByRole('button', { name: 'Refresh repositories' }).click();
    await expect(footprint).toContainText('Complete primary-language coverage: 4/4');
    await expect(footprint.getByRole('listitem').filter({ hasText: 'Python' })).toContainText('1 repo · 25.0%');
});

test('shows confirmed no-language as complete coverage and handles an empty connected collection', async ({ page }) => {
    let connected = [repos[2]];
    await page.route('**/api/v1/**', route => {
        const path = new URL(route.request().url()).pathname;
        if (path === '/api/v1/repositories') return route.fulfill({ json: connected });
        if (path.endsWith('/activity-metadata')) return route.fulfill({ json: details(2) });
        return route.fulfill({ json: path.endsWith('/unread-count') ? { count: 0 } : null });
    });
    await login(page); await page.goto('/overview/activity');
    const footprint = page.getByRole('region', { name: 'Language footprint' });
    await expect(footprint).toContainText('Complete primary-language coverage: 1/1');
    await expect(footprint.getByRole('listitem')).toContainText('No primary language');
    await expect(footprint.getByRole('listitem')).toContainText('1 repo · 100.0%');
    connected = []; await page.getByRole('button', { name: 'Refresh repositories' }).click();
    await expect(footprint).toContainText('0 connected repositories');
    await expect(footprint.getByRole('img')).toHaveCount(0);
});
