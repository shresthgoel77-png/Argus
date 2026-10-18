"use client";

import * as React from "react";
import type { Repository } from "@/lib/types/github";
import { createActivityMetadataLoader, metadataKey, type ActivityMetadata } from "./activity-metadata";

export function useActivityMetadata(repositories: Repository[], revision: number) {
    const [loader] = React.useState(createActivityMetadataLoader);
    const previousRevision = React.useRef(revision);
    const [results, setResults] = React.useState<Record<string, { key: string; revision: number; data: ActivityMetadata }>>({});
    React.useEffect(() => {
        let active = true;
        if (previousRevision.current !== revision) loader.invalidate();
        previousRevision.current = revision;
        loader.setScope(repositories);
        for (const repository of repositories) {
            void loader.load(repository).then((data) => {
                if (active) setResults((previous) => ({ ...previous, [repository.id]: { key: metadataKey(repository), revision, data } }));
            });
        }
        return () => { active = false; loader.setScope([]); };
    }, [loader, repositories, revision]);
    return Object.fromEntries(repositories.map((repository) => {
        const result = results[repository.id];
        return [repository.id, result?.revision === revision && result.key === metadataKey(repository) ? result.data : undefined];
    })) as Record<string, ActivityMetadata | undefined>;
}
