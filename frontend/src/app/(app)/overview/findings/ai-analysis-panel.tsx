"use client";

import Link from "next/link";
import * as React from "react";
import { AlertCircle, BrainCircuit, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { createFindingAIAnalysis, getFindingAIAnalysis } from "@/lib/api/ai-analysis";
import { getAIConnectionStatus } from "@/lib/api/ai-connection";
import type { AIAnalysis } from "@/lib/types/ai-analysis";

function formatDate(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "Date unavailable" : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function displayValue(value: string) {
    return value.replace(/[_-]/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function getRecommendations(value: AIAnalysis["recommendations"]): string[] {
    if (Array.isArray(value)) return value;
    return value ? [value] : [];
}

function AnalysisContent({ analysis }: { analysis: AIAnalysis }) {
    const analysisRecommendations = getRecommendations(analysis.recommendations);
    return (
        <div className="space-y-4 text-sm">
            <div>
                <p className="mb-1 font-medium text-foreground">Summary</p>
                <p className="whitespace-pre-wrap leading-relaxed text-muted-foreground">{analysis.summary ?? "No summary was provided."}</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-md border border-accent/30 bg-accent/5 p-3">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">AI severity assessment</p>
                    <p className="mt-1 font-semibold text-foreground">{analysis.severity_assessment ? displayValue(analysis.severity_assessment) : "Not provided"}</p>
                </div>
                <div className="rounded-md border bg-muted/30 p-3">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">AI confidence</p>
                    <p className="mt-1 font-semibold text-foreground">{analysis.confidence ?? "Not provided"}</p>
                </div>
            </div>
            <div>
                <p className="mb-1 font-medium text-foreground">Recommendations</p>
                {analysisRecommendations.length > 0 ? (
                    <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
                        {analysisRecommendations.map((recommendation, index) => <li key={`${recommendation}-${index}`}>{recommendation}</li>)}
                    </ul>
                ) : <p className="text-muted-foreground">No recommendations were provided.</p>}
            </div>
            <p className="text-xs text-muted-foreground">Generated {formatDate(analysis.completed_at ?? analysis.requested_at)}</p>
        </div>
    );
}

export function AIAnalysisPanel({ findingId }: { findingId: string }) {
    const [analysis, setAnalysis] = React.useState<AIAnalysis | null>(null);
    const [isConfigured, setIsConfigured] = React.useState<boolean | null>(null);
    const [isLoading, setIsLoading] = React.useState(true);
    const [isPending, setIsPending] = React.useState(false);
    const [error, setError] = React.useState<string | null>(null);

    const loadAnalysis = React.useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const [connection, latest] = await Promise.all([getAIConnectionStatus(), getFindingAIAnalysis(findingId)]);
            setIsConfigured(connection.configured);
            setAnalysis("exists" in latest ? null : latest);
        } catch (nextError) {
            setError(nextError instanceof Error ? nextError.message : "The AI analysis could not be loaded.");
        } finally {
            setIsLoading(false);
        }
    }, [findingId]);

    React.useEffect(() => { void Promise.resolve().then(loadAnalysis); }, [loadAnalysis]);

    const handleAnalyze = async () => {
        setIsPending(true);
        setError(null);
        try {
            setAnalysis(await createFindingAIAnalysis(findingId));
            setIsConfigured(true);
        } catch (nextError) {
            setError(nextError instanceof Error ? nextError.message : "The AI analysis could not be generated.");
        } finally {
            setIsPending(false);
        }
    };

    return (
        <Card className="border-accent/30 bg-card shadow-none">
            <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base"><BrainCircuit className="size-4 text-accent" aria-hidden="true" />Explain with AI</CardTitle>
                <CardDescription>AI-generated context is separate from the finding&apos;s deterministic severity.</CardDescription>
            </CardHeader>
            <CardContent>
                {isLoading ? <div className="space-y-3" aria-label="Loading AI analysis" aria-busy="true"><Skeleton className="h-4 w-1/3" /><Skeleton className="h-16 w-full" /><Skeleton className="h-4 w-2/3" /></div> : isConfigured === false ? (
                    <div className="space-y-3 text-sm">
                        <p className="text-muted-foreground">Set up a valid BYOK connection before generating an AI explanation.</p>
                        <Link href="/overview/settings#ai-connection" className="inline-flex h-9 items-center justify-center rounded-md border border-input bg-background px-3 text-sm font-medium transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">Open Settings AI/BYOK</Link>
                    </div>
                ) : error ? (
                    <div className="space-y-3" role="alert"><div className="flex items-start gap-2 text-sm text-destructive"><AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" /><p>{error}</p></div><Button variant="outline" size="sm" onClick={() => void loadAnalysis()}>Try again</Button></div>
                ) : analysis ? <AnalysisContent analysis={analysis} /> : (
                    <div className="space-y-3 text-sm"><p className="text-muted-foreground">Generate a focused explanation, severity assessment, and remediation guidance for this finding.</p><Button onClick={() => void handleAnalyze()} loading={isPending}><Sparkles className="size-4" aria-hidden="true" />Explain with AI</Button></div>
                )}
            </CardContent>
        </Card>
    );
}