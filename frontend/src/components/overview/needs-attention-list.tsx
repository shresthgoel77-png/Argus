"use client";

import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FindingIssuePreviewPanel } from "@/components/repositories/finding-issue-preview";
import type { FindingResponse } from "@/lib/types/findings";
import { displayValue, formatDate } from "./presentation";

export function NeedsAttentionList({ findings, reasons, assessmentAvailable = true }: { findings: FindingResponse[]; reasons: string[]; assessmentAvailable?: boolean }) {
    const [active, ...remaining] = findings;
    return (
        <div className="space-y-4 break-words">
            {active ? (
                <article className="space-y-3">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                        <Link href={`/overview/findings/${encodeURIComponent(active.id)}`} className="min-w-0 flex-1 font-semibold hover:text-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">{active.title}<ArrowUpRight className="ml-1 inline size-4" aria-hidden="true" /></Link>
                        <Badge variant={active.severity === "critical" ? "destructive" : active.severity === "high" ? "warning" : "outline"} className="capitalize">{displayValue(active.severity)}</Badge>
                    </div>
                    <p className="text-sm leading-relaxed text-muted-foreground">{active.description}</p>
                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                        <span className="capitalize">Source: {displayValue(active.source)}</span>
                        <span>Detected {formatDate(active.detected_at)}</span>
                        <Link href={`/overview/findings?category=${encodeURIComponent(active.category)}`} className="capitalize underline underline-offset-4">{displayValue(active.category)}</Link>
                        <span className="capitalize">Priority: {active.priority ? displayValue(active.priority) : "Unassigned"}</span>
                    </div>
                    {["open", "acknowledged"].includes(active.status) && <>
                        <FindingIssuePreviewPanel key={active.id} findingId={active.id} triggerLabel="Auto-Generate GitHub Issue" actions={<Button variant="outline" disabled aria-describedby="fix-preview-unavailable" className="h-auto min-h-10 whitespace-normal">Preview Automated Fix</Button>} />
                        <p id="fix-preview-unavailable" className="text-xs text-muted-foreground">Automated fix preview is unavailable: RepoMedic does not currently provide a fix-preview action. Issue generation opens a preview for approval.</p>
                    </>}
                </article>
            ) : (
                <div className="rounded-lg bg-muted/30 p-4 text-sm">
                    <h3 className="font-medium">{assessmentAvailable ? "Nothing needs attention" : "No active findings available"}</h3>
                    <p className="mt-1 text-muted-foreground">{assessmentAvailable ? "High-priority findings will appear here when there are issues to review." : "Assessment coverage is incomplete. An empty findings list does not confirm repository health."}</p>
                </div>
            )}
            {reasons.length > 0 && <details className="text-sm text-muted-foreground"><summary className="cursor-pointer font-medium text-foreground">Health reasons ({reasons.length})</summary><ul className="mt-2 list-disc space-y-1 pl-5">{reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul></details>}
            {remaining.length > 0 && <details className="border-t pt-3 text-sm"><summary className="cursor-pointer font-medium">More findings ({remaining.length})</summary><div className="mt-3 divide-y">{remaining.map((finding) => <Link key={finding.id} href={`/overview/findings/${encodeURIComponent(finding.id)}`} className="flex items-start justify-between gap-3 py-3 text-muted-foreground hover:text-accent"><span>{finding.title}</span><Badge variant="outline" className="capitalize">{finding.severity}</Badge></Link>)}</div></details>}
        </div>
    );
}
