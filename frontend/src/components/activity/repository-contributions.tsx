"use client";

import * as React from "react";
import { ExternalLink, GitCommitHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth/use-auth";
import { ContributionReadError, fetchRepositoryContributions } from "@/lib/api/repository-contributions";
import type { RepositoryContributionEvent, RepositoryContributions } from "@/lib/types/repository-contributions";
import { useRepositoryContributions } from "./use-repository-contributions";
import { CommitFrequency } from "./commit-frequency";
import { contributionDate, contributionDiff, contributionMonths, mergeContributionEvents } from "./contribution-presentation";

const number = (value: number | null | undefined) => value == null ? "Unavailable" : value.toLocaleString("en-US");

function readError(error: ContributionReadError) {
    switch (error.code) {
        case "authentication": return "Sign in again to read this repository's contributions.";
        case "not_found": return "This repository is unavailable or your access has changed.";
        case "snapshot_expired": return "This snapshot expired. Reload contributions to start a fresh timeline.";
        case "invalid_range": return "This contribution period could not be read.";
        default: return "Contributions are temporarily unavailable. Try again in a moment.";
    }
}

function coverage(data: RepositoryContributions) {
    if (data.status === "pending") return "GitHub is preparing this read. No counts are available yet.";
    if (data.status === "unsupported") return "GitHub did not supply supported contribution data for this read.";
    if (data.status === "unavailable") return data.reason === "permission_denied" || data.reason === "authorization_or_rate_limit"
        ? "GitHub access could not be confirmed for this read. Counts remain unavailable."
        : "GitHub contribution data is unavailable. Counts remain unknown.";
    if (!data.history_complete) return data.reason === "scan_limit"
        ? `Partial history · limited to ${data.scope.max_commits} commits. Metrics and chart cover retrieved commits only.`
        : "Partial history · the read stopped before the window was complete. Metrics and chart cover retrieved commits only.";
    return data.status === "partial" ? "Complete history for this window · some author or line fields are unavailable."
        : "Complete history for this window.";
}

function ContributionMetrics({ data }: { data?: RepositoryContributions }) {
    const metrics = data?.metrics;
    return <dl className="grid min-w-0 gap-3 sm:grid-cols-3" aria-label="Repository contribution metrics">
        <div className="min-w-0 rounded-lg border bg-background p-4"><dt className="text-xs font-medium text-muted-foreground">Commits</dt><dd className="mt-1 text-2xl font-semibold tabular-nums">{number(metrics?.commit_count)}</dd><dd className="mt-1 text-xs text-muted-foreground">{data && !data.history_complete ? "Retrieved in this period" : "In this period"}</dd></div>
        <div className="min-w-0 rounded-lg border bg-background p-4"><dt className="text-xs font-medium text-muted-foreground">Line changes</dt><dd className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xl font-semibold tabular-nums"><span className="text-success" aria-label={`Additions: ${number(metrics?.additions)}`}>{metrics?.additions == null ? "Additions unavailable" : `+${number(metrics.additions)}`}</span><span className="text-destructive" aria-label={`Deletions: ${number(metrics?.deletions)}`}>{metrics?.deletions == null ? "Deletions unavailable" : `−${number(metrics.deletions)}`}</span></dd><dd className="mt-1 text-xs text-muted-foreground">Reported additions / deletions</dd></div>
        <div className="min-w-0 rounded-lg border bg-background p-4"><dt className="text-xs font-medium text-muted-foreground">Active contributors</dt><dd className="mt-1 text-2xl font-semibold tabular-nums">{number(metrics?.distinct_authors)}</dd><dd className="mt-1 text-xs text-muted-foreground">Primary-author identities{metrics?.distinct_authors === null ? ` · ${metrics.known_authors} known; ${metrics.unknown_author_commits} commits unattributed` : ""}</dd></div>
    </dl>;
}

function CommitRow({ event }: { event: RepositoryContributionEvent }) {
    const lines = event.message?.trim().split("\n");
    const headline = lines?.[0]?.trim() || "Commit message unavailable";
    const detail = lines?.slice(1).join("\n").trim();
    const ratio = contributionDiff(event.additions, event.deletions);
    return <li className="relative min-w-0 border-l pl-5 pb-6 last:pb-1">
        <GitCommitHorizontal className="absolute -left-2 top-0.5 size-4 bg-card text-accent" aria-hidden="true" />
        <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0 space-y-2">
                <p className="break-words text-sm font-medium [overflow-wrap:anywhere]">{headline}</p>
                {detail && <details className="text-xs"><summary className="cursor-pointer rounded-sm text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">Full commit message</summary><p className="mt-2 whitespace-pre-wrap break-words text-muted-foreground [overflow-wrap:anywhere]">{event.message}</p></details>}
                <p className="break-words text-xs text-muted-foreground [overflow-wrap:anywhere]">{event.author.login ? `@${event.author.login}` : event.author.name || "Author unavailable"} · <time dateTime={event.committed_at}>{contributionDate(event.committed_at, true)}</time></p>
                <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                    <span className="break-all" title="Reachable from this default branch's pinned head">Reachable from {event.branch}</span>
                    {event.html_url ? <a href={event.html_url} target="_blank" rel="noopener noreferrer" aria-label={`View commit ${event.sha.slice(0, 7)} on GitHub`} className="inline-flex items-center gap-1 rounded-sm text-accent hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><code>{event.sha.slice(0, 7)}</code><ExternalLink className="size-3" aria-hidden="true" /></a> : <span>GitHub link unavailable · <code>{event.sha.slice(0, 7)}</code></span>}
                </div>
                {event.authored_at && event.authored_at !== event.committed_at && <p className="text-xs text-muted-foreground">Authored <time dateTime={event.authored_at}>{contributionDate(event.authored_at, true)}</time></p>}
            </div>
            <div className="shrink-0 space-y-1.5 text-xs tabular-nums sm:text-right">
                <p className="flex flex-wrap gap-2 sm:justify-end"><span className="text-success">{event.additions === null ? "Additions unavailable" : `+${number(event.additions)}`}</span><span className="text-destructive">{event.deletions === null ? "Deletions unavailable" : `−${number(event.deletions)}`}</span></p>
                {ratio ? <span role="img" aria-label={`${event.additions} additions, ${event.deletions} deletions; proportions within this commit`} className="inline-flex h-1.5 w-20 overflow-hidden rounded-full bg-muted"><span className="bg-success" style={{ width: `${ratio.additions}%` }} /><span className="bg-destructive" style={{ width: `${ratio.deletions}%` }} /></span> : <p className="text-muted-foreground">Diff proportions unavailable</p>}
            </div>
        </div>
    </li>;
}

type MoreState = { snapshot: string; items: RepositoryContributionEvent[]; next: string | null; loading: boolean; error?: ContributionReadError; seen: string[] };

function ContributionContent({ repositoryId }: { repositoryId: string }) {
    const [revision, setRevision] = React.useState(0);
    const read = useRepositoryContributions(repositoryId, true, {}, revision);
    const data = read.status === "ready" ? read.data : undefined;
    const [more, setMore] = React.useState<MoreState>();
    const generation = React.useRef(0);
    const controller = React.useRef<{ snapshot: string; abort: AbortController } | null>(null);
    React.useEffect(() => {
        if (controller.current && controller.current.snapshot !== data?.snapshot_id) {
            generation.current++;
            controller.current.abort.abort();
            controller.current = null;
        }
    }, [data?.snapshot_id]);
    React.useEffect(() => () => { generation.current++; controller.current?.abort.abort(); }, []);
    const currentMore = data && more?.snapshot === data.snapshot_id ? more : undefined;
    const items = mergeContributionEvents(data?.items ?? [], currentMore?.items ?? []);
    const next = currentMore ? currentMore.next : data?.next_cursor;
    const loading = read.status === "loading";
    function retry() {
        generation.current++;
        controller.current?.abort.abort();
        setMore(undefined);
        setRevision((value) => value + 1);
    }

    async function loadMore() {
        if (!data || !next || currentMore?.loading || currentMore?.error?.code === "snapshot_expired") return;
        const request = ++generation.current;
        controller.current?.abort.abort();
        controller.current = { snapshot: data.snapshot_id, abort: new AbortController() };
        const prior: MoreState = currentMore ?? { snapshot: data.snapshot_id, items: [], next, loading: false, seen: [] };
        setMore({ ...prior, loading: true, error: undefined });
        try {
            const page = await fetchRepositoryContributions(repositoryId, {
                start: data.scope.start_date, end: data.scope.end_date, cursor: next, limit: 20,
            }, controller.current.abort.signal);
            if (request !== generation.current) return;
            if (page.snapshot_id !== data.snapshot_id || JSON.stringify(page.scope) !== JSON.stringify(data.scope)
                || JSON.stringify(page.metrics) !== JSON.stringify(data.metrics) || JSON.stringify(page.frequency) !== JSON.stringify(data.frequency)) {
                throw new ContributionReadError("snapshot_expired");
            }
            if (page.next_cursor && (page.next_cursor === next || prior.seen.includes(page.next_cursor))) throw new ContributionReadError("unavailable");
            setMore({ snapshot: data.snapshot_id, items: mergeContributionEvents(prior.items, page.items),
                next: page.next_cursor, loading: false, seen: [...prior.seen, next] });
        } catch (error) {
            if (request === generation.current) setMore({ ...prior, loading: false,
                error: error instanceof ContributionReadError ? error : new ContributionReadError("unavailable") });
        }
    }

    return <section className="min-w-0 space-y-5" aria-label="Repository contributions">
        <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 space-y-1"><h3 className="font-semibold">Repository contributions</h3>
                {data ? <>
                    <p className="text-sm text-muted-foreground">{contributionDate(data.scope.start_date)} – {contributionDate(data.scope.end_date)} · UTC</p>
                    <p className="break-words text-xs text-muted-foreground [overflow-wrap:anywhere]">Default branch: {data.scope.branch ?? "unavailable"}{data.scope.head_sha ? ` · snapshot ${data.scope.head_sha.slice(0, 7)}` : ""}</p>
                    <p className="text-xs text-muted-foreground">Through <time dateTime={data.scope.until}>{contributionDate(data.scope.until, true)}</time></p>
                </> : <p className="text-xs text-muted-foreground">90 UTC dates · default-branch history{loading ? " · reading period and coverage…" : " · period and coverage unavailable"}</p>}
            </div>
            <Button variant="outline" size="sm" onClick={retry} disabled={loading}>{read.status === "error" ? "Retry contributions" : "Refresh contributions"}</Button>
        </div>
        {data && <div role="status" className={`space-y-1 rounded-lg border p-3 text-xs ${data.status === "available" ? "bg-accent/5 text-muted-foreground" : "bg-muted text-foreground"}`}><p>{coverage(data)}</p>{data.retry_after_seconds !== null && <p>Try again in {data.retry_after_seconds} seconds.</p>}</div>}
        {read.status === "error" && <p role="alert" className="rounded-lg border p-3 text-sm">{readError(read.error)}</p>}
        {read.status === "idle" && <p role="status" className="text-sm text-muted-foreground">Sign in to view repository contributions.</p>}
        {loading ? <div role="status" aria-label="Loading contribution metrics" className="grid gap-3 sm:grid-cols-3">{[0, 1, 2].map((key) => <Skeleton key={key} className="h-28 w-full" />)}</div> : <ContributionMetrics data={data} />}
        <section aria-label="Contribution timeline" className="min-w-0 space-y-4">
            <div className="space-y-1"><h4 className="text-sm font-semibold">Commit timeline</h4><p className="text-xs text-muted-foreground">Newest first · primary authors · merge commits included. PR associations and coauthors are not supplied by this source.</p></div>
            {loading ? <div role="status" aria-label="Loading commit timeline"><Skeleton className="h-32 w-full" /></div>
                : items.length ? <>{contributionMonths(items).map((month) => <section key={month.key} aria-label={month.label} className="min-w-0 space-y-3"><h5 className="text-xs font-semibold text-muted-foreground">{month.label}</h5><ol className="min-w-0 pl-2" aria-label={`Commits in ${month.label}`}>{month.items.map((event) => <CommitRow key={event.sha} event={event} />)}</ol></section>)}</>
                    : <p className="rounded-lg border border-dashed p-5 text-sm text-muted-foreground">{data?.metrics?.commit_count === 0 && data.history_complete ? "No commits in this period."
                        : data?.status === "pending" ? "Timeline pending. Retry after GitHub has prepared the read."
                            : data?.status === "unsupported" ? "Timeline unsupported for this read."
                                : data?.metrics ? "No commit records returned. Window coverage may be incomplete." : "Commit timeline unavailable."}</p>}
            {data?.metrics && <p className="text-xs text-muted-foreground">Showing {items.length} of {data.metrics.commit_count} retrieved commits{!data.history_complete ? "; window coverage is partial" : ""}.</p>}
            {currentMore?.error && <div role="alert" className="space-y-2 rounded-md border p-3 text-sm"><p>{currentMore.error.code === "snapshot_expired" ? readError(currentMore.error) : `More commits could not be loaded. ${readError(currentMore.error)}`}</p>{currentMore.error.code === "snapshot_expired" && <Button variant="outline" size="sm" onClick={retry}>Reload contributions</Button>}</div>}
            {next && currentMore?.error?.code !== "snapshot_expired" && <Button variant="outline" size="sm" onClick={() => void loadMore()} disabled={currentMore?.loading}>{currentMore?.loading ? "Loading more commits…" : currentMore?.error ? "Retry loading commits" : "Load more commits"}</Button>}
        </section>
        {loading ? <div role="status" aria-label="Loading commit frequency"><Skeleton className="h-60 w-full" /></div> : <CommitFrequency data={data} />}
    </section>;
}

export function RepositoryContributionsView({ repositoryId }: { repositoryId: string }) {
    const { user, isAuthenticated } = useAuth();
    return <ContributionContent key={`${repositoryId}:${isAuthenticated ? user?.id : "signed-out"}`} repositoryId={repositoryId} />;
}
