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
import { StatCard } from "@/components/rm/stat-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getDashboardOverview, getRepositories } from "@/lib/api/repositories";
import type { Repository } from "@/lib/types/github";
import type { DashboardOverviewResponse } from "@/lib/types/overview";

function getScoreVariant(score: number) {
    if (score >= 80) return "success";
    if (score >= 50) return "warning";
    return "destructive";
}

export default function AppOverviewPage() {
    const [repositories, setRepositories] = React.useState<Repository[]>([]);
    const [selectedRepositoryId, setSelectedRepositoryId] = React.useState<string | null>(null);
    const [overview, setOverview] = React.useState<DashboardOverviewResponse | null>(null);
    const [isLoading, setIsLoading] = React.useState(true);
    const [error, setError] = React.useState<string | null>(null);

    React.useEffect(() => {
        let active = true;

        async function loadOverview() {
            setIsLoading(true);
            setError(null);

            const nextRepositories = await getRepositories();
            if (!active) return;

            if (!nextRepositories || nextRepositories.length === 0) {
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
            setRepositories(nextRepositories);
            setSelectedRepositoryId(firstRepository.id);

            const nextOverview = await getDashboardOverview(firstRepository.id);
            if (!active) return;
            setOverview(nextOverview);
            setError(nextOverview ? null : "The dashboard could not be loaded right now.");
            setIsLoading(false);
        }

        void loadOverview();
        return () => {
            active = false;
        };
    }, []);

    const selectedRepository = repositories.find((repository) => repository.id === selectedRepositoryId) ?? repositories[0] ?? null;

    if (isLoading) {
        return (
            <div className="space-y-6">
                <SectionHeading
                    eyebrow="Workspace"
                    title="Overview"
                    description="A health check across your connected repositories and engineering activity."
                />
                <div className="grid gap-4 xl:grid-cols-2">
                    {Array.from({ length: 4 }).map((_, index) => (
                        <div key={index} className="h-40 animate-pulse rounded-lg border bg-card" />
                    ))}
                </div>
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
                <EmptyState
                    icon={<ShieldAlert className="size-6" aria-hidden="true" />}
                    title="Overview is temporarily unavailable"
                    description={error ?? "RepoMedic could not load the dashboard for this repository right now."}
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
        <div className="space-y-6">
            <SectionHeading
                eyebrow="Workspace"
                title="Overview"
                description={`Health check for ${selectedRepository.full_name}.`}
            />

            <div className="grid gap-4 xl:grid-cols-2">
                <section className="space-y-3" aria-labelledby="health-score-heading">
                    <h2 id="health-score-heading" className="text-lg font-semibold tracking-tight">Health score</h2>
                    {overview.health ? (
                        <div className="space-y-3">
                            <StatCard
                                className="border-primary/20 bg-muted/20"
                                label="Overall health score"
                                value={overview.health.overall_score}
                                trend={
                                    <Badge variant={getScoreVariant(overview.health.overall_score)}>
                                        {overview.health.overall_score >= 80 ? "Healthy" : overview.health.overall_score >= 50 ? "Warning" : "Critical"}
                                    </Badge>
                                }
                                description={overview.health.computed_at ? `Last computed ${new Date(overview.health.computed_at).toLocaleString()}` : "No compute timestamp yet"}
                            />
                            <div className="grid gap-3 sm:grid-cols-2">
                                {Object.entries(overview.health.category_scores).map(([category, score]) => (
                                    <div key={category} className="rounded-lg border bg-card p-4">
                                        <p className="text-sm text-muted-foreground">{category.replace(/_/g, " ")}</p>
                                        <div className="mt-2 flex items-center justify-between gap-2">
                                            <span className="text-2xl font-semibold tracking-tight">{score}</span>
                                            <Badge variant={getScoreVariant(score)}>{score >= 80 ? "Good" : score >= 50 ? "Fair" : "Poor"}</Badge>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ) : (
                        <EmptyState
                            icon={<HeartPulse className="size-6" aria-hidden="true" />}
                            title="No health score yet"
                            description="This repository has not produced a health snapshot yet."
                        />
                    )}
                </section>

                <section className="space-y-3" aria-labelledby="attention-heading">
                    <h2 id="attention-heading" className="text-lg font-semibold tracking-tight">Needs attention</h2>
                    <NeedsAttentionList findings={overview.needs_attention.findings} reasons={overview.needs_attention.reasons} />
                </section>

                <section className="space-y-3" aria-labelledby="category-intelligence-heading">
                    <h2 id="category-intelligence-heading" className="text-lg font-semibold tracking-tight">Category intelligence</h2>
                    <CategoryIntelligenceCards counts={overview.finding_category_counts} />
                </section>

                <section className="space-y-3" aria-labelledby="recent-activity-heading">
                    <h2 id="recent-activity-heading" className="text-lg font-semibold tracking-tight">Recent activity</h2>
                    <RecentActivityPreview items={overview.activity_feed} />
                </section>
            </div>

            <div className="grid gap-4 xl:grid-cols-2">
                <section className="space-y-3" aria-labelledby="trend-overview-heading">
                    <h2 id="trend-overview-heading" className="text-lg font-semibold tracking-tight">Trend overview</h2>
                    <div className="rounded-lg border bg-card p-4">
                        <TrendVisualization trends={overview.trends ?? null} />
                    </div>
                </section>

                <section className="space-y-3" aria-labelledby="ai-summary-heading">
                    <h2 id="ai-summary-heading" className="text-lg font-semibold tracking-tight">AI summary</h2>
                    <RepositoryAISummaryPanel repositoryId={selectedRepository.id} />
                </section>
            </div>
        </div>
    );
}
