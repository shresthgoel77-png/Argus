import type { RepositoryContributionEvent, RepositoryContributions } from "@/lib/types/repository-contributions";

export function contributionEvent(index: number, overrides: Partial<RepositoryContributionEvent> = {}): RepositoryContributionEvent {
    return { sha: index.toString(16).padStart(40, "0"), message: `Commit ${index}`, author: { name: "Contributor", login: "octocat" },
        committed_at: index === 3 ? "2026-09-30T23:00:00+00:00" : `2026-10-${index === 1 ? "18" : "17"}T12:00:00+00:00`,
        authored_at: null, html_url: `https://github.com/acme/alpha/commit/${index.toString(16).padStart(40, "0")}`,
        branch: "main", pull_request: null, additions: 8, deletions: 2, ...overrides };
}

export function contributionSnapshot(repositoryId = "repo-a", overrides: Partial<RepositoryContributions> = {}): RepositoryContributions {
    const frequency = [];
    for (let time = Date.parse("2026-07-21T00:00:00Z"); time <= Date.parse("2026-10-18T00:00:00Z"); time += 86400000) {
        const date = new Date(time).toISOString().slice(0, 10);
        frequency.push({ date, commits: ["2026-09-30", "2026-10-17", "2026-10-18"].includes(date) ? 1 : 0 });
    }
    return { repository_id: repositoryId, status: "available", reason: null, retry_after_seconds: null,
        snapshot_id: "a".repeat(32), fetched_at: "2026-10-18T23:00:00+00:00", history_complete: true,
        scope: { start_date: "2026-07-21", end_date: "2026-10-18", since: "2026-07-21T00:00:00+00:00", until: "2026-10-18T23:00:00+00:00",
            timezone: "UTC", source: "github_graphql_commit_history", branch: "main", head_sha: "f".repeat(40), includes_merges: true,
            author_coverage: "primary_author", pull_request_coverage: "unsupported", max_commits: 500, aggregation: "retrieved_unique_commits" },
        metrics: { commit_count: 3, additions: 24, deletions: 6, distinct_authors: 1, known_authors: 1, unknown_author_commits: 0 },
        frequency, items: [contributionEvent(1), contributionEvent(2)], next_cursor: `${"a".repeat(32)}:2`, ...overrides };
}
