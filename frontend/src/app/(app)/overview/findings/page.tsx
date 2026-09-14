"use client";

import * as React from "react";
import { AlertTriangle, ChevronLeft, ChevronRight, Search } from "lucide-react";

import { EmptyState } from "@/components/rm/empty-state";
import { SectionHeading } from "@/components/rm/section-heading";
import { StatusBadge, type FindingStatus, type Severity } from "@/components/rm/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { listFindings } from "@/lib/api/findings";
import { getRepositories } from "@/lib/api/repositories";
import type { FindingListResponse, FindingResponse } from "@/lib/types/findings";
import type { Repository } from "@/lib/types/github";

const PAGE_SIZE = 20;
const STATUSES: FindingStatus[] = ["open", "acknowledged", "resolved", "ignored"];
const SEVERITIES: Severity[] = ["critical", "high", "medium", "low", "info"];
const PRIORITIES = ["critical", "high", "medium", "low"] as const;
const CATEGORIES = ["security", "performance", "code_quality", "maintenance"] as const;

type Filters = { category: string; severity: string; priority: string; status: string };
const initialFilters: Filters = { category: "", severity: "", priority: "", status: "" };

function displayValue(value: string) {
    return value.replace(/[_-]/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDetectedDate(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "Date unavailable" : new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
}

function FindingsSkeleton() {
    return <div className="space-y-3" aria-label="Loading findings" aria-busy="true">{Array.from({ length: 5 }, (_, index) => <Card key={index}><CardContent className="grid gap-4 p-5 md:grid-cols-[minmax(0,1fr)_auto] md:items-center"><div className="space-y-3"><Skeleton className="h-5 w-3/5" /><Skeleton className="h-4 w-2/5" /><Skeleton className="h-4 w-1/3" /></div><div className="flex gap-2"><Skeleton className="h-6 w-16" /><Skeleton className="h-6 w-20" /></div></CardContent></Card>)}</div>;
}

function FindingRow({ finding, repositoryName }: { finding: FindingResponse; repositoryName: string }) {
    const severity = SEVERITIES.includes(finding.severity as Severity) ? finding.severity as Severity : undefined;
    const status = STATUSES.includes(finding.status as FindingStatus) ? finding.status as FindingStatus : undefined;
    return <Card><CardContent className="grid gap-4 p-5 md:grid-cols-[minmax(0,1fr)_auto] md:items-center"><div className="min-w-0 space-y-2"><div className="flex flex-wrap items-center gap-2"><h3 className="truncate font-semibold text-foreground">{finding.title}</h3><Badge variant="secondary" className="capitalize">{finding.category.replace(/[_-]/g, " ")}</Badge></div><div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground"><span>{repositoryName}</span><span>Detected {formatDetectedDate(finding.detected_at)}</span></div></div><div className="flex flex-wrap gap-2 md:justify-end"><StatusBadge severity={severity} label={displayValue(finding.severity)} /><Badge variant={finding.priority === "critical" || finding.priority === "high" ? "warning" : "secondary"} className="capitalize">Priority: {finding.priority ? displayValue(finding.priority) : "Unassigned"}</Badge><StatusBadge status={status} label={displayValue(finding.status)} /></div></CardContent></Card>;
}

function FilterSelect({ label, value, options, onChange }: { label: string; value: string; options: readonly string[]; onChange: (value: string) => void }) {
    return <label className="flex min-w-40 flex-1 flex-col gap-1.5 text-sm font-medium text-foreground">{label}<select value={value} onChange={(event) => onChange(event.target.value)} className="h-10 rounded-md border bg-card px-3 text-sm font-normal shadow-sm outline-none transition focus-visible:ring-2 focus-visible:ring-ring"><option value="">All {label.toLowerCase()}s</option>{options.map((option) => <option key={option} value={option}>{displayValue(option)}</option>)}</select></label>;
}

export default function FindingsPage() {
    const [filters, setFilters] = React.useState<Filters>(initialFilters);
    const [result, setResult] = React.useState<FindingListResponse | null>(null);
    const [repositories, setRepositories] = React.useState<Repository[]>([]);
    const [isLoading, setIsLoading] = React.useState(true);
    const [error, setError] = React.useState(false);
    const [offset, setOffset] = React.useState(0);
    const [retryKey, setRetryKey] = React.useState(0);

    React.useEffect(() => {
        let active = true;
        async function fetchFindings() {
            setIsLoading(true); setError(false);
            const params: Record<string, string> = { limit: PAGE_SIZE.toString(), offset: offset.toString() };
            if (filters.category) params.category = filters.category;
            if (filters.severity) params.severity = filters.severity;
            if (filters.priority) params.priority = filters.priority;
            if (filters.status) params.status_ = filters.status;
            const response = await listFindings(params);
            if (active) { setResult(response); setError(response === null); setIsLoading(false); }
        }
        void fetchFindings();
        return () => { active = false; };
    }, [filters, offset, retryKey]);

    React.useEffect(() => {
        let active = true;
        void getRepositories().then((response) => { if (active && response) setRepositories(response); });
        return () => { active = false; };
    }, [retryKey]);

    const repositoryNames = React.useMemo(() => new Map(repositories.map((repository) => [repository.id, repository.full_name])), [repositories]);
    const updateFilter = (key: keyof Filters, value: string) => { setFilters((current) => ({ ...current, [key]: value })); setOffset(0); };
    const hasPreviousPage = offset > 0;
    const hasNextPage = Boolean(result && offset + result.items.length < result.total);

    return <div className="space-y-6">
        <SectionHeading eyebrow="Review" title="Findings" description="Review code health findings across your connected repositories." />
        <div className="rounded-lg border bg-card p-4 shadow-soft" aria-label="Finding filters"><div className="flex flex-wrap gap-3"><FilterSelect label="Category" value={filters.category} options={CATEGORIES} onChange={(value) => updateFilter("category", value)} /><FilterSelect label="Severity" value={filters.severity} options={SEVERITIES} onChange={(value) => updateFilter("severity", value)} /><FilterSelect label="Priority" value={filters.priority} options={PRIORITIES} onChange={(value) => updateFilter("priority", value)} /><FilterSelect label="Status" value={filters.status} options={STATUSES} onChange={(value) => updateFilter("status", value)} /></div></div>
        {isLoading ? <FindingsSkeleton /> : error ? <EmptyState icon={<AlertTriangle className="size-6" aria-hidden="true" />} title="Findings are temporarily unavailable" description="RepoMedic could not load findings from your workspace. Try again in a moment." action={<Button variant="outline" onClick={() => setRetryKey((key) => key + 1)}>Try again</Button>} /> : result && result.items.length > 0 ? <div className="space-y-3">{result.items.map((finding) => <FindingRow key={finding.id} finding={finding} repositoryName={repositoryNames.get(finding.repository_id) ?? "Repository unavailable"} />)}</div> : <EmptyState icon={<Search className="size-6" aria-hidden="true" />} title="Your findings queue is clear" description="There are no findings matching these filters. New findings will appear here after RepoMedic analyzes a connected repository." />}
        {!isLoading && !error && result ? <div className="flex items-center justify-between gap-4 border-t pt-4"><p className="text-sm text-muted-foreground">{result.total === 0 ? "No findings" : `Showing ${offset + 1}–${Math.min(offset + result.items.length, result.total)} of ${result.total}`}</p><div className="flex gap-2"><Button variant="outline" size="sm" disabled={!hasPreviousPage} onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}><ChevronLeft className="size-4" aria-hidden="true" /> Previous</Button><Button variant="outline" size="sm" disabled={!hasNextPage} onClick={() => setOffset((current) => current + PAGE_SIZE)}>Next <ChevronRight className="size-4" aria-hidden="true" /></Button></div></div> : null}
    </div>;
}
