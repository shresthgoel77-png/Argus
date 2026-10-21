"use client";

import * as React from "react";
import { HeartPulse, ShieldAlert } from "lucide-react";

import { NeedsAttentionList } from "@/components/overview/needs-attention-list";
import { CategoryIntelligenceCards } from "@/components/overview/category-intelligence-cards";
import { RecentActivityPreview } from "@/components/overview/recent-activity-preview";
import { RepositoryAISummaryPanel } from "@/components/overview/repository-ai-summary-panel";
import { TrendVisualization } from "@/components/overview/trend-visualization";
import { EmptyState } from "@/components/rm/empty-state";
import { SectionHeading } from "@/components/rm/section-heading";
import { Button } from "@/components/ui/button";
import { AssessmentPanel } from "@/components/overview/assessment-panel";
import { HealthSummary, AssessmentRetry } from "@/components/overview/health-summary";
import { getDashboardOverview, getRepositories, refreshRepository } from "@/lib/api/repositories";
import type { Repository } from "@/lib/types/github";
import type { DashboardOverviewResponse } from "@/lib/types/overview";

function OverviewContent({ overview, repository, monitoringStatus, onRefresh }: {
    overview: DashboardOverviewResponse; repository: Repository; monitoringStatus: string; onRefresh: () => void;
}) {
    const [pending, setPending] = React.useState(false);
    const [retryError, setRetryError] = React.useState<string | null>(null);
    const mounted = React.useRef(false);
    React.useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);

    async function retryAssessment() {
        if (pending) return;
        setPending(true);
        setRetryError(null);
        try {
            const result = await refreshRepository(repository.id);
            if (!mounted.current) return;
            if (result) onRefresh();
            else setRetryError("The assessment could not be retried. Try again in a moment.");
        } finally {
            if (mounted.current) setPending(false);
        }
    }
    const retry = <AssessmentRetry onClick={() => void retryAssessment()} pending={pending} disabled={!repository.monitoring_enabled || monitoringStatus === "running"} />;

    return <>
        {retryError && <p role="alert" className="rounded-lg border border-destructive/20 p-3 text-sm text-destructive">{retryError}</p>}
        {!repository.monitoring_enabled && <p className="text-sm text-muted-foreground">Monitoring is disabled for this repository. Enable it in repository settings to retry assessments.</p>}
        <div className="grid min-w-0 overflow-hidden rounded-xl border bg-card shadow-soft xl:grid-cols-12" aria-label="Repository health and triage">
            <HealthSummary overview={overview} retry={retry} />
            <div className="min-w-0 border-t xl:col-span-9 xl:border-t-0">
                <RepositoryAISummaryPanel repositoryId={repository.id} embedded />
                <section className="min-w-0 space-y-4 border-t p-5 sm:p-6" aria-labelledby="attention-heading">
                    <h2 id="attention-heading" className="text-base font-semibold">Needs attention</h2>
                    <NeedsAttentionList findings={overview.needs_attention.findings} reasons={overview.needs_attention.reasons} assessmentAvailable={!!overview.health} />
                </section>
            </div>
        </div>
        <div className="grid min-w-0 items-start gap-5 xl:grid-cols-3">
            <section className="min-w-0 space-y-5 rounded-xl border bg-card p-5 sm:p-6 xl:h-full" aria-labelledby="category-intelligence-heading">
                <h2 id="category-intelligence-heading" className="text-base font-semibold">Category intelligence</h2>
                <CategoryIntelligenceCards overview={overview} />
            </section>
            <section className="min-w-0 space-y-5 rounded-xl border bg-card p-5 sm:p-6 xl:h-full" aria-labelledby="trend-overview-heading">
                <h2 id="trend-overview-heading" className="text-base font-semibold">Trend overview</h2>
                <TrendVisualization overview={overview} />
            </section>
            <section className="min-w-0 space-y-5 rounded-xl border bg-card p-5 sm:p-6 xl:h-full" aria-labelledby="recent-activity-heading">
                <h2 id="recent-activity-heading" className="text-base font-semibold">Recent activity</h2>
                <RecentActivityPreview items={overview.activity_feed} />
            </section>
        </div>
        <AssessmentPanel overview={overview} monitoringStatus={monitoringStatus} retry={retry} />
    </>;
}

export default function AppOverviewPage() {
    const [repositories, setRepositories] = React.useState<Repository[]>([]);
    const [selectedRepositoryId, setSelectedRepositoryId] = React.useState<string | null>(null);
    const [overview, setOverview] = React.useState<DashboardOverviewResponse | null>(null);
    const [isLoading, setIsLoading] = React.useState(true);
    const [error, setError] = React.useState<string | null>(null);
    const [refreshKey, setRefreshKey] = React.useState(0);

    React.useEffect(() => {
        let active = true;

        async function loadRepositories() {
            const nextRepositories = await getRepositories();
            if (!active) return;

            if (nextRepositories === null) {
                setError("Repositories could not be loaded right now.");
                setIsLoading(false);
                return;
            }
            setRepositories(nextRepositories);
            if (nextRepositories.length === 0) {
                setRepositories([]);
                setSelectedRepositoryId(null);
                setOverview(null);
                setIsLoading(false);
                return;
            }

            const orderedRepositories = nextRepositories.filter((repo) => repo.monitoring_enabled).length
                ? nextRepositories.filter((repo) => repo.monitoring_enabled)
                : nextRepositories;

            const firstRepository = orderedRepositories[0];
            setSelectedRepositoryId(firstRepository.id);
        }

        void loadRepositories();
        return () => {
            active = false;
        };
    }, []);

    React.useEffect(() => {
        if (!selectedRepositoryId) return;
        const repositoryId = selectedRepositoryId;
        let active = true;
        async function loadOverview() {
            setIsLoading(true);
            setError(null);
            setOverview(null);
            const nextOverview = await getDashboardOverview(repositoryId);
            if (!active) return;
            setOverview(nextOverview);
            setError(nextOverview ? null : "The dashboard could not be loaded right now.");
            setIsLoading(false);
        }
        void loadOverview();
        return () => {
            active = false;
        };
    }, [selectedRepositoryId, refreshKey]);

    const selectedRepository = repositories.find((repository) => repository.id === selectedRepositoryId) ?? null;
    const monitoringStatus = overview?.monitoring_status ?? selectedRepository?.monitoring_status ?? "unknown";

    const repositorySelector = repositories.length > 0 ? (
        <label className="flex w-full min-w-0 flex-col gap-2 text-sm sm:w-auto sm:max-w-sm">
            <span className="font-medium">Repository</span>
            <select
                aria-label="Select repository"
                className="h-10 w-full min-w-0 rounded-md border bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                value={selectedRepositoryId ?? ""}
                onChange={(event) => { setIsLoading(true); setOverview(null); setSelectedRepositoryId(event.target.value); }}
            >
                {repositories.map((repository) => (
                    <option key={repository.id} value={repository.id}>
                        {repository.full_name}{repository.monitoring_enabled ? "" : " (monitoring disabled)"}
                    </option>
                ))}
            </select>
        </label>
    ) : null;

    if (isLoading) {
        return (
            <div className="space-y-6">
                <SectionHeading
                    eyebrow="Workspace"
                    title="Overview"
                    description="A health check across your connected repositories and engineering activity."
                />
                {repositorySelector}
                <div className="grid gap-4 xl:grid-cols-3" aria-label="Loading overview" aria-busy="true">
                    {Array.from({ length: 4 }).map((_, index) => (
                        <div key={index} className="h-40 animate-pulse rounded-lg border bg-card" />
                    ))}
                </div>
            </div>
        );
    }

    if (error && !selectedRepository && repositories.length === 0) {
        return (
            <div className="space-y-6">
                <SectionHeading eyebrow="Workspace" title="Overview" description="A health check across your connected repositories and engineering activity." />
                <EmptyState icon={<ShieldAlert className="size-6" aria-hidden="true" />} title="Repositories are unavailable" description={error} />
            </div>
        );
    }

    if (!selectedRepository) {
        return (
            <div className="space-y-6">
                <SectionHeading
                    eyebrow="Workspace"
                    title="Overview"
                    description="A health check across your connected repositories and engineering activity."
                />
                {repositorySelector}
                <EmptyState
                    icon={<HeartPulse className="size-6" aria-hidden="true" />}
                    title="No connected repositories yet"
                    description="Connect a GitHub repository to start measuring health, issues, and AI-generated context."
                />
            </div>
        );
    }

    if (error || !overview) {
        return (
            <div className="space-y-6">
                <SectionHeading
                    eyebrow="Workspace"
                    title="Overview"
                    description="A health check across your connected repositories and engineering activity."
                />
                {repositorySelector}
                <EmptyState
                    icon={<ShieldAlert className="size-6" aria-hidden="true" />}
                    title="Overview is temporarily unavailable"
                    description={error ?? "Argus could not load the dashboard for this repository right now."}
                    action={
                        <Button variant="outline" onClick={() => window.location.reload()}>
                            Try again
                        </Button>
                    }
                />
            </div>
        );
    }

    return (
        <div className="min-w-0 space-y-6">
            <header className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
                <SectionHeading eyebrow="Workspace" title="Overview" description={`Health check for ${selectedRepository.full_name}.`} className="min-w-0 break-words" />
                {repositorySelector}
            </header>
            <OverviewContent key={selectedRepository.id} overview={overview} repository={selectedRepository} monitoringStatus={monitoringStatus} onRefresh={() => setRefreshKey((key) => key + 1)} />
        </div>
    );
}
