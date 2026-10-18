"use client";

import * as React from "react";
import { useAuth } from "@/lib/auth/use-auth";
import { ContributionReadError, fetchRepositoryContributions } from "@/lib/api/repository-contributions";
import type { RepositoryContributionParams, RepositoryContributions } from "@/lib/types/repository-contributions";

type ReadState = { status: "idle" | "loading" } | { status: "ready"; data: RepositoryContributions }
    | { status: "error"; error: ContributionReadError };

/** Read-model boundary for the upcoming Contributions UI. No prefetch or polling. */
export function useRepositoryContributions(repositoryId: string | null, active: boolean,
    { start, end, cursor, limit }: RepositoryContributionParams = {}, revision = 0): ReadState {
    const { user, isAuthenticated } = useAuth();
    const userId = isAuthenticated ? user?.id : undefined;
    const enabled = active && !!repositoryId && !!userId;
    const key = JSON.stringify([enabled, userId, repositoryId, start, end, cursor, limit, revision]);
    const [result, setResult] = React.useState<{ key: string; state: ReadState }>();
    React.useEffect(() => {
        if (!enabled || !repositoryId) return;
        let activeRequest = true;
        let generation = 0;
        let controller: AbortController | undefined;
        async function read() {
            const request = ++generation;
            controller?.abort();
            controller = new AbortController();
            try {
                const data = await fetchRepositoryContributions(repositoryId!, { start, end, cursor, limit }, controller.signal);
                if (activeRequest && request === generation) setResult({ key, state: { status: "ready", data } });
            } catch (error) {
                if (activeRequest && request === generation) setResult({ key, state: { status: "error",
                    error: error instanceof ContributionReadError ? error : new ContributionReadError("unavailable") } });
            }
        }
        void read();
        window.addEventListener("focus", read);
        return () => { activeRequest = false; controller?.abort(); window.removeEventListener("focus", read); };
    }, [enabled, repositoryId, userId, start, end, cursor, limit, revision, key]);
    return !enabled ? { status: "idle" } : result?.key === key ? result.state : { status: "loading" };
}
