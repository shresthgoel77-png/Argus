"use client";

import { Bell } from "lucide-react";
import type { Notification } from "@/lib/types/notifications";

export function notificationRoute(notification: Notification): string | null {
    if (notification.reference_type === "finding") return `/overview/findings/${notification.reference_id}`;
    if (notification.reference_type === "health_snapshot" && notification.repository_id) return `/overview/repositories/${notification.repository_id}`;
    return null;
}

function formatDate(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "Date unavailable" : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function NotificationItem({ notification, onClick }: { notification: Notification; onClick: () => void }) {
    return <button type="button" onClick={onClick} className="flex w-full items-start gap-3 border-b p-4 text-left transition-colors last:border-b-0 hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
        <span className={`mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full ${notification.read_at ? "bg-muted text-muted-foreground" : "bg-accent/15 text-accent"}`}><Bell className="size-4" aria-hidden="true" /></span>
        <span className="min-w-0 flex-1"><span className="flex items-start justify-between gap-3"><span className="font-medium text-foreground">{notification.title}</span>{!notification.read_at ? <span className="mt-1 size-2 shrink-0 rounded-full bg-accent" aria-label="Unread" /> : null}</span><span className="mt-1 block text-sm text-muted-foreground">{notification.message}</span><span className="mt-2 block text-xs text-muted-foreground">{formatDate(notification.created_at)}</span></span>
    </button>;
}