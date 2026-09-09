import { Page, expect } from '@playwright/test';

/**
 * Deterministically logs in by calling the backend's dev-login endpoint directly.
 * By using the page's request context, cookies returned by the backend
 * (such as auth_token) are automatically stored in the browser's context
 * and sent on subsequent requests.
 */
export async function login(page: Page) {
    // Hit the backend /dev-login direct API
    const response = await page.request.post('http://localhost:8000/api/v1/auth/dev-login');

    // Ensure we get a successful 200 response
    expect(response.status()).toBe(200);

    // The dev login will set a cookie in the response. Since we use `page.request`, 
    // that cookie is natively mapped to the browser context for the same origin.
    // We can just return the data if needed.
    const data = await response.json();
    return data;
}

/**
 * Programmatically clears the session by hitting the backend logout endpoint.
 */
export async function logout(page: Page) {
    const response = await page.request.post('http://localhost:8000/api/v1/auth/logout');
    expect(response.status()).toBe(200);
}
