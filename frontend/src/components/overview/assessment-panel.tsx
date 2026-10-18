import type { DashboardOverviewResponse } from "@/lib/types/overview";
import { Badge } from "@/components/ui/badge";
import { displayValue, formatDate } from "./presentation";

export function AssessmentPanel({ overview, monitoringStatus, retry }: { overview: DashboardOverviewResponse; monitoringStatus: string; retry: React.ReactNode }) {
    const checks = Object.entries(overview.monitoring_checks ?? {});
    return (
        <section className="min-w-0 space-y-4 rounded-xl border bg-card p-5 sm:p-6" aria-label="Assessment status">
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="space-y-1">
                    <h2 className="text-base font-semibold">Assessment status: {displayValue(monitoringStatus)}</h2>
                    <p className="text-xs text-muted-foreground">{overview.last_monitoring_at ? `Last checked ${formatDate(overview.last_monitoring_at)}` : "No assessment has completed yet"}</p>
                </div>
                {retry}
            </div>
            <div className="space-y-1 text-sm text-muted-foreground">
                <p>Health uses successfully assessed categories. Excluded categories do not affect the score.</p>
                {!overview.health && <p>A current health score is unavailable until valid assessment results are available.</p>}
                {Object.entries(overview.health?.coverage?.excluded_categories ?? {}).map(([category, check]) => (
                    <p key={category}>Excluded {displayValue(category)}: {check.status} — {check.reason}</p>
                ))}
            </div>
            {checks.length ? (
                <dl className="grid gap-3 border-t pt-4 sm:grid-cols-2 xl:grid-cols-3">
                    {checks.map(([name, check]) => (
                        <div key={name} className="min-w-0 rounded-lg border bg-muted/10 p-3">
                            <dt className="flex flex-wrap items-center justify-between gap-2 text-sm font-medium capitalize">{displayValue(name)}<Badge variant={check.status === "failed" ? "destructive" : "outline"}>{displayValue(check.status)}</Badge></dt>
                            <dd className="mt-2 space-y-1 text-xs leading-relaxed text-muted-foreground">
                                <p>{check.checked_at ? `Checked ${formatDate(check.checked_at)}` : "No check timestamp available"}</p>
                                {check.error_message && !Object.values(overview.health?.coverage?.excluded_categories ?? {}).some((excluded) => excluded.reason === check.error_message) && <p className="break-words">{check.error_message}</p>}
                            </dd>
                        </div>
                    ))}
                </dl>
            ) : <p className="text-sm text-muted-foreground">Individual check statuses are unavailable.</p>}
        </section>
    );
}
