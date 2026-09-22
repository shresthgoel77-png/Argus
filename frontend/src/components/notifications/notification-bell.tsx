"use client";

import * as React from "react";
import Link from "next/link";
import { Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import { NotificationItem, notificationRoute } from "./notification-item";
import { getUnreadNotificationCount, listNotifications, markNotificationRead } from "@/lib/api/notifications";
import type { Notification } from "@/lib/types/notifications";

export function NotificationBell() {
    const [count, setCount] = React.useState(0);
    const [items, setItems] = React.useState<Notification[]>([]);
    const [open, setOpen] = React.useState(false);
    const container = React.useRef<HTMLDivElement>(null);
    React.useEffect(() => { void getUnreadNotificationCount().then((result) => { if (result) setCount(result.count); }); }, []);
    React.useEffect(() => { const close = (event: MouseEvent) => { if (container.current && !container.current.contains(event.target as Node)) setOpen(false); }; document.addEventListener("mousedown", close); return () => document.removeEventListener("mousedown", close); }, []);
    async function toggle() { const nextOpen = !open; setOpen(nextOpen); if (nextOpen) { const result = await listNotifications({ limit: 5 }); if (result) setItems(result); } }
    async function handleClick(notification: Notification) { const updated = await markNotificationRead(notification.id); if (updated) { setItems((current) => current.map((item) => item.id === updated.id ? updated : item)); setCount((current) => Math.max(0, current - (notification.read_at ? 0 : 1))); } const route = notificationRoute(notification); if (route) window.location.assign(route); }
    return <div ref={container} className="relative"><Button variant="ghost" size="icon" aria-label={count ? `Notifications, ${count} unread` : "Notifications"} aria-expanded={open} onClick={() => void toggle()}><Bell className="size-5" aria-hidden="true" />{count > 0 ? <span className="absolute -right-0.5 -top-0.5 flex min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-bold leading-4 text-destructive-foreground">{count > 99 ? "99+" : count}</span> : null}</Button>{open ? <div className="absolute right-0 top-11 z-50 w-[min(22rem,calc(100vw-2rem))] overflow-hidden rounded-lg border bg-card shadow-lg"><div className="flex items-center justify-between border-b px-4 py-3"><h2 className="font-semibold">Notifications</h2><Link href="/overview/notifications" className="text-sm text-accent hover:underline" onClick={() => setOpen(false)}>View all</Link></div>{items.length ? items.map((notification) => <NotificationItem key={notification.id} notification={notification} onClick={() => void handleClick(notification)} />) : <p className="p-6 text-center text-sm text-muted-foreground">You&apos;re all caught up.</p>}</div> : null}</div>;
}