"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { AlertTriangle, ExternalLink, GitFork, Search } from "lucide-react";

import { IssuesFeature } from "@/components/repositories/issues-feature";
import { PullRequestsFeature } from "@/components/repositories/pull-requests-feature";
import { EmptyState } from "@/components/rm/empty-state";
import { SectionHeading } from "@/components/rm/section-heading";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { getRepositories } from "@/lib/api/repositories";
import type { Repository } from "@/lib/types/github";
import { ActivityRepositoryCard } from "./activity-repository-card";
import { LanguageFootprint } from "./language-footprint";
import { ContributionHeatmap } from "./contribution-heatmap";
import { RepositoryContributionsView } from "./repository-contributions";
import { useActivityMetadata } from "./use-activity-metadata";
import { githubRepositoryUrl, readWorkspaceSelection, workspaceUrl, workspaceViews, workItemDetailUrl, type WorkspaceView } from "./workspace-selection";

export function ActivityWorkspace() {
    const params = useSearchParams();
    const [repositories, setRepositories] = React.useState<Repository[]>([]);
    const [isLoading, setIsLoading] = React.useState(true);
    const [error, setError] = React.useState(false);
    const [retryKey, setRetryKey] = React.useState(0);
    const [existingId, setExistingId] = React.useState("");
    const [search, setSearch] = React.useState("");
    const metadata = useActivityMetadata(repositories, retryKey);
    const { repository, view } = readWorkspaceSelection(params, repositories, existingId);

    const hasDetail = params.getAll("item").length > 0;
    const detailUrl = workItemDetailUrl(params, repository, view);

    // Remember history selections for invalid URL fallback. React retries this guarded
    // same-component update before rendering children, so it cannot start a stale fetch.
    if (repository && repository.id !== existingId) setExistingId(repository.id);

    React.useEffect(() => {
        let active = true;
        let generation = 0;
        async function loadRepositories() {
            const request = ++generation;
            let response: Repository[] | null;
            try { response = await getRepositories(); }
            catch { response = null; }
            if (!active || request !== generation) return;
            setRepositories([...new Map((response ?? []).map((item) => [item.id, item])).values()]);
            setError(response === null);
            setIsLoading(false);
        }
        void loadRepositories();
        // Recheck authorization when returning from GitHub or repository settings.
        window.addEventListener("focus", loadRepositories);
        return () => {
            active = false;
            window.removeEventListener("focus", loadRepositories);
        };
    }, [retryKey]);

    React.useEffect(() => {
        if (isLoading || error || hasDetail) return;
        const next = workspaceUrl(window.location.href, repository?.id, view);
        if (next !== `${window.location.pathname}${window.location.search}${window.location.hash}`) {
            window.history.replaceState(null, "", next);
        }
    }, [params, repository?.id, view, isLoading, error, hasDetail]);

    function navigate(repositoryId: string, nextView: WorkspaceView) {
        const url = new URL(window.location.href);
        url.searchParams.delete("item");
        const next = workspaceUrl(url.href, repositoryId, nextView);
        if (next !== `${window.location.pathname}${window.location.search}${window.location.hash}`) {
            window.history.pushState(null, "", next);
        }
    }

    function refresh() {
        setIsLoading(true);
        setError(false);
        setRetryKey((key) => key + 1);
    }

    const query = search.trim().toLocaleLowerCase();
    const filtered = repositories.filter((candidate) => candidate.full_name.toLocaleLowerCase().includes(query));
    const githubUrl = repository ? githubRepositoryUrl(repository.full_name) : null;

    return (
        <div className="min-w-0 space-y-8">
            <SectionHeading eyebrow="Workspace" title="Activity" description="Your unified workspace for connected repositories, contributions, issues, and pull requests." />
            <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1.85fr)_minmax(0,1fr)]" aria-label="Workspace summaries">
                <ContributionHeatmap />
                <LanguageFootprint repositories={repositories} metadata={metadata} loading={isLoading} error={error} />
            </div>
            <section className="min-w-0 space-y-4" aria-labelledby="connected-repositories-title">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div><h2 id="connected-repositories-title" className="text-lg font-semibold">Connected repositories</h2><p className="text-sm text-muted-foreground">Choose a repository to open its workspace.</p></div>
                    <Button variant="outline" size="sm" onClick={refresh} disabled={isLoading}>Refresh repositories</Button>
                </div>
                {isLoading ? (
                    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3" role="status" aria-label="Loading repositories" aria-busy="true">
                        {[0, 1, 2].map((index) => <Skeleton key={index} className="h-32 w-full" />)}<span className="sr-only">Loading connected repositories…</span>
                    </div>
                ) : error ? (
                    <div role="alert"><EmptyState icon={<AlertTriangle className="size-6" aria-hidden="true" />} title="Repositories are temporarily unavailable" description="RepoMedic could not load your connected repositories. Try again in a moment." action={<Button variant="outline" onClick={refresh}>Try again</Button>} /></div>
                ) : repositories.length === 0 ? (
                    <EmptyState icon={<GitFork className="size-6" aria-hidden="true" />} title="No connected repositories" description="Connect a repository from Repositories to open its workspace." />
                ) : (
                    <>
                        <label className="flex min-w-0 items-center gap-2 rounded-lg border bg-card px-3 focus-within:ring-2 focus-within:ring-ring">
                            <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" /><span className="sr-only">Search connected repositories</span>
                            <input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search by owner or repository name…" className="h-11 w-full min-w-0 bg-transparent text-sm outline-none" />
                        </label>
                        <p role="status" className="text-xs text-muted-foreground">{filtered.length} of {repositories.length} repositories shown</p>
                        {filtered.length === 0 ? (
                            <EmptyState title="No matching repositories" description="Try another owner or repository name. Your selected workspace stays open." action={<Button variant="outline" size="sm" onClick={() => setSearch("")}>Clear search</Button>} />
                        ) : (
                            <ul className="grid min-w-0 gap-4 md:grid-cols-2 xl:grid-cols-3" aria-label="Connected repositories">
                                {filtered.map((candidate) => {
                                    const selected = candidate.id === repository?.id;
                                    return <li key={candidate.id} className="min-w-0">
                                        <ActivityRepositoryCard repository={candidate} selected={selected} metadata={metadata[candidate.id]} onSelect={() => navigate(candidate.id, view)} />
                                    </li>;
                                })}
                            </ul>
                        )}
                    </>
                )}
            </section>
            {!isLoading && !error && hasDetail && (
                <div role={detailUrl ? "status" : "alert"} className="space-y-3 rounded-lg border bg-card p-4">
                    {detailUrl ? <><p>Item #{params.getAll("item")[0]} details open on GitHub.</p><a className="text-accent underline" href={detailUrl} target="_blank" rel="noopener noreferrer">Open item details on GitHub</a></>
                        : <p>This item link is invalid or its repository is unavailable. Choose a connected repository to view its list.</p>}
                    {repository && <Button variant="outline" onClick={() => navigate(repository.id, view)}>Back to {view === "issues" ? "Issues" : "Pull Requests"}</Button>}
                </div>
            )}
            {!isLoading && !error && repository && (!hasDetail || detailUrl) && (
                <section id="repository-workspace" aria-labelledby="repository-workspace-title" className="min-w-0 space-y-6 rounded-xl border bg-card p-4 shadow-soft sm:p-6">
                    <div className="flex min-w-0 flex-col gap-4 border-b pb-5 md:flex-row md:items-center md:justify-between">
                        <div className="min-w-0 space-y-2">
                            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Selected repository</p>
                            <h2 id="repository-workspace-title" className="break-words text-xl font-semibold [overflow-wrap:anywhere]">{repository.full_name}</h2>
                            {githubUrl ? <a href={githubUrl} target="_blank" rel="noopener noreferrer" aria-label={`Open ${repository.full_name} on GitHub`} className="inline-flex items-center gap-1 text-sm text-accent hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">View on GitHub <ExternalLink className="size-3.5" aria-hidden="true" /></a> : <p className="text-sm text-muted-foreground">GitHub repository link unavailable</p>}
                        </div>
                        <label className="flex min-w-0 flex-col gap-2 text-sm font-medium md:w-48 md:shrink-0">
                            Workspace view
                            <select value={view} onChange={(event) => {
                                const next = workspaceViews.find((option) => option.value === event.target.value);
                                if (next) navigate(repository.id, next.value);
                            }} aria-controls="repository-workspace-detail" className="h-11 w-full min-w-0 rounded-md border bg-background px-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                                {workspaceViews.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                            </select>
                        </label>
                    </div>
                    <div id="repository-workspace-detail" className="min-w-0">
                        {view === "contributions" ? <RepositoryContributionsView key={`contributions:${repository.id}`} repositoryId={repository.id} />
                            : view === "issues" ? <IssuesFeature key={`issues:${repository.id}`} selectedRepository={repository} />
                                : <PullRequestsFeature key={`pull-requests:${repository.id}`} selectedRepository={repository} />}
                    </div>
                </section>
            )}
        </div>
    );
}
