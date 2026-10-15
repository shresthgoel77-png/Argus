type ClerkTokenGetter = () => Promise<string | null>;

let clerkTokenGetter: ClerkTokenGetter | null = null;
let pendingTokenGetterResolvers: Array<(getter: ClerkTokenGetter) => void> = [];

export function setClerkTokenGetter(getter: ClerkTokenGetter | null): void {
    clerkTokenGetter = getter;
    if (getter) {
        for (const resolve of pendingTokenGetterResolvers) {
            resolve(getter);
        }
        pendingTokenGetterResolvers = [];
    }
}

export function clearClerkTokenGetter(getter: ClerkTokenGetter): void {
    if (clerkTokenGetter === getter) {
        clerkTokenGetter = null;
    }
}

export async function getClerkAuthorizationHeaders(): Promise<Record<string, string>> {
    if (typeof window === "undefined") return {};

    const getter = clerkTokenGetter ?? await new Promise<ClerkTokenGetter>((resolve) => {
        pendingTokenGetterResolvers.push(resolve);
    });
    const token = await getter();
    return token ? { Authorization: `Bearer ${token}` } : {};
}
