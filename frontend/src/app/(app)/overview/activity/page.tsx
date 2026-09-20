"use client";

import * as React from "react";
import { Activity, AlertTriangle } from "lucide-react";

import { ActivityFeedList } from "@/components/activity/activity-feed-list";
import { SourceFilter } from "@/components/activity/source-filter";
import { EmptyState } from "@/components/rm/empty-state";
import { SectionHeading } from "@/components/rm/section-heading";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { getRepositories } from "@/lib/api/repositories";
import type { Repository } from "@/lib/types/github";
import type { ActivitySource } from "@/lib/types/activity";

export default function ActivityPage() {
    const [repositories, setRepositories] = React.useState<Repository[]>([]);
    const [isLoading, setIsLoading] = React.useState(true);
    const [error, setError] = React.useState(false);
    const [retryKey, setRetryKey] = React.useState(0);
    const [activeFilter, setActiveFilter] = React.useState<ActivitySource | "all">("all");

    React.useEffect(() => {
        let active = true;
        async function fetchRepositories() {
            const response = await getRepositories();
            if (active) {
                setRepositories(response ?? []);
                setError(response === null);
                setIsLoading(false);
            }
        }
        void fetchRepositories();
        return () => { active = false; };
    }, [retryKey]);

    return (
        <div className="space-y-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
                <SectionHeading
                    eyebrow="Workspace"
                    title="Activity"
                    description="Review recent events, finding updates, and bot interactions."
                />
                <SourceFilter value={activeFilter} onChange={setActiveFilter} />
            </div>

            {isLoading ? (
                <div className="space-y-4" aria-label="Loading repositories" aria-busy="true">
                    <Skeleton className="h-7 w-1/3" />
                    <Skeleton className="h-32 w-full" />
                </div>
            ) : error ? (
                <EmptyState
                    icon={<AlertTriangle className="size-6" aria-hidden="true" />}
                    title="Activity is temporarily unavailable"
                    description="RepoMedic could not load your connected repositories. Try again in a moment."
                    action={<Button variant="outline" onClick={() => setRetryKey((key) => key + 1)}>Try again</Button>}
                />
            ) : repositories.length === 0 ? (
                <EmptyState
                    icon={<Activity className="size-6" aria-hidden="true" />}
                    title="No connected repositories"
                    description="Connect a repository to see activity."
                />
            ) : (
                <div className="space-y-8">
                    {repositories.map((repository) => (
                        <section key={repository.id} className="space-y-3" aria-labelledby={`activity-${repository.id}`}>
                            <h2 id={`activity-${repository.id}`} className="text-lg font-semibold tracking-tight">{repository.full_name}</h2>
                            <ActivityFeedList key={`${repository.id}-${activeFilter}`} repositoryId={repository.id} sourceFilter={activeFilter} />
                        </section>
                    ))}
                </div>
            )}
        </div>
    );
}
