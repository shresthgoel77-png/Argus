import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ContributionReadError, fetchRepositoryContributions, parseRepositoryContributions } from "@/lib/api/repository-contributions";
import { useRepositoryContributions } from "@/components/activity/use-repository-contributions";
import { getClerkAuthorizationHeaders } from "@/lib/auth/clerk-token";
import type { RepositoryContributions } from "@/lib/types/repository-contributions";

let userId: string | undefined = "user-a";
vi.mock("@/lib/auth/use-auth", () => ({ useAuth: () => ({ isAuthenticated: !!userId, user: userId ? { id: userId } : undefined }) }));
vi.mock("@/lib/auth/clerk-token", () => ({ getClerkAuthorizationHeaders: vi.fn() }));

function fixture(repositoryId = "repo-a"): RepositoryContributions {
    return {
        repository_id: repositoryId, status: "available", reason: null, retry_after_seconds: null,
        snapshot_id: "a".repeat(32), fetched_at: "2026-10-19T03:00:00+00:00", history_complete: true,
        scope: { start_date: "2026-10-01", end_date: "2026-10-02", since: "2026-10-01T00:00:00+00:00",
            until: "2026-10-02T23:59:59+00:00", timezone: "UTC", source: "github_graphql_commit_history",
            branch: "main", head_sha: "f".repeat(40), includes_merges: true, author_coverage: "primary_author",
            pull_request_coverage: "unsupported", max_commits: 500, aggregation: "retrieved_unique_commits" },
        metrics: { commit_count: 0, additions: 0, deletions: 0, distinct_authors: 0, known_authors: 0, unknown_author_commits: 0 },
        frequency: [{ date: "2026-10-01", commits: 0 }, { date: "2026-10-02", commits: 0 }], items: [], next_cursor: null,
    };
}

beforeEach(() => {
    vi.resetAllMocks();
    userId = "user-a";
    vi.mocked(getClerkAuthorizationHeaders).mockResolvedValue({ Authorization: "Bearer fixture-clerk" });
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it("reads only the authenticated local endpoint with explicit range and pagination", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(fixture())));
    vi.stubGlobal("fetch", fetcher);
    const result = await fetchRepositoryContributions("repo-a", { start: "2026-10-01", end: "2026-10-02", cursor: "snapshot:20", limit: 10 });
    const [url, options] = fetcher.mock.calls[0];
    expect(url).toContain("/api/v1/repositories/repo-a/contributions?");
    expect(new URL(url).searchParams.get("cursor")).toBe("snapshot:20");
    expect(new URL(url).searchParams.get("limit")).toBe("10");
    expect(options).toMatchObject({ credentials: "include", cache: "no-store", headers: { Authorization: "Bearer fixture-clerk" } });
    expect(result.metrics?.commit_count).toBe(0);
    expect(url).not.toContain("api.github.com");
});

it("keeps provider pending, partial, unsupported and unavailable distinct from genuine zero", () => {
    expect(parseRepositoryContributions(fixture(), "repo-a").metrics?.additions).toBe(0);
    for (const status of ["pending", "unsupported", "unavailable"] as const) {
        const data = { ...fixture(), status, metrics: null, frequency: [], history_complete: false };
        expect(parseRepositoryContributions(data, "repo-a").status).toBe(status);
        expect(parseRepositoryContributions(data, "repo-a").metrics).toBeNull();
    }
    const partial = { ...fixture(), status: "partial", reason: "scan_limit", history_complete: false };
    expect(parseRepositoryContributions(partial, "repo-a").history_complete).toBe(false);
    expect(parseRepositoryContributions(partial, "repo-a").scope.aggregation).toBe("retrieved_unique_commits");
});

it("rejects wrong repositories, incompatible totals, fake completeness and malformed fields", () => {
    for (const data of [null, { ...fixture(), repository_id: "other" }, { ...fixture(), history_complete: false },
        { ...fixture(), status: "pending" }, { ...fixture(), metrics: { ...fixture().metrics, commit_count: 2 } },
        { ...fixture(), frequency: [] }, { ...fixture(), frequency: [{ date: "2026-10-01", commits: -1 }] },
        { ...fixture(), scope: { ...fixture().scope, source: "webhook_events" } },
        { ...fixture(), items: [{ sha: "bad" }] }]) {
        expect(() => parseRepositoryContributions(data, "repo-a")).toThrow(ContributionReadError);
    }
});

it("validates page events while keeping metrics and buckets scoped to the whole retrieved snapshot", () => {
    const data = fixture();
    data.metrics = { commit_count: 2, additions: 10, deletions: 4, distinct_authors: 1, known_authors: 1, unknown_author_commits: 0 };
    data.frequency[1].commits = 2;
    data.items = [{ sha: "b".repeat(40), message: "A real message", author: { name: "Person", login: "person" },
        committed_at: "2026-10-02T01:00:00+00:00", authored_at: "2026-09-30T01:00:00+00:00",
        html_url: `https://github.com/acme/repo/commit/${"b".repeat(40)}`, branch: "main", pull_request: null, additions: 5, deletions: 2 }];
    data.next_cursor = `${data.snapshot_id}:1`;
    expect(parseRepositoryContributions(data, "repo-a").metrics?.commit_count).toBe(2);
    expect(parseRepositoryContributions(data, "repo-a").items).toHaveLength(1);
    data.status = "partial";
    data.metrics.additions = null;
    data.metrics.distinct_authors = null;
    data.metrics.unknown_author_commits = 1;
    data.items[0].additions = null;
    expect(parseRepositoryContributions(data, "repo-a").metrics?.additions).toBeNull();
    data.items[0].html_url = "https://evil.example/commit/1";
    expect(() => parseRepositoryContributions(data, "repo-a")).toThrow(ContributionReadError);
});

it("returns actionable errors for auth, revoked scope, expired snapshots and invalid ranges", async () => {
    for (const [status, code] of [[401, "authentication"], [404, "not_found"], [409, "snapshot_expired"],
        [422, "invalid_range"], [503, "unavailable"]] as const) {
        vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("private provider detail", { status })));
        await expect(fetchRepositoryContributions("repo-a")).rejects.toMatchObject({ code, message: code });
    }
});

it("gates reads on active Contributions, selection and login; does not prefetch inactive views", async () => {
    const fetcher = vi.fn().mockImplementation(async () => new Response(JSON.stringify(fixture())));
    vi.stubGlobal("fetch", fetcher);
    const { result, rerender } = renderHook(({ active, repositoryId }) => useRepositoryContributions(repositoryId, active),
        { initialProps: { active: false, repositoryId: "repo-a" as string | null } });
    expect(result.current.status).toBe("idle");
    expect(fetcher).not.toHaveBeenCalled();
    rerender({ active: true, repositoryId: null });
    expect(fetcher).not.toHaveBeenCalled();
    userId = undefined;
    rerender({ active: true, repositoryId: "repo-a" });
    expect(result.current.status).toBe("idle");
    userId = "user-a";
    rerender({ active: true, repositoryId: "repo-a" });
    await waitFor(() => expect(result.current.status).toBe("ready"));
    expect(fetcher).toHaveBeenCalledTimes(1);
    rerender({ active: false, repositoryId: "repo-a" });
    act(() => window.dispatchEvent(new Event("focus")));
    expect(result.current.status).toBe("idle");
    expect(fetcher).toHaveBeenCalledTimes(1);
});

it("isolates repository/account/range/cursor changes and ignores out-of-order results", async () => {
    const pending: { url: string; resolve: (value: Response) => void }[] = [];
    vi.stubGlobal("fetch", vi.fn((url: string) => new Promise<Response>((resolve) => pending.push({ url, resolve }))));
    const { result, rerender } = renderHook(({ repo, cursor, start, revision }) =>
        useRepositoryContributions(repo, true, { cursor, start }, revision),
    { initialProps: { repo: "repo-a", cursor: undefined as string | undefined, start: undefined as string | undefined, revision: 0 } });
    await waitFor(() => expect(pending).toHaveLength(1));
    rerender({ repo: "repo-b", cursor: undefined, start: undefined, revision: 0 });
    expect(result.current.status).toBe("loading");
    await waitFor(() => expect(pending).toHaveLength(2));
    await act(async () => pending[1].resolve(new Response(JSON.stringify(fixture("repo-b")))));
    expect(result.current.status).toBe("ready");
    await act(async () => pending[0].resolve(new Response(JSON.stringify(fixture()))));
    expect(result.current.status === "ready" && result.current.data.repository_id).toBe("repo-b");
    userId = "user-b";
    rerender({ repo: "repo-b", cursor: undefined, start: undefined, revision: 0 });
    expect(result.current.status).toBe("loading");
    await waitFor(() => expect(pending).toHaveLength(3));
    rerender({ repo: "repo-b", cursor: "snapshot:20", start: "2026-10-01", revision: 0 });
    await waitFor(() => expect(pending).toHaveLength(4));
    expect(pending[3].url).toContain("cursor=snapshot%3A20");
    await act(async () => pending[3].resolve(new Response("", { status: 409 })));
    expect(result.current.status === "error" && result.current.error.code).toBe("snapshot_expired");
    rerender({ repo: "repo-b", cursor: undefined, start: undefined, revision: 1 });
    expect(result.current.status).toBe("loading");
    await waitFor(() => expect(pending).toHaveLength(5));
    await act(async () => pending[4].resolve(new Response(JSON.stringify(fixture("repo-b")))));
    expect(result.current.status).toBe("ready");
    act(() => window.dispatchEvent(new Event("focus")));
    await waitFor(() => expect(pending).toHaveLength(6));
});
