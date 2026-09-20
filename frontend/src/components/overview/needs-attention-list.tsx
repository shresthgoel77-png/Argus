import Link from "next/link";
import { AlertTriangle, ArrowUpRight } from "lucide-react";

import { EmptyState } from "@/components/rm/empty-state";
import { Badge } from "@/components/ui/badge";
import type { FindingResponse } from "@/lib/types/findings";

function displayValue(value: string) {
    return value.replace(/[_-]/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function NeedsAttentionList({ findings, reasons }: { findings: FindingResponse[]; reasons: string[] }) {
    if (!findings.length) {
        return (
            <EmptyState
                icon={<AlertTriangle className="size-6" aria-hidden="true" />}
                title="Nothing needs attention"
                description="High-priority findings will appear here once RepoMedic identifies issues to review."
            />
        );
    }

    return (
        <div className="space-y-3">
            {reasons.length > 0 && (
                <div className="rounded-md border border-amber-500/20 bg-amber-500/5 p-3 text-sm text-amber-900 dark:text-amber-100">
                    <p className="font-medium">Health reasons</p>
                    <ul className="mt-2 list-disc space-y-1 pl-5">
                        {reasons.map((reason) => <li key={reason}>{reason}</li>)}
                    </ul>
                </div>
            )}

            {findings.map((finding) => (
                <Link
                    key={finding.id}
                    href={`/overview/findings?category=${encodeURIComponent(finding.category)}`}
                    className="block rounded-lg border bg-card p-4 transition-colors hover:bg-muted/50"
                >
                    <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 space-y-2">
                            <div className="flex flex-wrap items-center gap-2">
                                <h3 className="truncate font-semibold text-foreground">{finding.title}</h3>
                                <Badge variant="warning" className="capitalize">{displayValue(finding.severity)}</Badge>
                            </div>
                            <p className="line-clamp-2 text-sm text-muted-foreground">{finding.description}</p>
                        </div>
                        <ArrowUpRight className="mt-1 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        <span className="rounded-full border px-2 py-1 capitalize">{displayValue(finding.category)}</span>
                        <span>Priority: {finding.priority ? displayValue(finding.priority) : "Unassigned"}</span>
                    </div>
                </Link>
            ))}
        </div>
    );
}
