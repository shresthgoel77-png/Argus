import type { DashboardOverviewResponse } from "@/lib/types/overview";
import type { HealthCategory } from "@/lib/types/health";

export const HEALTH_CATEGORIES: Record<HealthCategory, string> = {
    code_quality: "Code Quality", security: "Security", dependencies: "Dependencies",
    ci_cd: "CI/CD", issues: "Issues", pull_requests: "Pull Requests",
};

const CHECK_NAMES: Record<HealthCategory, string> = {
    code_quality: "code_quality", security: "security", dependencies: "dependency",
    ci_cd: "ci_cd", issues: "stale_issues", pull_requests: "stale_prs",
};

export function categoryCheck(overview: DashboardOverviewResponse, category: HealthCategory) {
    return overview.monitoring_checks?.[CHECK_NAMES[category]] ?? overview.monitoring_checks?.[category];
}

export function displayValue(value: string) {
    return value.replace(/[_-]/g, " ");
}

export function formatDate(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "Date unavailable" : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function scoreVariant(score: number) {
    return score >= 80 ? "success" : score >= 50 ? "warning" : "destructive";
}

export function signedDelta(delta: number) {
    return `${delta > 0 ? "+" : ""}${delta}`;
}
