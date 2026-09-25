/**
 * Auth provider detection — single source of truth for the frontend.
 *
 * When NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY is set to a non-empty string,
 * Clerk is the active auth provider.  Otherwise the development adapter
 * is used, matching the backend's own environment-gated selection.
 */

export function isClerkEnabled(): boolean {
    return typeof process !== "undefined"
        && typeof process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY === "string"
        && process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY.length > 0;
}

/**
 * Returns the login path appropriate for the active auth provider.
 * Clerk → /sign-in (hosted Clerk UI)
 * Dev   → /login   (local dev-adapter card)
 */
export function getAuthLoginPath(): string {
    return isClerkEnabled() ? "/sign-in" : "/login";
}
