import { GitHubConnection } from "../types/github";
import { getClerkAuthorizationHeaders } from "../auth/clerk-token";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchClient(endpoint: string, options: RequestInit = {}) {
    const clerkHeaders = await getClerkAuthorizationHeaders();
    const mergedOptions: RequestInit = {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...options.headers,
            ...clerkHeaders,
        },
        credentials: "include",
        cache: "no-store",
    };

    return fetch(`${API_URL}${endpoint}`, mergedOptions);
}

export async function startInstall(connectionId?: string): Promise<{ install_url: string } | null> {
    try {
        const query = connectionId ? `?connection_id=${encodeURIComponent(connectionId)}` : "";
        const res = await fetchClient(`/api/v1/github/install/start${query}`);
        if (!res.ok) {
            console.error("startInstall failed with status:", res.status);
            return null;
        }
        return await res.json() as { install_url: string };
    } catch (error) {
        console.error("Network error during startInstall:", error);
        return null;
    }
}

export async function completeInstall(params: {
    installation_id: string;
    setup_action: string;
    state: string;
}): Promise<GitHubConnection | null> {
    const urlParams = new URLSearchParams({
        installation_id: params.installation_id,
        setup_action: params.setup_action,
        state: params.state,
    });

    const res = await fetchClient(`/api/v1/github/install/callback?${urlParams.toString()}`);
    if (!res.ok) {
        const body = await res.json().catch(() => ({})) as { detail?: string; error?: { message?: string } };
        throw new Error(body.detail || body.error?.message || `GitHub connection failed (HTTP ${res.status}).`);
    }
    return await res.json() as GitHubConnection;
}

export async function syncInstallation(installation_id: string): Promise<GitHubConnection | null> {
    try {
        const res = await fetchClient(`/api/v1/github/sync`, {
            method: "POST",
            body: JSON.stringify({ installation_id }),
        });
        if (!res.ok) {
            console.error("syncInstallation failed with status:", res.status);
            return null;
        }
        return await res.json() as GitHubConnection;
    } catch (error) {
        console.error("Network error during syncInstallation:", error);
        return null;
    }
}

export async function getConnections(): Promise<GitHubConnection[] | null> {
    try {
        const res = await fetchClient("/api/v1/github/connections");
        if (!res.ok) {
            console.error("getConnections failed with status:", res.status);
            return null;
        }
        return await res.json() as GitHubConnection[];
    } catch (error) {
        console.error("Network error during getConnections:", error);
        return null;
    }
}
