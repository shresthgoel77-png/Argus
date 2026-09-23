"use client";

import * as React from "react";
import { AlertTriangle, ChevronLeft, ChevronRight, MessageCircle } from "lucide-react";

import { EmptyState } from "@/components/rm/empty-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { listRepositoryBotInteractions } from "@/lib/api/bot-interactions";
import type { BotInteraction, BotInteractionListResponse } from "@/lib/types/bot-interactions";

const PAGE_SIZE = 20;

function displayValue(value: string) {
    return value.replace(/[_-]/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function statusLabel(interaction: BotInteraction) {
    if (interaction.status === "skipped") {
        return `Skipped${interaction.skip_reason ? ` - ${displayValue(interaction.skip_reason)}` : ""}`;
    }
    return displayValue(interaction.status);
}

function formatDate(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime())
        ? "Date unavailable"
        : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function InteractionsSkeleton() {
    return (
        <div className="space-y-3" aria-label="Loading bot activity" aria-busy="true">
            {Array.from({ length: 3 }, (_, index) => (
                <Card key={index}>
                    <CardContent className="space-y-3 p-5">
                        <Skeleton className="h-5 w-3/5" />
                        <Skeleton className="h-4 w-2/5" />
                        <Skeleton className="h-4 w-full" />
                    </CardContent>
                </Card>
            ))}
        </div>
    );
}

function InteractionRow({ interaction }: { interaction: BotInteraction }) {
    return (
        <Card>
            <CardContent className="space-y-3 p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 space-y-1">
                        <p className="font-medium text-foreground">{interaction.question_text}</p>
                        <p className="text-sm text-muted-foreground">
                            {interaction.requester_github_login} · {formatDate(interaction.created_at)}
                        </p>
                    </div>
                    <div className="flex shrink-0 flex-wrap gap-2 text-sm">
                        <span className="rounded-md border bg-muted px-2 py-1 text-muted-foreground">
                            {displayValue(interaction.intent)}
                        </span>
                        <span className="rounded-md border bg-card px-2 py-1 text-foreground">
                            {statusLabel(interaction)}
                        </span>
                    </div>
                </div>
                {interaction.status === "completed" && interaction.response_text ? (
                    <div className="border-l-2 border-accent pl-3 text-sm text-muted-foreground">
                        {interaction.response_text}
                    </div>
                ) : null}
            </CardContent>
        </Card>
    );
}

export function BotInteractionList({ repositoryId }: { repositoryId: string }) {
    const [result, setResult] = React.useState<BotInteractionListResponse | null>(null);
    const [isLoading, setIsLoading] = React.useState(true);
    const [error, setError] = React.useState(false);
    const [pageIndex, setPageIndex] = React.useState(0);
    const [cursors, setCursors] = React.useState<(string | undefined)[]>([undefined]);
    const [retryKey, setRetryKey] = React.useState(0);

    React.useEffect(() => {
        let active = true;
        async function fetchInteractions() {
            setIsLoading(true);
            setError(false);
            const cursor = cursors[pageIndex];
            const params: Record<string, string> = { limit: PAGE_SIZE.toString() };
            if (cursor) params.cursor = cursor;
            const response = await listRepositoryBotInteractions(repositoryId, params);
            if (active) {
                setResult(response);
                setError(response === null);
                setIsLoading(false);
                if (response?.next_cursor) {
                    setCursors(prev => {
                        const next = [...prev];
                        next[pageIndex + 1] = response.next_cursor ?? undefined;
                        return next;
                    });
                }
            }
        }
        void fetchInteractions();
        return () => { active = false; };
    }, [pageIndex, cursors, repositoryId, retryKey]);

    if (isLoading) return <InteractionsSkeleton />;
    if (error) {
        return (
            <EmptyState
                icon={<AlertTriangle className="size-6" aria-hidden="true" />}
                title="Bot activity is temporarily unavailable"
                description="RepoMedic could not load this repository's bot interactions. Try again in a moment."
                action={<Button variant="outline" onClick={() => setRetryKey((key) => key + 1)}>Try again</Button>}
            />
        );
    }
    if (!result || result.items.length === 0) {
        return (
            <EmptyState
                icon={<MessageCircle className="size-6" aria-hidden="true" />}
                title="No bot activity yet"
                description="Mention the bot in a comment to get started."
            />
        );
    }

    const hasPreviousPage = pageIndex > 0;
    const hasNextPage = Boolean(result.next_cursor);
    const offsetDisplay = pageIndex * PAGE_SIZE;

    return (
        <div className="space-y-3">
            {result.items.map((interaction) => <InteractionRow key={interaction.id} interaction={interaction} />)}
            <div className="flex items-center justify-between gap-4 border-t pt-4">
                <p className="text-sm text-muted-foreground">
                    Showing {offsetDisplay + 1}-{Math.min(offsetDisplay + result.items.length, result.total)} of {result.total}
                </p>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" disabled={!hasPreviousPage} onClick={() => setPageIndex((current) => Math.max(0, current - 1))}>
                        <ChevronLeft className="size-4" aria-hidden="true" /> Previous
                    </Button>
                    <Button variant="outline" size="sm" disabled={!hasNextPage} onClick={() => setPageIndex((current) => current + 1)}>
                        Next <ChevronRight className="size-4" aria-hidden="true" />
                    </Button>
                </div>
            </div>
        </div>
    );
}