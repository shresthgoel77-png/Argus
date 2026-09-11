import { AuthUser } from "../auth/types";

// Get the base API URL from environment, fallback to localhost for development
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Standard fetch wrapper that enforces credentials/cookies inclusion and handles JSON headers.
 * Centralizing this here simplifies endpoint calls.
 */
async function fetchClient(endpoint: string, options: RequestInit = {}) {
    const mergedOptions: RequestInit = {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...options.headers,
        },
        // Crucial for cookie-based auth
        credentials: "include",
    };

    return fetch(`${API_URL}${endpoint}`, mergedOptions);
}

/**
 * Fetch the currently logged-in user from the backend.
 * Uses cookies sent via `credentials: "include"`.
 * Returns the AuthUser if successful, null if 401 or network error.
 */
export async function getCurrentUser(): Promise<AuthUser | null> {
    try {
        const res = await fetchClient("/api/v1/auth/me");
        if (!res.ok) {
            if (res.status === 401) return null;
            console.warn("Failed to get current user", res.status);
            return null;
        }
        return await res.json() as AuthUser;
    } catch (error) {
        console.error("Network error getting current user:", error);
        return null;
    }
}

/**
 * For development purposes ONLY. Logs in a test user and establishes a session cookie.
 */
export async function devLogin(): Promise<AuthUser | null> {
    try {
        const res = await fetchClient("/api/v1/auth/dev-login", { method: "POST" });
        if (!res.ok) {
            console.error("devLogin failed with status:", res.status);
            return null;
        }
        return await res.json() as AuthUser;
    } catch (error) {
        console.error("Network error during devLogin:", error);
        return null;
    }
}

/**
 * Logs out the current user, instructing the backend to clear the session cookie.
 */
export async function logout(): Promise<void> {
    try {
        const res = await fetchClient("/api/v1/auth/logout", { method: "POST" });
        if (!res.ok) {
            console.error("logout failed with status:", res.status);
        }
    } catch (error) {
        console.error("Network error during logout:", error);
    }
}
