export interface NotificationPreferences {
    email_enabled: boolean;
    min_severity_email: "critical" | "high" | "medium" | "low" | "info";
}

export class NotificationPreferencesApiError extends Error {
    constructor(message: string, public status?: number) {
        super(message);
        this.name = "NotificationPreferencesApiError";
    }
}

export async function getNotificationPreferences(): Promise<NotificationPreferences> {
    const res = await fetch("/api/v1/users/me/notification-preferences");
    if (!res.ok) {
        throw new NotificationPreferencesApiError("Failed to fetch notification preferences", res.status);
    }
    return res.json() as Promise<NotificationPreferences>;
}

export async function updateNotificationPreferences(
    data: NotificationPreferences
): Promise<NotificationPreferences> {
    const res = await fetch("/api/v1/users/me/notification-preferences", {
        method: "PATCH",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(data),
    });

    if (!res.ok) {
        throw new NotificationPreferencesApiError("Failed to update notification preferences", res.status);
    }
    return res.json() as Promise<NotificationPreferences>;
}
