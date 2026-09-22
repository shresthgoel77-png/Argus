export interface NotificationPreferences {
    email_enabled: boolean;
    min_severity_email: "critical" | "high" | "medium" | "low" | "info";
}

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

export class NotificationPreferencesApiError extends Error {
    constructor(message: string, public status?: number) {
        super(message);
        this.name = "NotificationPreferencesApiError";
    }
}

export async function getNotificationPreferences(): Promise<NotificationPreferences> {
    const res = await fetchClient("/api/v1/notifications/preferences");
    if (!res.ok) {
        throw new NotificationPreferencesApiError("Failed to fetch notification preferences", res.status);
    }
    return res.json() as Promise<NotificationPreferences>;
}

export async function updateNotificationPreferences(
    data: NotificationPreferences
): Promise<NotificationPreferences> {
    const res = await fetchClient("/api/v1/notifications/preferences", {
        method: "PATCH",
        body: JSON.stringify(data),
    });

    if (!res.ok) {
        throw new NotificationPreferencesApiError("Failed to update notification preferences", res.status);
    }
    return res.json() as Promise<NotificationPreferences>;
}
