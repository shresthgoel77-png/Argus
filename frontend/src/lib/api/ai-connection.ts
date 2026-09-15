import { AIConnectionRequest, AIConnectionStatus, AIProviderKey } from "../types/ai-connection";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const AI_PROVIDER_OPTIONS: Array<{ key: AIProviderKey; label: string; models: string[] }> = [
    {
        key: "gemini",
        label: "Gemini",
        models: [
            "gemini-3.8-flash",
            "gemini-3.7-flash",
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-3.1-pro-preview",
            "gemini-3-flash-preview",
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
        ],
    },
];

export class AIConnectionApiError extends Error {
    readonly status: number;

    constructor(status: number, message: string) {
        super(message);
        this.name = "AIConnectionApiError";
        this.status = status;
    }
}

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

async function throwApiError(response: Response): Promise<never> {
    let message = "The AI connection request could not be completed.";
    try {
        const payload = await response.json() as { detail?: string };
        if (typeof payload.detail === "string" && payload.detail.length > 0) {
            message = payload.detail;
        }
    } catch {
        // Keep the UI message generic when the API did not return JSON.
    }
    throw new AIConnectionApiError(response.status, message);
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
): Promise<AIConnectionStatus> {
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
            return throwApiError(res);
        }
        return parseAIConnectionStatus(await res.json());
    } catch (error) {
        if (error instanceof AIConnectionApiError) throw error;
        throw new AIConnectionApiError(0, "The AI connection could not be reached.");
    }
}

export async function getAIConnectionStatus(): Promise<AIConnectionStatus> {
    try {
        const res = await fetchClient("/api/v1/ai/connection");
        if (!res.ok) {
            return throwApiError(res);
        }
        return parseAIConnectionStatus(await res.json());
    } catch (error) {
        if (error instanceof AIConnectionApiError) throw error;
        throw new AIConnectionApiError(0, "The AI connection status could not be loaded.");
    }
}

export async function deleteAIConnection(): Promise<void> {
    try {
        const res = await fetchClient("/api/v1/ai/connection", { method: "DELETE" });
        if (!res.ok) {
            return throwApiError(res);
        }
    } catch (error) {
        if (error instanceof AIConnectionApiError) throw error;
        throw new AIConnectionApiError(0, "The AI connection could not be removed.");
    }
}