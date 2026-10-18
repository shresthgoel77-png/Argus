import { getClerkAuthorizationHeaders } from "@/lib/auth/clerk-token";
import type { RepositoryContributionParams, RepositoryContributions } from "@/lib/types/repository-contributions";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ContributionReadError extends Error {
    constructor(public readonly code: "authentication" | "not_found" | "snapshot_expired" | "invalid_range" | "unavailable") {
        super(code);
    }
}

const count = (value: unknown) => Number.isSafeInteger(value) && (value as number) >= 0;
const nullableCount = (value: unknown) => value === null || count(value);
const nullableString = (value: unknown) => value === null || typeof value === "string";
const date = (value: unknown) => typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)
    && Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value;
const timestamp = (value: unknown) => typeof value === "string" && Number.isFinite(Date.parse(value));

/** Reject broken contracts rather than manufacturing zero or complete coverage. */
export function parseRepositoryContributions(value: unknown, repositoryId: string): RepositoryContributions {
    const data = value as RepositoryContributions;
    const scope = data?.scope;
    const metrics = data?.metrics;
    const hasData = data?.status === "available" || data?.status === "partial";
    if (!data || data.repository_id !== repositoryId
        || !["available", "partial", "pending", "unsupported", "unavailable"].includes(data.status)
        || !nullableString(data.reason) || !nullableCount(data.retry_after_seconds)
        || typeof data.snapshot_id !== "string" || !/^[a-f0-9]{32}$/.test(data.snapshot_id)
        || !timestamp(data.fetched_at) || typeof data.history_complete !== "boolean"
        || (data.status === "available" && !data.history_complete)
        || !scope || !date(scope.start_date) || !date(scope.end_date) || scope.start_date > scope.end_date
        || !timestamp(scope.since) || !timestamp(scope.until) || Date.parse(scope.since) > Date.parse(scope.until)
        || Date.parse(scope.end_date) - Date.parse(scope.start_date) > 89 * 86400000
        || scope.timezone !== "UTC" || scope.source !== "github_graphql_commit_history"
        || scope.aggregation !== "retrieved_unique_commits" || !nullableString(scope.branch)
        || !nullableString(scope.head_sha) || scope.includes_merges !== true
        || scope.author_coverage !== "primary_author" || scope.pull_request_coverage !== "unsupported"
        || !count(scope.max_commits) || !nullableString(data.next_cursor)
        || (data.next_cursor !== null && !/^[a-f0-9]{32}:[1-9]\d*$/.test(data.next_cursor))
        || !Array.isArray(data.items) || data.items.length > 100 || !Array.isArray(data.frequency)
        || (hasData ? !metrics : metrics !== null || data.items.length !== 0 || data.frequency.length !== 0)) {
        throw new ContributionReadError("unavailable");
    }
    if (metrics && (!count(metrics.commit_count) || metrics.commit_count > scope.max_commits
        || !nullableCount(metrics.additions) || !nullableCount(metrics.deletions)
        || !nullableCount(metrics.distinct_authors) || !count(metrics.known_authors)
        || !count(metrics.unknown_author_commits) || data.items.length > metrics.commit_count
        || metrics.known_authors > metrics.commit_count || metrics.unknown_author_commits > metrics.commit_count
        || (metrics.distinct_authors !== null && metrics.distinct_authors !== metrics.known_authors)
        || (data.status === "available" && (metrics.additions === null || metrics.deletions === null
            || metrics.distinct_authors === null || metrics.unknown_author_commits !== 0))
        || data.frequency.length !== (Date.parse(scope.end_date) - Date.parse(scope.start_date)) / 86400000 + 1
        || data.frequency.some((bucket) => !date(bucket.date) || !count(bucket.commits)
            || bucket.date < scope.start_date || bucket.date > scope.end_date)
        || new Set(data.frequency.map((bucket) => bucket.date)).size !== data.frequency.length
        || data.frequency.reduce((sum, bucket) => sum + bucket.commits, 0) !== metrics.commit_count)) {
        throw new ContributionReadError("unavailable");
    }
    if (new Set(data.items.map((item) => item.sha)).size !== data.items.length
        || data.items.some((item, index) => !/^[a-f0-9]{40,64}$/.test(item.sha)
            || !nullableString(item.message) || !item.author || !nullableString(item.author.name)
            || !nullableString(item.author.login) || !timestamp(item.committed_at)
            || (item.authored_at !== null && !timestamp(item.authored_at))
            || !nullableString(item.html_url) || (item.html_url !== null && !item.html_url.startsWith("https://github.com/"))
            || item.branch !== scope.branch || item.pull_request !== null
            || !nullableCount(item.additions) || !nullableCount(item.deletions)
            || Date.parse(item.committed_at) < Date.parse(scope.since)
            || Date.parse(item.committed_at) > Date.parse(scope.until)
            || (index > 0 && Date.parse(data.items[index - 1].committed_at) < Date.parse(item.committed_at)))) {
        throw new ContributionReadError("unavailable");
    }
    return data;
}

export async function fetchRepositoryContributions(repositoryId: string, params: RepositoryContributionParams = {}, signal?: AbortSignal) {
    const query = new URLSearchParams();
    if (params.start) query.set("start", params.start);
    if (params.end) query.set("end", params.end);
    if (params.cursor) query.set("cursor", params.cursor);
    if (params.limit !== undefined) query.set("limit", String(params.limit));
    const response = await fetch(`${API_URL}/api/v1/repositories/${encodeURIComponent(repositoryId)}/contributions?${query}`, {
        headers: await getClerkAuthorizationHeaders(), credentials: "include", cache: "no-store", signal,
    });
    if (!response.ok) {
        throw new ContributionReadError(response.status === 401 ? "authentication" : response.status === 404 ? "not_found"
            : response.status === 409 ? "snapshot_expired" : response.status === 422 ? "invalid_range" : "unavailable");
    }
    return parseRepositoryContributions(await response.json(), repositoryId);
}
