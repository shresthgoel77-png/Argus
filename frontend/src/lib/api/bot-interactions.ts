import type { BotInteractionListResponse } from "../types/bot-interactions";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function listRepositoryBotInteractions(
    repositoryId: string,
    params?: Record<string, string>,
): Promise<BotInteractionListResponse | null> {
    const queryString = params && Object.keys(params).length > 0
        ? `?${new URLSearchParams(params).toString()}`
        : "";

    try {
        const response = await fetch(
            `${API_URL}/api/v1/repositories/${repositoryId}/bot-interactions${queryString}`,
            {
                headers: { "Content-Type": "application/json" },
                credentials: "include",
            },
        );
        if (!response.ok) {
            console.error("listRepositoryBotInteractions failed with status:", response.status);
            return null;
        }
        return await response.json() as BotInteractionListResponse;
    } catch (error) {
        console.error("Network error during listRepositoryBotInteractions:", error);
        return null;
    }
}