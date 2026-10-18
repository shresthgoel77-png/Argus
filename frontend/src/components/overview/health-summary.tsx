import { HeartPulse } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { DashboardOverviewResponse } from "@/lib/types/overview";
import { formatDate, scoreVariant } from "./presentation";

export function HealthSummary({ overview, retry }: { overview: DashboardOverviewResponse; retry: React.ReactNode }) {
    const health = overview.health;
    const historical = !health ? overview.last_recorded_health : null;
    const checks = Object.values(overview.monitoring_checks ?? {});
    return (
        <section className="min-w-0 space-y-5 bg-muted/20 p-5 sm:p-6 xl:col-span-3 xl:border-r" aria-labelledby="health-score-heading">
            <h2 id="health-score-heading" className="flex items-center gap-2 text-base font-semibold"><HeartPulse className="size-4 text-accent" aria-hidden="true" />Health score</h2>
            {health ? (
                <div className="space-y-3">
                    <p className="text-xs font-medium text-muted-foreground">Overall health score</p>
                    <p className="text-5xl font-semibold tracking-tight tabular-nums">{health.overall_score}<span className="ml-1 text-base font-normal text-muted-foreground">/100</span></p>
                    <Badge variant={scoreVariant(health.overall_score)}>{health.overall_score >= 80 ? "Healthy" : health.overall_score >= 50 ? "Warning" : "Critical"}</Badge>
                    <p className="text-xs leading-relaxed text-muted-foreground">{health.computed_at ? `Last computed ${formatDate(health.computed_at)}` : "No compute timestamp yet"}</p>
                    <p className="text-xs text-muted-foreground">Snapshot available{health.coverage ? ` · ${health.coverage.assessed_categories.length}/6 categories assessed${health.coverage.assessed_categories.length < 6 ? " · partial coverage" : "."}` : " · coverage unknown"}</p>
                </div>
            ) : historical ? (
                <div className="space-y-3">
                    <p className="text-sm font-medium">Last recorded score</p>
                    <p className="text-4xl font-semibold tabular-nums">{historical.overall_score}<span className="ml-1 text-base font-normal text-muted-foreground">/100</span></p>
                    <Badge variant="outline">Historical</Badge>
                    <p className="text-xs leading-relaxed text-muted-foreground">Recorded {formatDate(historical.computed_at)}. Historical score, not a current assessment. {historical.coverage ? `${historical.coverage.assessed_categories.length}/6 categories assessed at the time.` : "Coverage unknown."}</p>
                    <p className="text-xs text-muted-foreground">Current snapshot unavailable</p>
                </div>
            ) : (
                <div className="space-y-2"><h3 className="font-medium">No health score yet</h3><p className="text-sm text-muted-foreground">No valid health snapshot is available for this repository.</p></div>
            )}
            <div className="border-t pt-4 text-xs text-muted-foreground">
                {checks.length ? <p>{checks.filter((check) => check.status === "failed").length} failed checks · {checks.filter((check) => ["unavailable", "blocked"].includes(check.status)).length} unavailable / blocked checks{checks.some((check) => check.status === "skipped") ? ` · ${checks.filter((check) => check.status === "skipped").length} skipped` : ""}</p> : <p>Check counts unavailable</p>}
            </div>
            {retry}
        </section>
    );
}

export function AssessmentRetry({ onClick, pending, disabled }: { onClick: () => void; pending: boolean; disabled: boolean }) {
    return <Button variant="outline" size="sm" onClick={onClick} loading={pending} disabled={disabled} className="max-w-full">{pending ? "Checking…" : "Retry assessment"}</Button>;
}
