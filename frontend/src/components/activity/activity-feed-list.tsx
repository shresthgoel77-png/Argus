"use client";

import * as React from "react";
import {
    Activity,
    AlertTriangle,
    Bot,
    CheckCircle2,
    ChevronDown,
    ChevronLeft,
    ChevronRight,
    ChevronUp,
    GitCommit,
    HeartPulse,
    MessageCircle,
    ShieldAlert,
} from "lucide-react";

import { EmptyState } from "@/components/rm/empty-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { listRepositoryActivity } from "@/lib/api/activity";
import type { ActivityFeedResponse, ActivityItem, ActivitySource } from "@/lib/types/activity";

const PAGE_SIZE = 20;

function displayValue(value: string) {
    if (!value) return "";
    return value.replace(/[_-]/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDate(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime())
        ? "Date unavailable"
        : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function SourceIcon({ source, className }: { source: ActivitySource; className?: string }) {
    switch (source) {
        case "github_event":
            return <GitCommit className={className} />;
        case "finding_detected":
            return <ShieldAlert className={className} />;
        case "finding_resolved":
            return <CheckCircle2 className={className} />;
        case "health_changed":
            return <HeartPulse className={className} />;
        case "bot_interaction":
            return <Bot className={className} />;
        default:
            return <Activity className={className} />;
    }
}

function ActivityRow({ item }: { item: ActivityItem }) {
    const [isExpanded, setIsExpanded] = React.useState(false);
    const d = item.source === "bot_interaction" && item.details ? item.details : null;
    const isBotInteraction = d !== null;

    return (
        <Card>
            <CardContent className="space-y-3 p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex min-w-0 items-start gap-4">
                        <div className="mt-1 rounded-full bg-muted p-2 text-muted-foreground">
                            <SourceIcon source={item.source} className="size-4" />
                        </div>
                        <div className="space-y-1">
                            <p className="font-medium text-foreground">{item.title}</p>
                            <p className="text-sm text-muted-foreground">
                                {formatDate(item.timestamp)}
                                {d?.requester_github_login ? ` · by ${d.requester_github_login}` : ""}
                            </p>
                        </div>
                    </div>

                    <div className="flex shrink-0 flex-wrap items-center gap-2 text-sm">
                        {d && d.intent && (
                            <span className="rounded-md border bg-muted px-2 py-1 text-muted-foreground">
                                {displayValue(d.intent)}
                            </span>
                        )}
                        {d && d.status && (
                            <span className="rounded-md border bg-card px-2 py-1 text-foreground">
                                {d.status === "skipped"
                                    ? `Skipped${d.skip_reason ? ` - ${displayValue(d.skip_reason)}` : ""}`
                                    : displayValue(d.status)}
                            </span>
                        )}
                        {isBotInteraction && (
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setIsExpanded(!isExpanded)}
                                className="-mr-2 ml-1 px-2"
                                aria-expanded={isExpanded}
                            >
                                {isExpanded ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
                            </Button>
                        )}
                    </div>
                </div>

                <div className="pl-12">
                    {!isBotInteraction && (
                        <p className="text-sm text-muted-foreground">{item.summary}</p>
                    )}

                    {d && isExpanded && (
                        <div className="mt-2 space-y-3 border-l-2 border-muted pl-4">
                            <div className="space-y-1">
                                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Question</p>
                                <p className="text-sm text-foreground">{d.question_text}</p>
                            </div>
                            {d.status === "completed" && d.response_text && (
                                <div className="space-y-1">
                                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Response</p>
                                    <div className="text-sm text-muted-foreground">{d.response_text}</div>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}

function LoadingSkeleton() {
    return (
        <div className="space-y-3" aria-label="Loading activity feed" aria-busy="true">
            {Array.from({ length: 3 }, (_, index) => (
                <Card key={index}>
                    <CardContent className="flex gap-4 p-5">
                        <Skeleton className="mt-1 size-8 shrink-0 rounded-full" />
                        <div className="w-full space-y-3">
                            <Skeleton className="h-5 w-3/5" />
                            <Skeleton className="h-4 w-2/5" />
                            <Skeleton className="h-4 w-full" />
                        </div>
                    </CardContent>
                </Card>
            ))}
        </div>
    );
}

export function ActivityFeedList({ repositoryId, sourceFilter }: { repositoryId: string; sourceFilter: ActivitySource | "all" }) {
    const [result, setResult] = React.useState<ActivityFeedResponse | null>(null);
    const [isLoading, setIsLoading] = React.useState(true);
    const [error, setError] = React.useState(false);

    // Pagination history to support "Previous" since the API only accepts `before` for next page
    const [cursors, setCursors] = React.useState<(string | null)[]>([null]);
    const [pageIndex, setPageIndex] = React.useState(0);
    const [retryKey, setRetryKey] = React.useState(0);

    React.useEffect(() => {
        let active = true;
        async function fetchFeed() {
            setIsLoading(true);
            setError(false);

            const params: Record<string, string> = { limit: PAGE_SIZE.toString() };
            if (sourceFilter !== "all") {
                params.source = sourceFilter;
            }
            const currentCursor = cursors[pageIndex];
            if (currentCursor) {
                params.before = currentCursor;
            }

            const response = await listRepositoryActivity(repositoryId, params);
            if (active) {
                setResult(response);
                setError(response === null);
                setIsLoading(false);
            }
        }
        void fetchFeed();
        return () => { active = false; };
    }, [pageIndex, cursors, sourceFilter, repositoryId, retryKey]);

    if (isLoading) return <LoadingSkeleton />;
    if (error) {
        return (
            <EmptyState
                icon={<AlertTriangle className="size-6" aria-hidden="true" />}
                title="Activity feed is temporarily unavailable"
                description="RepoMedic could not load this repository's activity. Try again in a moment."
                action={<Button variant="outline" onClick={() => setRetryKey((key) => key + 1)}>Try again</Button>}
            />
        );
    }
    if (!result || result.items.length === 0) {
        return (
            <EmptyState
                icon={<MessageCircle className="size-6" aria-hidden="true" />}
                title={sourceFilter === "all" ? "No activity yet" : "No matching activity found"}
                description="Check back later for updates."
            />
        );
    }

    const hasPreviousPage = pageIndex > 0;
    const hasNextPage = result.next_before !== null;

    const handleNext = () => {
        if (!hasNextPage) return;
        // if we haven't fetched this page yet, add its cursor
        if (pageIndex + 1 >= cursors.length) {
            setCursors(prev => [...prev, result.next_before]);
        }
        setPageIndex(current => current + 1);
    };

    const handlePrevious = () => {
        if (!hasPreviousPage) return;
        setPageIndex(current => current - 1);
    };

    return (
        <div className="space-y-3">
            {result.items.map((item) => <ActivityRow key={`${item.source}-${item.reference_id}`} item={item} />)}
            <div className="flex items-center justify-between gap-4 border-t pt-4">
                <p className="text-sm text-muted-foreground">
                    Page {pageIndex + 1}
                </p>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" disabled={!hasPreviousPage} onClick={handlePrevious}>
                        <ChevronLeft className="size-4 mr-1" aria-hidden="true" /> Previous
                    </Button>
                    <Button variant="outline" size="sm" disabled={!hasNextPage} onClick={handleNext}>
                        Next <ChevronRight className="size-4 ml-1" aria-hidden="true" />
                    </Button>
                </div>
            </div>
        </div>
    );
}
