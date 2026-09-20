"use client";

import Link from "next/link";
import * as React from "react";
import { AlertCircle, BrainCircuit, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { createRepositoryAIAnalysis, getRepositoryAIAnalysis } from "@/lib/api/ai-analysis";
import { getAIConnectionStatus } from "@/lib/api/ai-connection";
import type { AIAnalysis } from "@/lib/types/ai-analysis";

function formatDate(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "Date unavailable" : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function RepositoryAISummaryPanel({ repositoryId }: { repositoryId: string }) {
    const [analysis, setAnalysis] = React.useState<AIAnalysis | null>(null);
    const [isConfigured, setIsConfigured] = React.useState<boolean | null>(null);
    const [isLoading, setIsLoading] = React.useState(true);
    const [isPending, setIsPending] = React.useState(false);
    const [error, setError] = React.useState<string | null>(null);

    const loadSummary = React.useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const [connection, latest] = await Promise.all([
                getAIConnectionStatus(),
                getRepositoryAIAnalysis(repositoryId),
            ]);

            setIsConfigured(connection.configured);
            setAnalysis("exists" in latest ? null : latest);
        } catch (nextError) {
            setError(nextError instanceof Error ? nextError.message : "The repository summary could not be loaded.");
        } finally {
            setIsLoading(false);
        }
    }, [repositoryId]);

    React.useEffect(() => {
        void Promise.resolve().then(loadSummary);
    }, [loadSummary]);

    const handleGenerate = async () => {
        setIsPending(true);
        setError(null);
        try {
            setAnalysis(await createRepositoryAIAnalysis(repositoryId));
            setIsConfigured(true);
        } catch (nextError) {
            setError(nextError instanceof Error ? nextError.message : "The repository summary could not be generated.");
        } finally {
            setIsPending(false);
        }
    };

    return (
        <Card className="border-accent/30 bg-card shadow-none">
            <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                    <BrainCircuit className="size-4 text-accent" aria-hidden="true" />
                    Repository summary
                </CardTitle>
                <CardDescription>AI-generated context from the repository&apos;s current health and findings.</CardDescription>
            </CardHeader>
            <CardContent>
                {isLoading ? (
                    <div className="space-y-3" aria-label="Loading repository summary" aria-busy="true">
                        <Skeleton className="h-4 w-1/3" />
                        <Skeleton className="h-16 w-full" />
                        <Skeleton className="h-4 w-2/3" />
                    </div>
                ) : isConfigured === false ? (
                    <div className="space-y-3 text-sm">
                        <p className="text-muted-foreground">Set up a valid BYOK connection before generating a repository summary.</p>
                        <Link href="/overview/settings#ai-connection" className="inline-flex h-9 items-center justify-center rounded-md border border-input bg-background px-3 text-sm font-medium transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                            Open AI/BYOK settings
                        </Link>
                    </div>
                ) : error ? (
                    <div className="space-y-3" role="alert">
                        <div className="flex items-start gap-2 text-sm text-destructive">
                            <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                            <p>{error}</p>
                        </div>
                        <Button variant="outline" size="sm" onClick={() => void loadSummary()}>Try again</Button>
                    </div>
                ) : analysis ? (
                    <div className="space-y-4 text-sm">
                        <p className="whitespace-pre-wrap leading-relaxed text-muted-foreground">{analysis.summary ?? "No summary was provided."}</p>
                        {analysis.recommendations && (
                            <div className="rounded-md border bg-muted/30 p-3">
                                <p className="mb-1 font-medium text-foreground">Recommended actions</p>
                                <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
                                    {Array.isArray(analysis.recommendations)
                                        ? analysis.recommendations.map((recommendation, index) => <li key={`${recommendation}-${index}`}>{recommendation}</li>)
                                        : <li>{analysis.recommendations}</li>}
                                </ul>
                            </div>
                        )}
                        <p className="text-xs text-muted-foreground">
                            Generated {analysis.completed_at ? formatDate(analysis.completed_at) : formatDate(analysis.requested_at)}
                        </p>
                    </div>
                ) : (
                    <div className="space-y-3 text-sm">
                        <p className="text-muted-foreground">Generate a repository summary to capture the current health and the most important follow-ups.</p>
                        <Button onClick={() => void handleGenerate()} loading={isPending}>
                            <Sparkles className="size-4" aria-hidden="true" />
                            Generate Summary
                        </Button>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
