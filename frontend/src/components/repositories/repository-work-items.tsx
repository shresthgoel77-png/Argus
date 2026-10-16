"use client";

import * as React from "react";
import { ExternalLink, Loader2 } from "lucide-react";

import { EmptyState } from "@/components/rm/empty-state";
import { Button } from "@/components/ui/button";
import { getRepositories } from "@/lib/api/repositories";
import { listRepositoryWorkItems, type GitHubWorkItem } from "@/lib/api/repository-work-items";
import type { Repository } from "@/lib/types/github";

export function RepositoryWorkItems({ kind }: { kind: "issues" | "pull-requests" }) {
    const [repositories, setRepositories] = React.useState<Repository[]>([]);
    const [selectedId, setSelectedId] = React.useState("");
    const [items, setItems] = React.useState<GitHubWorkItem[]>([]);
    const [isLoading, setIsLoading] = React.useState(true);
    const [error, setError] = React.useState<string | null>(null);
    const [refreshKey, setRefreshKey] = React.useState(0);
    const [repositoryRetryKey, setRepositoryRetryKey] = React.useState(0);

    React.useEffect(() => {
        let active = true;
        void getRepositories().then((result) => {
            if (!active) return;
            if (result === null) {
                setError("Connected repositories could not be loaded.");
                setIsLoading(false);
            } else {
                setRepositories(result);
                setSelectedId(result.find((repository) => repository.monitoring_enabled)?.id ?? result[0]?.id ?? "");
                if (result.length === 0) setIsLoading(false);
            }
        });
        return () => { active = false; };
    }, [repositoryRetryKey]);

    React.useEffect(() => {
        if (!selectedId) return;
        let active = true;
        async function loadItems() {
            setIsLoading(true);
            setError(null);
            try {
                const result = await listRepositoryWorkItems(selectedId, kind);
                if (active) setItems(result);
            } catch (loadError: unknown) {
                if (active) {
                    setError(loadError instanceof Error ? loadError.message : "GitHub data could not be loaded.");
                    setItems([]);
                }
            } finally {
                if (active) setIsLoading(false);
            }
        }
        void loadItems();
        return () => { active = false; };
    }, [selectedId, kind, refreshKey]);

    const selectedRepository = repositories.find((repository) => repository.id === selectedId);
    const noun = kind === "issues" ? "issues" : "pull requests";

    if (isLoading && repositories.length === 0) {
        return <div className="flex justify-center p-8"><Loader2 className="size-6 animate-spin text-muted-foreground" /></div>;
    }
    if (repositories.length === 0 && !error) {
        return <EmptyState title="No repositories connected" description={`Connect a GitHub repository to load its real ${noun}.`} />;
    }

    return (
        <section className="space-y-4">
            {repositories.length > 0 && (
                <label className="flex items-center gap-3 text-sm">
                    <span className="font-medium">Repository</span>
                    <select
                        aria-label="Select repository"
                        className="h-10 max-w-full rounded-md border bg-background px-3"
                        value={selectedId}
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
                    <Button variant="outline" size="sm" onClick={() => { setIsLoading(true); setError(null); if (selectedId) setRefreshKey((key) => key + 1); else setRepositoryRetryKey((key) => key + 1); }}>Try again</Button>
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
