"use client";

import * as React from "react";
import { GitFork, Loader2 } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/rm/empty-state";
import { SectionHeading } from "@/components/rm/section-heading";
import { Button } from "@/components/ui/button";
import { getConnections } from "@/lib/api/github";
import { getAvailableRepositories, getRepositories } from "@/lib/api/repositories";
import type { GitHubConnection, AvailableRepository, Repository } from "@/lib/types/github";
import { AvailableRepositoryList } from "@/components/repositories/available-repository-list";
import { RepositoryCard } from "@/components/repositories/repository-card";

export default function RepositoriesPage() {
    const [isLoading, setIsLoading] = React.useState(true);
    const [connections, setConnections] = React.useState<GitHubConnection[]>([]);
    const [availableRepos, setAvailableRepos] = React.useState<Record<string, AvailableRepository[]>>({});
    const [persistedRepos, setPersistedRepos] = React.useState<Repository[]>([]);
    const [fetchKey, setFetchKey] = React.useState(0);

    React.useEffect(() => {
        async function fetchData() {
            setIsLoading(true);
            const [fetchedConnections, fetchedPersisted] = await Promise.all([
                getConnections(),
                getRepositories(),
            ]);

            const conns = fetchedConnections ?? [];
            setConnections(conns);

            const availableMap: Record<string, AvailableRepository[]> = {};
            await Promise.all(
                conns.map(async (conn) => {
                    const repos = await getAvailableRepositories(conn.id.toString());
                    if (repos) {
                        availableMap[conn.id.toString()] = repos;
                    }
                })
            );
            setAvailableRepos(availableMap);

            setPersistedRepos(fetchedPersisted ?? []);
            setIsLoading(false);
        }
        fetchData();
    }, [fetchKey]);

    const refetch = () => setFetchKey((k) => k + 1);

    return (
        <div className="space-y-6">
            <SectionHeading
                eyebrow="Workspace"
                title="Repositories"
                description="Manage the repositories that RepoMedic will monitor."
            />
            {isLoading ? (
                <div className="flex justify-center p-8">
                    <Loader2 className="size-6 animate-spin text-muted-foreground" />
                </div>
            ) : connections.length === 0 ? (
                <EmptyState
                    icon={<GitFork className="size-6" aria-hidden="true" />}
                    title="No repositories connected yet"
                    description="Connect a GitHub repository to begin monitoring its health and findings."
                    action={
                        <Button>
                            <Link href="/overview/settings">Connect a repository</Link>
                        </Button>
                    }
                />
            ) : (
                <div className="space-y-12">
                    {persistedRepos.length > 0 && (
                        <div className="space-y-4">
                            <h3 className="text-lg font-medium">Monitored Repositories</h3>
                            <div className="grid gap-4">
                                {persistedRepos.map((repo) => (
                                    <RepositoryCard
                                        key={repo.id}
                                        repository={repo}
                                        onToggle={refetch}
                                    />
                                ))}
                            </div>
                        </div>
                    )}

                    <div className="space-y-8">
                        {connections.map((conn) => (
                            <div key={conn.id} className="space-y-4">
                                {connections.length > 1 && (
                                    <h4 className="font-medium text-muted-foreground">
                                        Connection: {conn.account_login}
                                    </h4>
                                )}
                                <AvailableRepositoryList
                                    connectionId={conn.id.toString()}
                                    repositories={availableRepos[conn.id.toString()] || []}
                                    onAdded={refetch}
                                />
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
