# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: tests\auth-protected-routes.spec.ts >> Authentication and Protected Routes >> UI login form flow works correctly
- Location: e2e\tests\auth-protected-routes.spec.ts:42:9

# Error details

```
Error: page.goto: net::ERR_CONNECTION_REFUSED at http://localhost:3000/login
Call log:
  - navigating to "http://localhost:3000/login", waiting until "load"

```

# Test source

```ts
  1  | import { test, expect } from '@playwright/test';
  2  | import { login, logout } from '../helpers/auth';
  3  | 
  4  | test.describe('Authentication and Protected Routes', () => {
  5  | 
  6  |     test('unauthenticated user is redirected to /login when accessing protected route', async ({ page }) => {
  7  |         // Attempt to navigate to a protected app route
  8  |         await page.goto('/overview');
  9  | 
  10 |         // We expect the app to redirect us because no cookie is set
  11 |         await expect(page).toHaveURL(/.*\/login/);
  12 |     });
  13 | 
  14 |     test('programmatic login allows access to protected routes', async ({ page }) => {
  15 |         // Note: We use the helper to establish the session without touching the UI
  16 |         await login(page);
  17 | 
  18 |         // Now navigate to a protected route
  19 |         await page.goto('/overview');
  20 | 
  21 |         // Expect we are genuinely on the overview page and not redirected
  22 |         await expect(page).toHaveURL(/.*\/overview/);
  23 |     });
  24 | 
  25 |     test('programmatic logout revokes access', async ({ page }) => {
  26 |         await login(page);
  27 | 
  28 |         // Validate we're allowed in initially
  29 |         await page.goto('/overview');
  30 |         await expect(page).toHaveURL(/.*\/overview/);
  31 | 
  32 |         // Now log out through the backend programmatic helper
  33 |         await logout(page);
  34 | 
  35 |         // Reload the page. The backend cookie should be invalid/cleared.
  36 |         await page.reload();
  37 | 
  38 |         // Thus we expect a redirect to login
  39 |         await expect(page).toHaveURL(/.*\/login/);
  40 |     });
  41 | 
  42 |     test('UI login form flow works correctly', async ({ page }) => {
  43 |         // This test actually walks the real UI as per requirements
> 44 |         await page.goto('/login');
     |                    ^ Error: page.goto: net::ERR_CONNECTION_REFUSED at http://localhost:3000/login
  45 | 
  46 |         // Submit the dev login form (assumes there is a submit button)
  47 |         // Based on standard dev-login conventions from Prompts 1-6
  48 |         const submitButton = page.locator('button[type="submit"], button:has-text("Login")');
  49 |         await expect(submitButton).toBeVisible();
  50 |         await submitButton.click();
  51 | 
  52 |         // Wait for the redirect to overview
  53 |         await page.waitForURL(/.*\/overview/, { timeout: 5000 });
  54 |         await expect(page).toHaveURL(/.*\/overview/);
  55 |     });
  56 | 
  57 | });
  58 | 
```