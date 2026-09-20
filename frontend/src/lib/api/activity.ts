import { ActivityFeedResponse } from "../types/activity";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function listRepositoryActivity(
    repositoryId: string,
    params?: Record<string, string>,
): Promise<ActivityFeedResponse | null> {
    const queryString = params && Object.keys(params).length > 0
        ? `?${new URLSearchParams(params).toString()}`
        : "";

    try {
        const response = await fetch(
            `${API_URL}/api/v1/repositories/${repositoryId}/activity${queryString}`,
            {
                headers: { "Content-Type": "application/json" },
                credentials: "include",
            },
        );
        if (!response.ok) {
            console.error("listRepositoryActivity failed with status:", response.status);
            return null;
        }
        return (await response.json()) as ActivityFeedResponse;
    } catch (error) {
        console.error("Network error during listRepositoryActivity:", error);
        return null;
    }
}
