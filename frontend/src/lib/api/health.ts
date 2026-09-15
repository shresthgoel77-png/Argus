import { HealthSnapshotListResponse, RepositoryHealthSnapshot } from "../types/health";

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

export async function getRepositoryHealth(repositoryId: string): Promise<RepositoryHealthSnapshot | null> {
    try {
        const res = await fetchClient(`/api/v1/repositories/${repositoryId}/health`);
        if (!res.ok) {
            console.error("getRepositoryHealth failed with status:", res.status);
            return null;
        }
        return (await res.json()) as RepositoryHealthSnapshot;
    } catch (error) {
        console.error("Network error during getRepositoryHealth:", error);
        return null;
    }
}

export async function getRepositoryHealthHistory(
    repositoryId: string,
    params?: Record<string, string>
): Promise<HealthSnapshotListResponse | null> {
    const queryString = params && Object.keys(params).length > 0 ? `?${new URLSearchParams(params).toString()}` : "";
    try {
        const res = await fetchClient(`/api/v1/repositories/${repositoryId}/health/history${queryString}`);
        if (!res.ok) {
            console.error("getRepositoryHealthHistory failed with status:", res.status);
            return null;
        }
        return (await res.json()) as HealthSnapshotListResponse;
    } catch (error) {
        console.error("Network error during getRepositoryHealthHistory:", error);
        return null;
    }
}

export async function triggerHealthRun(repositoryId: string): Promise<RepositoryHealthSnapshot | null> {
    try {
        const res = await fetchClient(`/api/v1/repositories/${repositoryId}/health-runs`, {
            method: "POST"
        });
        if (!res.ok) {
            console.error("triggerHealthRun failed with status:", res.status);
            return null;
        }
        return (await res.json()) as RepositoryHealthSnapshot;
    } catch (error) {
        console.error("Network error during triggerHealthRun:", error);
        return null;
    }
}
