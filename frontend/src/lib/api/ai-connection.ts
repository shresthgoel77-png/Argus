import { AIConnectionRequest, AIConnectionStatus, AIProviderKey } from "../types/ai-connection";

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

function parseAIConnectionStatus(payload: {
    configured: boolean;
    provider?: AIProviderKey;
    model?: string;
    status?: "valid" | "invalid" | "error";
    last_validated_at?: string;
}): AIConnectionStatus {
    return {
        configured: payload.configured,
        provider: payload.provider,
        model: payload.model,
        status: payload.status,
        lastValidatedAt: payload.last_validated_at,
    };
}

export async function createOrReplaceAIConnection(
    params: AIConnectionRequest
): Promise<AIConnectionStatus | null> {
    try {
        const res = await fetchClient("/api/v1/ai/connection", {
            method: "POST",
            body: JSON.stringify({
                provider: params.provider,
                model: params.model,
                api_key: params.apiKey,
            }),
        });
        if (!res.ok) {
            console.error("createOrReplaceAIConnection failed with status:", res.status);
            return null;
        }
        return parseAIConnectionStatus(await res.json());
    } catch {
        console.error("Network error during createOrReplaceAIConnection");
        return null;
    }
}

export async function getAIConnectionStatus(): Promise<AIConnectionStatus | null> {
    try {
        const res = await fetchClient("/api/v1/ai/connection");
        if (!res.ok) {
            console.error("getAIConnectionStatus failed with status:", res.status);
            return null;
        }
        return parseAIConnectionStatus(await res.json());
    } catch {
        console.error("Network error during getAIConnectionStatus");
        return null;
    }
}

export async function deleteAIConnection(): Promise<void> {
    try {
        const res = await fetchClient("/api/v1/ai/connection", { method: "DELETE" });
        if (!res.ok) {
            console.error("deleteAIConnection failed with status:", res.status);
        }
    } catch {
        console.error("Network error during deleteAIConnection");
    }
}