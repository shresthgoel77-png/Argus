"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, ChevronLeft, ChevronRight } from "lucide-react";
import { EmptyState } from "@/components/rm/empty-state";
import { SectionHeading } from "@/components/rm/section-heading";
import { Button } from "@/components/ui/button";
import { NotificationItem, notificationRoute } from "@/components/notifications/notification-item";
import { listNotifications, markAllNotificationsRead, markNotificationRead } from "@/lib/api/notifications";
import type { Notification } from "@/lib/types/notifications";

const PAGE_SIZE = 25;

export default function NotificationsPage() {
    const router = useRouter();
    const [items, setItems] = React.useState<Notification[]>([]);
    const [before, setBefore] = React.useState<string | undefined>();
    const [history, setHistory] = React.useState<string[]>([]);
    const [unreadOnly, setUnreadOnly] = React.useState(false);
    const [loading, setLoading] = React.useState(true);
    const [error, setError] = React.useState(false);
    React.useEffect(() => { let active = true; void listNotifications({ before, unread_only: unreadOnly, limit: PAGE_SIZE }).then((result) => { if (active) { setItems(result ?? []); setError(result === null); setLoading(false); } }); return () => { active = false; }; }, [before, unreadOnly]);
    function resetFilter(next: boolean) { setUnreadOnly(next); setBefore(undefined); setHistory([]); }
    function nextPage() { const cursor = items.at(-1)?.created_at; if (cursor) { setHistory((current) => [...current, before ?? ""]); setBefore(cursor); } }
    function previousPage() { const previous = history.at(-1); if (previous !== undefined) { setHistory((current) => current.slice(0, -1)); setBefore(previous || undefined); } }
    async function handleClick(notification: Notification) { const updated = await markNotificationRead(notification.id); if (updated) setItems((current) => current.map((item) => item.id === updated.id ? updated : item)); const route = notificationRoute(notification); if (route) router.push(route); }
    async function handleMarkAll() { await markAllNotificationsRead(); setItems((current) => current.map((item) => ({ ...item, read_at: item.read_at ?? new Date().toISOString() }))); }
    return <div className="space-y-6"><div className="flex flex-wrap items-end justify-between gap-4"><SectionHeading eyebrow="Workspace" title="Notifications" description="Review events from your connected repositories." /><Button variant="outline" onClick={() => void handleMarkAll()} disabled={!items.some((item) => !item.read_at)}>Mark all as read</Button></div><label className="flex w-fit items-center gap-2 text-sm font-medium"><input type="checkbox" checked={unreadOnly} onChange={(event) => resetFilter(event.target.checked)} />Unread only</label>{loading ? <div className="rounded-lg border bg-card p-8 text-center text-sm text-muted-foreground" aria-busy="true">Loading notifications...</div> : error ? <EmptyState icon={<AlertTriangle className="size-6" />} title="Notifications are temporarily unavailable" description="RepoMedic could not load notifications. Try again in a moment." /> : items.length ? <div className="overflow-hidden rounded-lg border bg-card">{items.map((notification) => <NotificationItem key={notification.id} notification={notification} onClick={() => void handleClick(notification)} />)}</div> : <EmptyState title="No notifications" description={unreadOnly ? "There are no unread notifications." : "New repository events will appear here."} />}{!loading && !error ? <div className="flex justify-end gap-2">{history.length ? <Button variant="outline" size="sm" onClick={previousPage}><ChevronLeft className="size-4" />Previous</Button> : null}{items.length >= PAGE_SIZE ? <Button variant="outline" size="sm" onClick={nextPage}>Next<ChevronRight className="size-4" /></Button> : null}</div> : null}</div>;
}