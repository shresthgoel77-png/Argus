import Link from "next/link";
import { Layers3 } from "lucide-react";

import { EmptyState } from "@/components/rm/empty-state";
import { Card, CardContent } from "@/components/ui/card";

const CATEGORY_LABELS: Record<string, string> = {
    ci_cd: "CI/CD",
    dependencies: "Dependencies",
    security: "Security",
    issues: "Issues",
    pull_requests: "Pull Requests",
    code_quality: "Code Quality",
};

export function CategoryIntelligenceCards({ counts }: { counts: Record<string, number> }) {
    const entries = Object.entries(CATEGORY_LABELS)
        .map(([category, label]) => ({ category, label, count: counts[category] ?? 0 }))
        .filter((entry) => entry.count > 0);

    if (!entries.length) {
        return (
            <EmptyState
                icon={<Layers3 className="size-6" aria-hidden="true" />}
                title="No category signals yet"
                description="RepoMedic will surface category breakdowns as findings appear."
            />
        );
    }

    return (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-2">
            {entries.map((entry) => (
                <Link key={entry.category} href={`/overview/findings?category=${encodeURIComponent(entry.category)}`} className="block">
                    <Card className="h-full transition-colors hover:bg-muted/50">
                        <CardContent className="flex items-center justify-between gap-4 pt-5">
                            <div>
                                <p className="text-sm text-muted-foreground">{entry.label}</p>
                                <p className="mt-1 text-2xl font-semibold tracking-tight text-foreground">{entry.count}</p>
                            </div>
                            <div className="rounded-full bg-accent/10 px-2 py-1 text-xs font-medium text-accent">Open</div>
                        </CardContent>
                    </Card>
                </Link>
            ))}
        </div>
    );
}
