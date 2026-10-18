import { test, expect } from '@playwright/test';
import { login } from '../helpers/auth';

const today = new Date().toISOString().slice(0, 10);
const currentYear = Number(today.slice(0, 4));
function calendar(year: number) {
    const end = year === currentYear ? today : `${year}-12-31`;
    const yesterday = new Date(Date.parse(`${today}T00:00:00Z`) - 86400000).toISOString().slice(0, 10);
    const days = [];
    for (let time = Date.UTC(year, 0, 1); new Date(time).toISOString().slice(0, 10) <= end; time += 86400000) {
        const date = new Date(time).toISOString().slice(0, 10);
        const count = year === 2024 && date === '2024-02-29' ? 3 : year === currentYear ? date === today ? 2 : date === yesterday ? 1 : 0 : 0;
        days.push({ date, count, level: count ? 2 : 0 });
    }
    return { status: 'available', year, as_of_date: today, days, total: days.reduce((sum, day) => sum + day.count, 0), login: 'verified-person', github_user_id: '42', access_context: 'a'.repeat(64) };
}
async function mockShell(page: import('@playwright/test').Page) {
    await page.route('**/api/v1/**', route => {
        const path = new URL(route.request().url()).pathname;
        return route.fulfill({ json: path.endsWith('/repositories') ? [] : path.endsWith('/unread-count') ? { count: 0 } : null });
    });
}

test('renders verified personal counts, leap alignment, keyboard tooltips, current streak, and responsive 65/35 summaries', async ({ page }, testInfo) => {
    await mockShell(page);
    await page.route('**/api/v1/github/contributions?*', route => route.fulfill({ json: calendar(Number(new URL(route.request().url()).searchParams.get('year'))) }));
    await login(page); await page.goto('/overview/activity');
    const heatmap = page.getByRole('region', { name: 'Your contribution heatmap', exact: true });
    await expect(heatmap.getByRole('heading', { name: `3 contributions in ${currentYear}`, exact: true })).toBeVisible();
    await expect(heatmap).toContainText(`Current streak: 2 days · through ${today}`);
    const years = page.getByLabel('Calendar year');
    await years.focus(); await years.press('ArrowDown'); await years.press('Enter');
    await expect(years).toHaveValue(String(currentYear - 1));
    await years.selectOption('2024');
    await expect(heatmap.getByRole('heading', { name: '3 contributions in 2024', exact: true })).toBeVisible();
    await expect(heatmap).toContainText('Historical year · current streak is not shown.');
    await expect(heatmap.locator('[data-state="covered"]')).toHaveCount(366);
    const january = heatmap.locator('[data-date="2024-01-01"]');
    expect(await january.evaluate(element => getComputedStyle(element).gridRowStart)).toBe('3'); // Monday.
    const leap = heatmap.getByRole('button', { name: '3 contributions on February 29, 2024', exact: true });
    await leap.focus();
    await expect(heatmap.getByRole('tooltip')).toHaveText('3 contributions on February 29, 2024');
    await leap.press('ArrowRight');
    await expect(heatmap.locator('[data-date="2024-03-07"]')).toBeFocused();
    await expect(heatmap.getByRole('tooltip')).toHaveText('0 contributions on March 7, 2024');
    await expect(heatmap.getByLabel('Contribution intensity: Less to More')).toContainText('Less');
    const language = page.getByRole('region', { name: 'Language footprint', exact: true });
    for (const width of [1440, 1024, 390, 320]) {
        await page.setViewportSize({ width, height: 1000 });
        const calendarBox = await heatmap.boundingBox(), languageBox = await language.boundingBox();
        if (width >= 1024) {
            expect(calendarBox!.y).toBe(languageBox!.y);
            expect(calendarBox!.width / languageBox!.width).toBeCloseTo(1.85, 1);
        } else expect(languageBox!.y).toBeGreaterThan(calendarBox!.y);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        expect(await page.locator('main').evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
        await heatmap.scrollIntoViewIfNeeded();
        await page.screenshot({ path: testInfo.outputPath(`personal-calendar-${width}.png`), fullPage: true });
    }
    const scroller = heatmap.getByRole('region', { name: /Contribution calendar for 2024/ });
    expect(await scroller.evaluate(element => element.scrollWidth > element.clientWidth)).toBe(true);
    await scroller.evaluate(element => { element.scrollLeft = element.scrollWidth; });
    await page.screenshot({ path: testInfo.outputPath('personal-calendar-320-december.png'), fullPage: true });
});

test('isolates rapid year responses and shows missing/future dates and access failures without zero totals', async ({ page }) => {
    await mockShell(page);
    let release!: () => void, first = true, mode = 'identity';
    const held = new Promise<void>(resolve => { release = resolve; });
    await page.route('**/api/v1/github/contributions?*', async route => {
        const year = Number(new URL(route.request().url()).searchParams.get('year'));
        if (year !== currentYear) return route.fulfill({ json: calendar(year) });
        if (first) { first = false; await held; return route.fulfill({ json: calendar(year) }); }
        if (mode === 'permission') return route.fulfill({ status: 403, json: { detail: 'Access denied' } });
        if (mode === 'partial') { const result = calendar(year); result.days = result.days.filter(day => day.date !== `${year}-01-02`); return route.fulfill({ json: result }); }
        return route.fulfill({ json: { status: 'unavailable', year, as_of_date: today, total: null, days: [], reason: 'identity_unavailable' } });
    });
    await login(page); await page.goto('/overview/activity');
    const heatmap = page.getByRole('region', { name: 'Your contribution heatmap', exact: true });
    await expect(heatmap).toContainText(`Loading contributions in ${currentYear}`);
    await page.getByLabel('Calendar year').selectOption(String(currentYear - 1));
    await expect(heatmap.getByRole('heading', { name: `0 contributions in ${currentYear - 1}`, exact: true })).toBeVisible();
    const obsoleteFinished = page.waitForResponse(response => response.url().includes(`/github/contributions?year=${currentYear}`));
    release(); await obsoleteFinished;
    await expect(heatmap.getByRole('heading', { name: `0 contributions in ${currentYear - 1}`, exact: true })).toBeVisible();
    await page.getByLabel('Calendar year').selectOption(String(currentYear));
    await expect(heatmap).toContainText(`Contributions unavailable in ${currentYear}`);
    await expect(heatmap).toContainText('A verified linked GitHub user is not available');
    await expect(heatmap.locator('[data-state="covered"]')).toHaveCount(0);
    await expect(heatmap.locator('[data-state="missing"]')).not.toHaveCount(0);
    await expect(heatmap.locator('[data-state="future"]')).not.toHaveCount(0);
    mode = 'permission'; await heatmap.getByRole('button', { name: 'Retry calendar' }).click();
    await expect(heatmap).toContainText('GitHub could not return a verified personal calendar');
    mode = 'partial'; await heatmap.getByRole('button', { name: 'Retry calendar' }).click();
    await expect(heatmap.getByRole('heading', { name: `3 reported contributions in ${currentYear}`, exact: true })).toBeVisible();
    await expect(heatmap).toContainText('Partial date coverage; missing dates are not zero');
    await expect(heatmap.locator(`[data-date="${currentYear}-01-02"]`)).toHaveAttribute('aria-label', `January 2, ${currentYear}: contribution data missing`);
});
