import { AvailableRepository, Repository } from "../types/github";

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

export async function getAvailableRepositories(connectionId: string): Promise<AvailableRepository[] | null> {
    try {
        const res = await fetchClient(`/api/v1/github/connections/${connectionId}/repositories`);
        if (!res.ok) {
            console.error("getAvailableRepositories failed with status:", res.status);
            return null;
        }
        return await res.json() as AvailableRepository[];
    } catch (error) {
        console.error("Network error during getAvailableRepositories:", error);
        return null;
    }
}

export async function addRepository(params: {
    connection_id: string;
    github_repo_id: number;
}): Promise<Repository | null> {
    try {
        const res = await fetchClient("/api/v1/repositories", {
            method: "POST",
            body: JSON.stringify(params),
        });
        if (!res.ok) {
            console.error("addRepository failed with status:", res.status);
            return null;
        }
        return await res.json() as Repository;
    } catch (error) {
        console.error("Network error during addRepository:", error);
        return null;
    }
}

export async function getRepositories(): Promise<Repository[] | null> {
    try {
        const res = await fetchClient("/api/v1/repositories");
        if (!res.ok) {
            console.error("getRepositories failed with status:", res.status);
            return null;
        }
        return await res.json() as Repository[];
    } catch (error) {
        console.error("Network error during getRepositories:", error);
        return null;
    }
}

export async function setMonitoringEnabled(
    repositoryId: string,
    enabled: boolean
): Promise<Repository | null> {
    try {
        const res = await fetchClient(`/api/v1/repositories/${repositoryId}`, {
            method: "PATCH",
            body: JSON.stringify({ monitoring_enabled: enabled }),
        });
        if (!res.ok) {
            console.error("setMonitoringEnabled failed with status:", res.status);
            return null;
        }
        return await res.json() as Repository;
    } catch (error) {
        console.error("Network error during setMonitoringEnabled:", error);
        return null;
    }
}
