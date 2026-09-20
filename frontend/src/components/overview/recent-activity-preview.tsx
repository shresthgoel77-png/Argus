import { Clock3 } from "lucide-react";

import { EmptyState } from "@/components/rm/empty-state";
import type { OverviewActivityItem } from "@/lib/types/overview";

function formatDate(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime())
        ? "Date unavailable"
        : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function RecentActivityPreview({ items }: { items: OverviewActivityItem[] }) {
    if (!items.length) {
        return (
            <EmptyState
                icon={<Clock3 className="size-6" aria-hidden="true" />}
                title="No recent activity"
                description="Repository events and review activity will appear here as soon as there is activity to show."
            />
        );
    }

    return (
        <div className="space-y-3">
            {items.map((item) => (
                <div key={`${item.reference_id}-${item.timestamp}`} className="rounded-lg border bg-card p-3">
                    <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                        <span className="rounded-full border px-2 py-1 capitalize">{item.source.replace(/_/g, " ")}</span>
                        <span>{formatDate(item.timestamp)}</span>
                    </div>
                    <p className="mt-2 font-medium text-foreground">{item.title}</p>
                    <p className="mt-1 text-sm text-muted-foreground">{item.summary}</p>
                </div>
            ))}
        </div>
    );
}
