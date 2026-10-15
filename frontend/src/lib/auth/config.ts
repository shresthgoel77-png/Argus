/**
 * Auth provider detection — single source of truth for the frontend.
 *
 * Clerk is the only supported authentication provider. This helper reports
 * whether the required frontend configuration is present; it never selects
 * an alternate provider.
 */

export function isClerkEnabled(): boolean {
    return typeof process !== "undefined"
        && typeof process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY === "string"
        && process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY.length > 0;
}

/**
 * Returns the Clerk sign-in route.
 */
export function getAuthLoginPath(): string {
    return "/sign-in";
}
