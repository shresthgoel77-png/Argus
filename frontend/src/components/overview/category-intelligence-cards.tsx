import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { DashboardOverviewResponse } from "@/lib/types/overview";
import { categoryCheck, displayValue, HEALTH_CATEGORIES } from "./presentation";

export function CategoryIntelligenceCards({ overview }: { overview: DashboardOverviewResponse }) {
    return (
        <div className="space-y-4"><div className="divide-y">
            {(["code_quality", "security", "dependencies", "ci_cd"] as const).map((category) => {
                const check = categoryCheck(overview, category);
                const excluded = overview.health?.coverage?.excluded_categories[category];
                const status = excluded?.status ?? check?.status;
                const count = overview.finding_category_counts[category];
                const assessed = !excluded && (check ? check.status === "success" : overview.health?.category_scores[category] != null);
                return (
                    <Link key={category} href={`/overview/findings?category=${encodeURIComponent(category)}`} className="group flex items-center justify-between gap-3 py-4 first:pt-0 last:pb-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                        <div className="min-w-0 space-y-1">
                            <p className="text-sm font-medium group-hover:text-accent">{HEALTH_CATEGORIES[category]}</p>
                            <p className="text-xs text-muted-foreground">
                                {count != null && (count > 0 || assessed) ? `${count} open finding${count === 1 ? "" : "s"}` : "Findings unavailable"}
                            </p>
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                            <Badge variant="outline" className="capitalize">{displayValue(status ?? (assessed ? "assessed" : "not assessed"))}</Badge>
                            <ArrowUpRight className="size-3.5 text-muted-foreground" aria-hidden="true" />
                        </div>
                    </Link>
                );
            })}
        </div>
            {(["issues", "pull_requests"] as const).some((category) => overview.finding_category_counts[category] > 0) && <div className="flex flex-wrap gap-3 border-t pt-3 text-xs text-muted-foreground">{(["issues", "pull_requests"] as const).filter((category) => overview.finding_category_counts[category] > 0).map((category) => <Link key={category} href={`/overview/findings?category=${category}`} className="underline underline-offset-4">{HEALTH_CATEGORIES[category]}: {overview.finding_category_counts[category]} open</Link>)}</div>}
        </div>
    );
}
