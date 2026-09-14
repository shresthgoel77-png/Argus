import { FindingResponse, FindingListResponse, FindingStatusUpdateRequest } from "../types/findings";

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

export async function listFindings(params?: Record<string, string>): Promise<FindingListResponse | null> {
    const queryString = params && Object.keys(params).length > 0 ? `?${new URLSearchParams(params).toString()}` : "";
    try {
        const res = await fetchClient(`/api/v1/findings${queryString}`);
        if (!res.ok) {
            console.error("listFindings failed with status:", res.status);
            return null;
        }
        return (await res.json()) as FindingListResponse;
    } catch (error) {
        console.error("Network error during listFindings:", error);
        return null;
    }
}

export async function listRepositoryFindings(repositoryId: string, params?: Record<string, string>): Promise<FindingListResponse | null> {
    const queryString = params && Object.keys(params).length > 0 ? `?${new URLSearchParams(params).toString()}` : "";
    try {
        const res = await fetchClient(`/api/v1/repositories/${repositoryId}/findings${queryString}`);
        if (!res.ok) {
            console.error("listRepositoryFindings failed with status:", res.status);
            return null;
        }
        return (await res.json()) as FindingListResponse;
    } catch (error) {
        console.error("Network error during listRepositoryFindings:", error);
        return null;
    }
}

export async function getFinding(id: string): Promise<FindingResponse | null> {
    try {
        const res = await fetchClient(`/api/v1/findings/${id}`);
        if (!res.ok) {
            console.error("getFinding failed with status:", res.status);
            return null;
        }
        return (await res.json()) as FindingResponse;
    } catch (error) {
        console.error("Network error during getFinding:", error);
        return null;
    }
}

export async function updateFindingStatus(
    id: string,
    status: FindingStatusUpdateRequest["status"]
): Promise<FindingResponse | null> {
    try {
        const res = await fetchClient(`/api/v1/findings/${id}/status`, {
            method: "PATCH",
            body: JSON.stringify({ status }),
        });
        if (!res.ok) {
            console.error("updateFindingStatus failed with status:", res.status);
            return null;
        }
        return (await res.json()) as FindingResponse;
    } catch (error) {
        console.error("Network error during updateFindingStatus:", error);
        return null;
    }
}
