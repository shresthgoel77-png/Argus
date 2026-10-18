"use client";

import * as React from "react";
import { ExternalLink, Loader2 } from "lucide-react";

import { EmptyState } from "@/components/rm/empty-state";
import { Button } from "@/components/ui/button";
import { getRepositories } from "@/lib/api/repositories";
import { listRepositoryWorkItems, type GitHubWorkItem } from "@/lib/api/repository-work-items";
import type { Repository } from "@/lib/types/github";

export function RepositoryWorkItems({ kind, selectedRepository: controlledRepository }: {
    kind: "issues" | "pull-requests";
    /** A repository supplied by an embedding workspace; undefined keeps the standalone selector. */
    selectedRepository?: Repository | null;
}) {
    const [repositories, setRepositories] = React.useState<Repository[]>([]);
    const [selectedId, setSelectedId] = React.useState("");
    const [repositoriesLoading, setRepositoriesLoading] = React.useState(controlledRepository === undefined);
    const [repositoriesError, setRepositoriesError] = React.useState<string | null>(null);
    const [itemsResult, setItemsResult] = React.useState<{ scope: string; items: GitHubWorkItem[] } | null>(null);
    const [requestState, setRequestState] = React.useState<{ scope: string; status: "loading" | "success" | "error"; error?: string }>({
        scope: "",
        status: "loading",
    });
    const [refreshKey, setRefreshKey] = React.useState(0);
    const [repositoryRetryKey, setRepositoryRetryKey] = React.useState(0);
    const selectedIdForRequest = controlledRepository === undefined ? selectedId : controlledRepository?.id ?? "";
    const selectedRepository = controlledRepository === undefined
        ? repositories.find((repository) => repository.id === selectedIdForRequest)
        : controlledRepository ?? undefined;
    const requestScope = `${kind}:${selectedIdForRequest}:${refreshKey}`;

    React.useEffect(() => {
        if (controlledRepository !== undefined) return;
        let active = true;
        void getRepositories().then((result) => {
            if (!active) return;
            if (result === null) {
                setRepositoriesError("Connected repositories could not be loaded.");
            } else {
                setRepositories(result);
                setSelectedId(result.find((repository) => repository.monitoring_enabled)?.id ?? result[0]?.id ?? "");
            }
            setRepositoriesLoading(false);
        });
        return () => { active = false; };
    }, [controlledRepository, repositoryRetryKey]);

    React.useEffect(() => {
        if (!selectedIdForRequest) return;
        let active = true;
        async function loadItems() {
            setRequestState({ scope: requestScope, status: "loading" });
            try {
                const result = await listRepositoryWorkItems(selectedIdForRequest, kind);
                if (active) {
                    setItemsResult({ scope: requestScope, items: result });
                    setRequestState({ scope: requestScope, status: "success" });
                }
            } catch (loadError: unknown) {
                if (active) {
                    setItemsResult({ scope: requestScope, items: [] });
                    setRequestState({
                        scope: requestScope,
                        status: "error",
                        error: loadError instanceof Error ? loadError.message : "GitHub data could not be loaded.",
                    });
                }
            }
        }
        void loadItems();
        return () => { active = false; };
    }, [selectedIdForRequest, kind, refreshKey, requestScope]);

    const noun = kind === "issues" ? "issues" : "pull requests";
    const isLoading = (controlledRepository === undefined && repositoriesLoading)
        || (!!selectedIdForRequest && (requestState.scope !== requestScope || requestState.status === "loading"));
    const error = repositoriesError
        ?? (requestState.scope === requestScope && requestState.status === "error"
            ? requestState.error ?? "GitHub data could not be loaded."
            : null);
    const items = itemsResult?.scope === requestScope ? itemsResult.items : [];

    if (isLoading && controlledRepository === undefined && repositoriesLoading) {
        return <div className="flex justify-center p-8"><Loader2 className="size-6 animate-spin text-muted-foreground" /></div>;
    }
    if (controlledRepository === undefined && repositories.length === 0 && !error && !repositoriesLoading) {
        return <EmptyState title="No repositories connected" description={`Connect a GitHub repository to load its real ${noun}.`} />;
    }

    if (controlledRepository === null) {
        return <EmptyState title="Select a repository" description={`Select a connected repository to load its real ${noun}.`} />;
    }

    return (
        <section className="space-y-4">
            {controlledRepository === undefined && repositories.length > 0 && (
                <label className="flex items-center gap-3 text-sm">
                    <span className="font-medium">Repository</span>
                    <select
                        aria-label="Select repository"
                        className="h-10 max-w-full rounded-md border bg-background px-3"
                        value={selectedIdForRequest}
                        onChange={(event) => setSelectedId(event.target.value)}
                    >
                        {repositories.map((repository) => (
                            <option key={repository.id} value={repository.id}>{repository.full_name}</option>
                        ))}
                    </select>
                </label>
            )}
            {error ? (
                <div role="alert" className="space-y-3 rounded-lg border border-destructive/40 p-4 text-sm">
                    <p>{error}</p>
                    <Button variant="outline" size="sm" onClick={() => {
                        if (repositoriesError) {
                            setRepositoriesLoading(true);
                            setRepositoriesError(null);
                            setRepositoryRetryKey((key) => key + 1);
                        } else {
                            setRefreshKey((key) => key + 1);
                        }
                    }}>Try again</Button>
                </div>
            ) : isLoading ? (
                <div className="flex justify-center p-8" aria-label={`Loading GitHub ${noun}`}>
                    <Loader2 className="size-6 animate-spin text-muted-foreground" />
                </div>
            ) : items.length === 0 ? (
                <EmptyState title={`No open ${noun}`} description={`GitHub reports no open ${noun} for ${selectedRepository?.full_name ?? "this repository"}.`} />
            ) : (
                <div className="space-y-3">
                    {items.map((item) => (
                        <article key={item.number} className="rounded-lg border bg-card p-4">
                            <div className="flex flex-wrap items-start justify-between gap-3">
                                <div className="space-y-1">
                                    <h2 className="font-medium">
                                        <span className="mr-2 text-muted-foreground">#{item.number}</span>
                                        {item.title}
                                    </h2>
                                    <p className="text-sm text-muted-foreground">
                                        {item.state} {item.draft ? "· draft" : ""}
                                        {item.user?.login ? ` · opened by ${item.user.login}` : ""}
                                        {item.updated_at ? ` · updated ${new Date(item.updated_at).toLocaleDateString()}` : ""}
                                    </p>
                                    {!!item.labels.length && (
                                        <div className="flex flex-wrap gap-2 pt-1">
                                            {item.labels.map((label, index) => (
                                                <span key={`${label.name ?? "label"}-${index}`} className="rounded-full border px-2 py-0.5 text-xs">{label.name ?? "Label"}</span>
                                            ))}
                                        </div>
                                    )}
                                </div>
                                <a href={item.html_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm text-primary hover:underline">
                                    View on GitHub <ExternalLink className="size-3.5" aria-hidden="true" />
                                </a>
                            </div>
                        </article>
                    ))}
                </div>
            )}
        </section>
    );
}
