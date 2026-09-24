"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { ChevronLeft, Loader2, Play, RefreshCw } from "lucide-react";

import { EmptyState } from "@/components/rm/empty-state";
import { SectionHeading } from "@/components/rm/section-heading";
import { StatCard } from "@/components/rm/stat-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
    getRepositoryHealth,
    getRepositoryHealthHistory,
    triggerHealthRun
} from "@/lib/api/health";
import { getRepositories, refreshRepository } from "@/lib/api/repositories";
import type {
    RepositoryHealthSnapshot,
    HealthSnapshotHistoryItem,
    HealthCategory
} from "@/lib/types/health";
import type { Repository } from "@/lib/types/github";

type PageProps = {
    params: Promise<{ id: string }>;
};

const CATEGORIES: Record<HealthCategory, string> = {
    ci_cd: "CI/CD",
    dependencies: "Dependencies",
    security: "Security",
    issues: "Issues",
    pull_requests: "Pull Requests",
    code_quality: "Code Quality",
};

function getScoreVariant(score: number) {
    if (score >= 80) return "success";
    if (score >= 50) return "warning";
    return "destructive";
}

function formatDate(dateStr: string) {
    const d = new Date(dateStr);
    return Number.isNaN(d.getTime()) ? "Date unavailable" : new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
    }).format(d);
}

export default function RepositoryHealthPage(props: PageProps) {
    const params = React.use(props.params);
    const { id } = params;
    const router = useRouter();

    const [repository, setRepository] = React.useState<Repository | null>(null);
    const [health, setHealth] = React.useState<RepositoryHealthSnapshot | null>(null);
    const [history, setHistory] = React.useState<HealthSnapshotHistoryItem[]>([]);
    const [isLoading, setIsLoading] = React.useState(true);
    const [isTriggering, setIsTriggering] = React.useState(false);
    const [isRefreshing, setIsRefreshing] = React.useState(false);
    const [refreshKey, setRefreshKey] = React.useState(0);

    React.useEffect(() => {
        let active = true;
        async function loadData() {
            setIsLoading(true);
            try {
                const [reposRes, healthRes, historyRes] = await Promise.all([
                    getRepositories(),
                    getRepositoryHealth(id),
                    getRepositoryHealthHistory(id, { limit: "10" }),
                ]);

                if (active) {
                    const repo = reposRes?.find((r) => r.id.toString() === id);
                    if (repo) setRepository(repo);
                    if (healthRes) setHealth(healthRes);
                    if (historyRes?.items) setHistory(historyRes.items);
                }
            } finally {
                if (active) {
                    setIsLoading(false);
                }
            }
        }
        loadData();
        return () => {
            active = false;
        };
    }, [id, refreshKey]);

    const handleTrigger = async () => {
        setIsTriggering(true);
        try {
            await triggerHealthRun(id);
            setRefreshKey((k) => k + 1); // Refresh data on success
        } finally {
            setIsTriggering(false);
        }
    };

    const handleRefresh = async () => {
        setIsRefreshing(true);
        try {
            await refreshRepository(id);
            setRefreshKey((k) => k + 1); // Refresh data on success
        } finally {
            setIsRefreshing(false);
        }
    };

    if (isLoading) {
        return (
            <div className="space-y-6">
                <Skeleton className="h-10 w-1/3" />
                <Skeleton className="h-4 w-1/4" />
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {Array.from({ length: 6 }).map((_, i) => (
                        <Skeleton key={i} className="h-24 w-full" />
                    ))}
                </div>
            </div>
        );
    }

    if (!repository) {
        return (
            <EmptyState
                title="Repository not found"
                description="The repository you're looking for doesn't exist or isn't connected."
                action={
                    <Button onClick={() => router.push("/overview/repositories")}>
                        Back to Repositories
                    </Button>
                }
            />
        );
    }

    return (
        <div className="space-y-8">
            <div className="flex items-center justify-between gap-4 flex-wrap">
                <div className="flex flex-col gap-2">
                    <Button variant="ghost" size="sm" onClick={() => router.push("/overview/repositories")} className="-ml-3 text-muted-foreground">
                        <ChevronLeft className="size-4 mr-1" />
                        Back to Repositories
                    </Button>
                    <SectionHeading
                        eyebrow="Repository Health"
                        title={repository.full_name}
                        description="View deep health analytics and scores."
                    />
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="outline" onClick={handleRefresh} disabled={isRefreshing || !repository.monitoring_enabled}>
                        {isRefreshing ? (
                            <Loader2 className="size-4 mr-2 animate-spin" />
                        ) : (
                            <RefreshCw className="size-4 mr-2" />
                        )}
                        {isRefreshing ? "Refreshing..." : "Refresh Now"}
                    </Button>
                    <Button onClick={handleTrigger} disabled={isTriggering || !repository.monitoring_enabled}>
                        {isTriggering ? (
                            <Loader2 className="size-4 mr-2 animate-spin" />
                        ) : (
                            <Play className="size-4 mr-2" />
                        )}
                        {isTriggering ? "Running..." : "Run Health Check"}
                    </Button>
                </div>
            </div>

            {!repository.monitoring_enabled ? (
                <EmptyState
                    title="Monitoring Disabled"
                    description="Enable monitoring for this repository to view its health data."
                    action={
                        <Button onClick={() => router.push("/overview/repositories")}>
                            Manage Monitoring
                        </Button>
                    }
                />
            ) : !health ? (
                <EmptyState
                    title="Not yet checked"
                    description="This repository has not been checked yet. Run a health check to get started."
                    action={
                        <Button onClick={handleTrigger} disabled={isTriggering}>
                            {isTriggering && <Loader2 className="size-4 mr-2 animate-spin" />}
                            Run Health Check
                        </Button>
                    }
                />
            ) : (
                <div className="space-y-8">
                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                        <StatCard
                            className="lg:col-span-3 bg-muted/20 border-primary/20"
                            label="Overall Health Score"
                            value={health.overall_score}
                            trend={
                                <Badge variant={getScoreVariant(health.overall_score)}>
                                    {health.overall_score >= 80 ? 'Healthy' : health.overall_score >= 50 ? 'Warning' : 'Critical'}
                                </Badge>
                            }
                            description={`Last computed at ${formatDate(health.computed_at)}`}
                        />

                        {(Object.entries(health.category_scores) as [HealthCategory, number][]).map(([cat, score]) => (
                            <StatCard
                                key={cat}
                                label={CATEGORIES[cat] || cat}
                                value={score}
                                trend={
                                    <Badge variant={getScoreVariant(score)} className="text-[10px] px-1 py-0 h-4">
                                        {score >= 80 ? 'Good' : score >= 50 ? 'Fair' : 'Poor'}
                                    </Badge>
                                }
                            />
                        ))}
                    </div>

                    <div className="grid gap-6 md:grid-cols-2">
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-lg">Latest Reasons</CardTitle>
                            </CardHeader>
                            <CardContent>
                                {health.reasons.length > 0 ? (
                                    <ul className="space-y-2 list-disc pl-5 text-sm text-muted-foreground marker:text-muted">
                                        {health.reasons.map((reason, i) => (
                                            <li key={i}>{reason}</li>
                                        ))}
                                    </ul>
                                ) : (
                                    <p className="text-sm text-muted-foreground">No specific reasons provided.</p>
                                )}
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader>
                                <CardTitle className="text-lg">Health Trend</CardTitle>
                            </CardHeader>
                            <CardContent>
                                {history.length > 0 ? (
                                    <div className="space-y-4">
                                        {history.map((item, index) => (
                                            <div key={index} className="flex items-center justify-between gap-4 text-sm border-b last:border-0 pb-2 last:pb-0">
                                                <span className="text-muted-foreground">
                                                    {formatDate(item.computed_at)}
                                                </span>
                                                <Badge variant={getScoreVariant(item.overall_score)}>
                                                    Score: {item.overall_score}
                                                </Badge>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-sm text-muted-foreground">No history available yet.</p>
                                )}
                            </CardContent>
                        </Card>
                    </div>
                </div>
            )}
        </div>
    );
}
