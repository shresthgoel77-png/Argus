import type { AIAnalysis, AIAnalysisResponse } from "../types/ai-analysis";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class AIAnalysisApiError extends Error {
    readonly status: number;

    constructor(status: number, message: string) {
        super(message);
        this.name = "AIAnalysisApiError";
        this.status = status;
    }
}

async function fetchClient(endpoint: string, options: RequestInit = {}) {
    return fetch(`${API_URL}${endpoint}`, {
        ...options,
        headers: { "Content-Type": "application/json", ...options.headers },
        credentials: "include",
    });
}

async function throwApiError(response: Response): Promise<never> {
    let message = "The AI analysis request could not be completed.";
    try {
        const payload = await response.json() as { detail?: string; error_message?: string };
        const apiMessage = payload.error_message ?? payload.detail;
        if (typeof apiMessage === "string" && apiMessage.length > 0) message = apiMessage;
    } catch {
        // Keep the user-facing message calm when the API response is not JSON.
    }
    throw new AIAnalysisApiError(response.status, message);
}

async function requestAnalysis<T>(endpoint: string, options?: RequestInit): Promise<T> {
    try {
        const response = await fetchClient(endpoint, options);
        if (!response.ok) return throwApiError(response);
        return await response.json() as T;
    } catch (error) {
        if (error instanceof AIAnalysisApiError) throw error;
        throw new AIAnalysisApiError(0, "The AI analysis service could not be reached.");
    }
}

export function getFindingAIAnalysis(findingId: string): Promise<AIAnalysisResponse> {
    return requestAnalysis<AIAnalysisResponse>(`/api/v1/findings/${findingId}/ai-analysis`);
}

export function createFindingAIAnalysis(findingId: string): Promise<AIAnalysis> {
    return requestAnalysis<AIAnalysis>(`/api/v1/findings/${findingId}/ai-analysis`, { method: "POST" });
}