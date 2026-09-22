import type { Notification, UnreadCountResponse } from "../types/notifications";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request(endpoint: string, options: RequestInit = {}) {
    return fetch(`${API_URL}${endpoint}`, {
        ...options,
        headers: { "Content-Type": "application/json", ...options.headers },
        credentials: "include",
    });
}

export async function listNotifications(params: { before?: string; unread_only?: boolean; limit?: number } = {}): Promise<Notification[] | null> {
    const query = new URLSearchParams();
    if (params.before) query.set("before", params.before);
    if (params.unread_only) query.set("unread_only", "true");
    if (params.limit) query.set("limit", params.limit.toString());
    try {
        const response = await request(`/api/v1/notifications${query.toString() ? `?${query}` : ""}`);
        return response.ok ? await response.json() as Notification[] : null;
    } catch (error) { console.error("Network error during listNotifications:", error); return null; }
}

export async function getUnreadNotificationCount(): Promise<UnreadCountResponse | null> {
    try { const response = await request("/api/v1/notifications/unread-count"); return response.ok ? await response.json() as UnreadCountResponse : null; }
    catch (error) { console.error("Network error during getUnreadNotificationCount:", error); return null; }
}

export async function markNotificationRead(id: string): Promise<Notification | null> {
    try { const response = await request(`/api/v1/notifications/${id}/read`, { method: "POST" }); return response.ok ? await response.json() as Notification : null; }
    catch (error) { console.error("Network error during markNotificationRead:", error); return null; }
}

export async function markAllNotificationsRead(): Promise<number | null> {
    try {
        const response = await request("/api/v1/notifications/read-all", { method: "POST" });
        return response.ok ? (await response.json() as { count: number }).count : null;
    } catch (error) { console.error("Network error during markAllNotificationsRead:", error); return null; }
}