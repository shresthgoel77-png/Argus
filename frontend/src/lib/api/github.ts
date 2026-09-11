import { GitHubConnection } from "../types/github";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchClient(endpoint: string, options: RequestInit = {}) {
    const mergedOptions: RequestInit = {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...options.headers,
        },
        credentials: "include",
    };

    return fetch(`${API_URL}${endpoint}`, mergedOptions);
}

export async function startInstall(): Promise<{ install_url: string } | null> {
    try {
        const res = await fetchClient("/api/v1/github/install/start");
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
    try {
        const urlParams = new URLSearchParams({
            installation_id: params.installation_id,
            setup_action: params.setup_action,
            state: params.state,
        });

        const res = await fetchClient(`/api/v1/github/install/callback?${urlParams.toString()}`);
        if (!res.ok) {
            console.error("completeInstall failed with status:", res.status);
            return null;
        }
        return await res.json() as GitHubConnection;
    } catch (error) {
        console.error("Network error during completeInstall:", error);
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
