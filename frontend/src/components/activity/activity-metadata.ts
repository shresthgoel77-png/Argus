import { getClerkAuthorizationHeaders } from "@/lib/auth/clerk-token";
import type { Repository } from "@/lib/types/github";

export interface ActivityMetadata {
    repository_id: string;
    metadata_status: "available" | "unavailable";
    primary_language_status: "known" | "none" | "unknown";
    primary_language: string | null;
    description: string | null;
    topics: string[] | null;
    stars: number | null;
    forks: number | null;
    open_issues_and_pull_requests: number | null;
    updated_at: string | null;
    languages_status: "available" | "unavailable";
    language_bytes: Record<string, number> | null;
    fetched_at: string | null;
}

export function unavailableMetadata(id: string): ActivityMetadata {
    return { repository_id: id, metadata_status: "unavailable", primary_language_status: "unknown", primary_language: null,
        description: null, topics: null, stars: null, forks: null, open_issues_and_pull_requests: null,
        updated_at: null, languages_status: "unavailable", language_bytes: null, fetched_at: null };
}

const count = (value: unknown) => typeof value === "number" && Number.isSafeInteger(value) && value >= 0 ? value : null;
const date = (value: unknown) => typeof value === "string" && Number.isFinite(Date.parse(value)) ? value : null;

export function parseActivityMetadata(value: unknown, id: string): ActivityMetadata {
    const result = unavailableMetadata(id);
    if (!value || typeof value !== "object" || !("repository_id" in value) || value.repository_id !== id) return result;
    const data = value as Record<string, unknown>;
    if (data.metadata_status === "available") {
        result.metadata_status = "available";
        if (data.primary_language_status === "known" && typeof data.primary_language === "string" && data.primary_language.trim()) {
            result.primary_language_status = "known";
            result.primary_language = data.primary_language;
        } else if (data.primary_language_status === "none" && data.primary_language === null) result.primary_language_status = "none";
        result.description = typeof data.description === "string" ? data.description : null;
        result.topics = Array.isArray(data.topics) && data.topics.every((topic) => typeof topic === "string") ? data.topics : null;
        result.stars = count(data.stars);
        result.forks = count(data.forks);
        result.open_issues_and_pull_requests = count(data.open_issues_and_pull_requests);
        result.updated_at = date(data.updated_at);
    }
    if (data.languages_status === "available" && data.language_bytes && typeof data.language_bytes === "object" && !Array.isArray(data.language_bytes)) {
        const entries = Object.entries(data.language_bytes);
        if (entries.every(([name, size]) => name.length > 0 && count(size) !== null)
            && Number.isSafeInteger(entries.reduce((sum, [, size]) => sum + (size as number), 0))) {
            result.languages_status = "available";
            result.language_bytes = Object.fromEntries(entries);
        }
    }
    result.fetched_at = date(data.fetched_at);
    return result;
}

export async function fetchActivityMetadata(repository: Repository): Promise<ActivityMetadata> {
    try {
        const headers = await getClerkAuthorizationHeaders();
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/repositories/${encodeURIComponent(repository.id)}/activity-metadata`, {
            headers, credentials: "include", cache: "no-store",
        });
        return response.ok ? parseActivityMetadata(await response.json(), repository.id) : unavailableMetadata(repository.id);
    } catch { return unavailableMetadata(repository.id); }
}

export const metadataKey = (repository: Repository) => `${repository.id}:${repository.full_name}`;

/** Instance-local cache: cannot survive logout/unmount into another user's workspace. */
export function createActivityMetadataLoader(fetcher = fetchActivityMetadata) {
    const cache = new Map<string, { promise: Promise<ActivityMetadata>; expires: number; pending: boolean }>();
    const queue: (() => Promise<void>)[] = [];
    let running = 0;
    let scope: Set<string> | null = null;
    function drain() {
        while (running < 4 && queue.length) {
            const job = queue.shift()!;
            running++;
            void job().finally(() => { running--; drain(); });
        }
    }
    return {
        setScope(repositories: Repository[]) { scope = new Set(repositories.map(metadataKey)); },
        invalidate() { for (const [key, entry] of cache) if (!entry.pending) cache.delete(key); },
        load(repository: Repository) {
            const key = metadataKey(repository);
            const existing = cache.get(key);
            if (existing && existing.expires > Date.now()) return existing.promise;
            let finish!: (value: ActivityMetadata) => void;
            const promise = new Promise<ActivityMetadata>((resolve) => { finish = resolve; });
            const entry = { promise, expires: Infinity, pending: true };
            cache.set(key, entry);
            queue.push(async () => {
                let result = unavailableMetadata(repository.id);
                try { if (!scope || scope.has(key)) result = await fetcher(repository); }
                catch { /* One failed repository leaves the remaining queue usable. */ }
                entry.pending = false;
                entry.expires = Date.now() + (result.primary_language_status === "unknown" || result.languages_status !== "available" ? 15_000 : 60_000);
                finish(result);
                if (cache.size > 512) for (const [oldKey, old] of cache) {
                    if (!old.pending && oldKey !== key) cache.delete(oldKey);
                    if (cache.size <= 512) break;
                }
            });
            drain();
            return promise;
        },
    };
}

const knownColors: Record<string, string> = { TypeScript: "#3178c6", JavaScript: "#c4a600", Python: "#3572a5", Java: "#b07219", Go: "#008da8", Rust: "#a85b32", Ruby: "#ad2424", CSS: "#663399", HTML: "#d94a23", Shell: "#638c25", C: "#555555", "C++": "#d4558d" };
export function languageColor(name: string): string {
    if (Object.hasOwn(knownColors, name)) return knownColors[name];
    let hash = 0;
    for (const character of name) hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
    return `hsl(${hash % 360} 55% 43%)`;
}

export interface LanguageSegment { key: string; label: string; count: number; percentage: number; color: string }
export function primaryLanguageDistribution(repositories: Repository[], metadata: Record<string, ActivityMetadata | undefined>) {
    const unique = [...new Map(repositories.map((repository) => [repository.id, repository])).values()];
    const groups = new Map<string, { label: string; count: number; color: string }>();
    let known = 0;
    for (const repository of unique) {
        const item = metadata[repository.id];
        const status = item?.metadata_status === "available" ? item.primary_language_status : "unknown";
        const language = status === "known" ? item?.primary_language : null;
        const key = language ? `language:${language}` : status === "none" ? "none" : "unknown";
        if (key !== "unknown") known++;
        const group = groups.get(key) ?? { label: language ?? (key === "none" ? "No primary language" : "Unknown"), count: 0, color: language ? languageColor(language) : key === "none" ? "#cbd5e1" : "#64748b" };
        group.count++;
        groups.set(key, group);
    }
    const rows: LanguageSegment[] = [...groups.entries()].map(([key, group]) => ({ key, ...group, percentage: group.count / unique.length * 100 }))
        .sort((a, b) => (a.key === "unknown" ? 1 : b.key === "unknown" ? -1 : b.count - a.count || a.label.localeCompare(b.label)));
    return { total: unique.length, known, rows };
}

export function byteLanguageDistribution(metadata: ActivityMetadata): LanguageSegment[] {
    if (metadata.languages_status !== "available" || !metadata.language_bytes) return [];
    const total = Object.values(metadata.language_bytes).reduce((sum, size) => sum + size, 0);
    return Object.entries(metadata.language_bytes).filter(([, size]) => size > 0)
        .map(([name, size]) => ({ key: name, label: name, count: size, percentage: size / total * 100, color: languageColor(name) }))
        .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}
