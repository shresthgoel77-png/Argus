import type { DashboardOverviewResponse } from "@/lib/types/overview";
import type { HealthCategory } from "@/lib/types/health";
import { Badge } from "@/components/ui/badge";
import { categoryCheck, displayValue, HEALTH_CATEGORIES, signedDelta } from "./presentation";

export function TrendVisualization({ overview }: { overview: DashboardOverviewResponse }) {
    const { health, trends } = overview;
    return (
        <div className="space-y-4">
            {trends ? (
                <div className="flex items-center justify-between gap-2 rounded-md bg-muted/40 p-3 text-sm">
                    <span className="text-muted-foreground">Overall delta <span className="text-xs">· {trends.window_days} days</span></span>
                    <span className="font-semibold tabular-nums">{signedDelta(trends.health_trend.overall_delta)}</span>
                </div>
            ) : <p className="text-sm text-muted-foreground">No trend data yet</p>}
            {(Object.entries(HEALTH_CATEGORIES) as [HealthCategory, string][]).filter(([category]) =>
                health?.category_scores[category] != null || health?.coverage?.excluded_categories[category] || categoryCheck(overview, category) || trends?.health_trend.category_deltas.some((entry) => entry.category === category)
            ).map(([category, label]) => {
                const excluded = health?.coverage?.excluded_categories[category];
                const score = excluded ? undefined : health?.category_scores[category];
                const delta = trends?.health_trend.category_deltas.find((entry) => entry.category === category)?.delta;
                return (
                    <div key={category} className="space-y-1.5">
                        <div className="flex flex-wrap items-center justify-between gap-1 text-xs">
                            <span className="font-medium">{label}</span>
                            <div className="flex flex-wrap items-center gap-2 text-muted-foreground">
                                {score != null ? <span>Score <strong className="font-medium tabular-nums text-foreground">{score}</strong></span> : <Badge variant="outline" className="capitalize">{displayValue(excluded?.status ?? categoryCheck(overview, category)?.status ?? "unavailable")}</Badge>}
                                {delta != null && <span>Δ <span className="tabular-nums text-foreground">{signedDelta(delta)}</span></span>}
                            </div>
                        </div>
                        {score != null && (
                            <div role="progressbar" aria-label={`${label} score`} aria-valuenow={score} aria-valuemin={0} aria-valuemax={100} className="h-1.5 overflow-hidden rounded-full bg-muted">
                                <div className={`h-full rounded-full ${score >= 80 ? "bg-success" : score >= 50 ? "bg-warning" : "bg-destructive"}`} style={{ width: `${Math.max(0, Math.min(score, 100))}%` }} />
                            </div>
                        )}
                    </div>
                );
            })}
        </div>
    );
}
