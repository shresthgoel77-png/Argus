import { getClerkAuthorizationHeaders } from "../auth/clerk-token";

export interface NotificationPreferences {
    email_enabled: boolean;
    min_severity_email: "critical" | "high" | "medium" | "low" | "info";
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchClient(endpoint: string, options: RequestInit = {}) {
    const clerkHeaders = await getClerkAuthorizationHeaders();
    const mergedOptions: RequestInit = {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...options.headers,
            ...clerkHeaders,
        },
        credentials: "include",
    };

    return fetch(`${API_URL}${endpoint}`, mergedOptions);
}

export class NotificationPreferencesApiError extends Error {
    constructor(message: string, public status?: number) {
        super(message);
        this.name = "NotificationPreferencesApiError";
    }
}

export async function getNotificationPreferences(): Promise<NotificationPreferences> {
    try {
        const res = await fetchClient("/api/v1/notifications/preferences");
        if (!res.ok) {
            throw new NotificationPreferencesApiError("Failed to fetch notification preferences", res.status);
        }
        return await res.json() as NotificationPreferences;
    } catch (error) {
        if (error instanceof NotificationPreferencesApiError) throw error;
        throw new NotificationPreferencesApiError("Failed to fetch notification preferences");
    }
}

export async function updateNotificationPreferences(
    data: NotificationPreferences
): Promise<NotificationPreferences> {
    try {
        const res = await fetchClient("/api/v1/notifications/preferences", {
            method: "PUT",
            body: JSON.stringify(data),
        });

        if (!res.ok) {
            throw new NotificationPreferencesApiError("Failed to update notification preferences", res.status);
        }
        return await res.json() as NotificationPreferences;
    } catch (error) {
        if (error instanceof NotificationPreferencesApiError) throw error;
        throw new NotificationPreferencesApiError("Failed to update notification preferences");
    }
}
