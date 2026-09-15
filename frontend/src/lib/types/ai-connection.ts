export type AIProviderKey = "gemini" | (string & {});

export type AIConnectionStatus = {
    configured: boolean;
    provider?: AIProviderKey;
    model?: string;
    status?: "valid" | "invalid" | "error";
    lastValidatedAt?: string;
};

export type AIConnectionRequest = {
    provider: AIProviderKey;
    model: string;
    apiKey: string;
};