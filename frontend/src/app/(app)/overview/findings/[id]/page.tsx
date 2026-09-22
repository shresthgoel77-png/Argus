"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { EmptyState } from "@/components/rm/empty-state";
import { SectionHeading } from "@/components/rm/section-heading";
import { StatusBadge, type Severity } from "@/components/rm/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { getFinding } from "@/lib/api/findings";
import type { FindingResponse } from "@/lib/types/findings";

type PageProps = { params: Promise<{ id: string }> };

export default function FindingDetailPage({ params }: PageProps) {
    const { id } = React.use(params);
    const router = useRouter();
    const [finding, setFinding] = React.useState<FindingResponse | null>(null);
    const [loading, setLoading] = React.useState(true);
    React.useEffect(() => { let active = true; void getFinding(id).then((result) => { if (active) { setFinding(result); setLoading(false); } }); return () => { active = false; }; }, [id]);
    if (loading) return <div className="p-8 text-center text-sm text-muted-foreground" aria-busy="true">Loading finding...</div>;
    if (!finding) return <EmptyState title="Finding not found" description="This finding may have been removed or is no longer available." action={<Button onClick={() => router.push("/overview/findings")}>Back to Findings</Button>} />;
    const severity = ["critical", "high", "medium", "low", "info"].includes(finding.severity) ? finding.severity as Severity : undefined;
    return <div className="space-y-6"><Button variant="ghost" size="sm" onClick={() => router.push("/overview/findings")}><ChevronLeft className="size-4" />Back to Findings</Button><SectionHeading eyebrow="Finding" title={finding.title} description={finding.description} /><Card><CardContent className="space-y-4 p-6"><div className="flex flex-wrap gap-2"><StatusBadge severity={severity} label={finding.severity} /><Badge variant="secondary" className="capitalize">{finding.category.replace(/[_-]/g, " ")}</Badge><Badge variant="outline" className="capitalize">{finding.status}</Badge></div><p className="text-sm leading-6 text-muted-foreground">{finding.description}</p></CardContent></Card></div>;
}