import type { RepositoryContributionEvent } from "@/lib/types/repository-contributions";

export function contributionDate(value: string, withTime = false) {
    return new Date(value).toLocaleString("en-US", {
        timeZone: "UTC", year: "numeric", month: "short", day: "numeric",
        ...(withTime ? { hour: "2-digit", minute: "2-digit", hour12: false } as const : {}),
    }) + (withTime ? " UTC" : "");
}

export function mergeContributionEvents(...pages: RepositoryContributionEvent[][]) {
    const unique = new Map<string, RepositoryContributionEvent>();
    for (const event of pages.flat()) if (!unique.has(event.sha)) unique.set(event.sha, event);
    return [...unique.values()].sort((a, b) => Date.parse(b.committed_at) - Date.parse(a.committed_at)
        || b.sha.localeCompare(a.sha));
}

export function contributionMonths(items: RepositoryContributionEvent[]) {
    const groups = new Map<string, { key: string; label: string; items: RepositoryContributionEvent[] }>();
    for (const item of mergeContributionEvents(items)) {
        const key = new Date(item.committed_at).toISOString().slice(0, 7);
        if (!groups.has(key)) groups.set(key, { key, label: new Date(item.committed_at).toLocaleString("en-US", {
            timeZone: "UTC", month: "long", year: "numeric",
        }), items: [] });
        groups.get(key)!.items.push(item);
    }
    return [...groups.values()];
}

export function contributionDiff(additions: number | null, deletions: number | null) {
    if (additions === null || deletions === null) return null;
    const total = additions + deletions;
    return { additions: total ? additions / total * 100 : 0, deletions: total ? deletions / total * 100 : 0 };
}
