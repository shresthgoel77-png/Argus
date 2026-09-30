import type { Page } from "@playwright/test";

export async function clerkApiFetch(
    page: Page,
    apiUrl: string,
    path: string,
    init: { method?: string; body?: string } = {},
): Promise<{ status: number; body: string }> {
    return page.evaluate(
        async ({ apiUrl, path, init }) => {
            const clerk = (window as Window & {
                Clerk?: { session?: { getToken: () => Promise<string | null> } | null };
            }).Clerk;
            const token = (await clerk?.session?.getToken()) ?? null;
            const res = await fetch(`${apiUrl}${path}`, {
                method: init.method ?? "GET",
                body: init.body,
                headers: {
                    "Content-Type": "application/json",
                    ...(token ? { Authorization: `Bearer ${token}` } : {}),
                },
            });
            return { status: res.status, body: await res.text() };
        },
        { apiUrl, path, init },
    );
}
