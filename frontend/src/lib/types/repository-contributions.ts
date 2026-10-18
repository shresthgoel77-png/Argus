export type ContributionReadStatus = "available" | "partial" | "pending" | "unsupported" | "unavailable";

export interface RepositoryContributionEvent {
    sha: string;
    message: string | null;
    author: { name: string | null; login: string | null };
    committed_at: string;
    authored_at: string | null;
    html_url: string | null;
    /** Reachable from this branch's pinned head; not an inferred branch of origin. */
    branch: string;
    pull_request: null;
    additions: number | null;
    deletions: number | null;
}

export interface RepositoryContributions {
    repository_id: string;
    status: ContributionReadStatus;
    reason: string | null;
    retry_after_seconds: number | null;
    snapshot_id: string;
    fetched_at: string;
    history_complete: boolean;
    scope: {
        start_date: string; end_date: string; since: string; until: string; timezone: "UTC";
        source: "github_graphql_commit_history"; branch: string | null; head_sha: string | null;
        includes_merges: true; author_coverage: "primary_author"; pull_request_coverage: "unsupported";
        max_commits: number; aggregation: "retrieved_unique_commits";
    };
    /** All retrieved unique commits, independent of the current display page. Partial = subset counts. */
    metrics: {
        commit_count: number; additions: number | null; deletions: number | null;
        distinct_authors: number | null; known_authors: number; unknown_author_commits: number;
    } | null;
    /** UTC daily buckets over the same retrieved set as metrics. Partial zero is not a confirmed zero day. */
    frequency: { date: string; commits: number }[];
    items: RepositoryContributionEvent[];
    next_cursor: string | null;
}

export interface RepositoryContributionParams {
    start?: string;
    end?: string;
    cursor?: string;
    limit?: number;
}
