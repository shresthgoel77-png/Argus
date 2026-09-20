import { Activity } from "lucide-react";

import { EmptyState } from "@/components/rm/empty-state";
import type { DashboardOverviewTrends } from "@/lib/types/overview";

const CATEGORY_LABELS: Record<string, string> = {
    ci_cd: "CI/CD",
    dependencies: "Dependencies",
    security: "Security",
    issues: "Issues",
    pull_requests: "Pull Requests",
    code_quality: "Code Quality",
};

export function TrendVisualization({ trends }: { trends: DashboardOverviewTrends | null }) {
    if (!trends) {
        return (
            <EmptyState
                icon={<Activity className="size-6" aria-hidden="true" />}
                title="No trend data yet"
                description="Health and finding velocity will appear once the repository has enough history."
            />
        );
    }

    const deltas = trends.health_trend.category_deltas.slice(0, 5);
    const maxDelta = Math.max(1, ...deltas.map((entry) => Math.abs(entry.delta)));

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Overall delta</span>
                <span className="font-medium text-foreground">{trends.health_trend.overall_delta > 0 ? "+" : ""}{trends.health_trend.overall_delta}</span>
            </div>
            {deltas.length > 0 ? (
                <div className="space-y-3">
                    {deltas.map((entry) => (
                        <div key={entry.category} className="space-y-1.5">
                            <div className="flex items-center justify-between text-sm">
                                <span className="text-muted-foreground">{CATEGORY_LABELS[entry.category] ?? entry.category}</span>
                                <span className={entry.delta >= 0 ? "text-success" : "text-destructive"}>
                                    {entry.delta > 0 ? "+" : ""}{entry.delta}
                                </span>
                            </div>
                            <div className="h-2 overflow-hidden rounded-full bg-muted">
                                <div
                                    className={entry.delta >= 0 ? "h-full rounded-full bg-success" : "h-full rounded-full bg-destructive"}
                                    style={{ width: `${Math.min((Math.abs(entry.delta) / maxDelta) * 100, 100)}%` }}
                                />
                            </div>
                        </div>
                    ))}
                </div>
            ) : (
                <p className="text-sm text-muted-foreground">No trend changes have been recorded yet.</p>
            )}
        </div>
    );
}
