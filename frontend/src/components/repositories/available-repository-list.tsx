"use client";

import * as React from "react";
import { AvailableRepository } from "@/lib/types/github";
import { Button } from "@/components/ui/button";
import { addRepository } from "@/lib/api/repositories";

export interface AvailableRepositoryListProps {
    connectionId: string;
    repositories: AvailableRepository[];
    onAdded: () => void;
}

export function AvailableRepositoryList({
    connectionId,
    repositories,
    onAdded,
}: AvailableRepositoryListProps) {
    const [addingIds, setAddingIds] = React.useState<Set<number>>(new Set());

    const handleAdd = async (githubRepoId: number) => {
        setAddingIds((prev) => new Set(prev).add(githubRepoId));
        await addRepository({
            connection_id: connectionId,
            github_repo_id: githubRepoId,
        });
        setAddingIds((prev) => {
            const next = new Set(prev);
            next.delete(githubRepoId);
            return next;
        });
        onAdded();
    };

    if (repositories.length === 0) {
        return <div className="text-sm text-muted-foreground p-4">No available repositories found for this connection.</div>;
    }

    return (
        <div className="space-y-4 pt-4">
            <h3 className="text-lg font-medium">Available Repositories</h3>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {repositories.map((repo) => {
                    const isAdding = addingIds.has(repo.github_repo_id);

                    return (
                        <div
                            key={repo.github_repo_id}
                            className="flex flex-col gap-3 rounded-lg border bg-card p-4 transition-all"
                        >
                            <div className="flex flex-1 flex-col gap-1">
                                <span className="font-semibold">{repo.full_name}</span>
                                {repo.private && (
                                    <span className="text-xs text-muted-foreground">Private</span>
                                )}
                            </div>
                            <Button
                                variant={repo.already_added ? "secondary" : "default"}
                                onClick={() => handleAdd(repo.github_repo_id)}
                                disabled={repo.already_added || isAdding}
                            >
                                {repo.already_added ? "Added" : isAdding ? "Adding..." : "Add"}
                            </Button>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
