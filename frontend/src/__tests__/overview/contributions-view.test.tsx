import * as React from "react";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { RepositoryContributionsView } from "@/components/activity/repository-contributions";
import { contributionDiff, contributionMonths, mergeContributionEvents } from "@/components/activity/contribution-presentation";
import { ContributionReadError, fetchRepositoryContributions } from "@/lib/api/repository-contributions";
import type { RepositoryContributions } from "@/lib/types/repository-contributions";
import { contributionEvent, contributionSnapshot } from "../fixtures/repository-contributions";

let userId: string | undefined = "person-a";
vi.mock("@/lib/auth/use-auth", () => ({ useAuth: () => ({ isAuthenticated: !!userId, user: userId ? { id: userId } : undefined }) }));
vi.mock("@/lib/api/repository-contributions", async (original) => ({ ...await original<typeof import("@/lib/api/repository-contributions")>(), fetchRepositoryContributions: vi.fn() }));
beforeEach(() => { vi.resetAllMocks(); userId = "person-a"; vi.mocked(fetchRepositoryContributions).mockResolvedValue(contributionSnapshot()); });
afterEach(() => vi.restoreAllMocks());

it("labels the exact period, branch and coverage; metrics and textual chart use the entire snapshot", async () => {
    render(<RepositoryContributionsView repositoryId="repo-a" />);
    expect(screen.getByLabelText("Loading contribution metrics")).toBeInTheDocument();
    expect(screen.getByLabelText("Loading commit frequency")).toBeInTheDocument();
    expect(screen.getByLabelText("Loading commit timeline")).toBeInTheDocument();
    expect(screen.getByLabelText("Loading contribution metrics").compareDocumentPosition(screen.getByLabelText("Loading commit timeline")) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByLabelText("Loading commit timeline").compareDocumentPosition(screen.getByLabelText("Loading commit frequency")) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(await screen.findByText("Complete history for this window.")).toBeInTheDocument();
    expect(screen.getByText("Jul 21, 2026 – Oct 18, 2026 · UTC")).toBeInTheDocument();
    expect(screen.getByText("Default branch: main · snapshot fffffff")).toBeInTheDocument();
    expect(screen.getByLabelText("Repository contribution metrics")).toHaveTextContent("Commits3");
    expect(screen.getByLabelText("Additions: 24")).toHaveTextContent("+24");
    expect(screen.getByLabelText("Deletions: 6")).toHaveTextContent("−6");
    expect(screen.getByLabelText("Repository contribution metrics")).toHaveTextContent("Active contributors1");
    expect(screen.getByRole("img", { name: /3 commits; daily peak 1/ })).toBeInTheDocument();
    expect(screen.getByText("3 commits across 90 UTC dates.")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Daily commit counts", { exact: true }));
    expect(screen.getByRole("table")).toHaveTextContent("Window counts · UTC · total 3");
    expect(screen.getByText("Showing 2 of 3 retrieved commits.")).toBeInTheDocument();
    const link = screen.getAllByRole("link", { name: "View commit 0000000 on GitHub" })[0];
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByRole("region", { name: "Contribution timeline" })).toHaveTextContent("PR associations and coauthors are not supplied");
    const timeline = screen.getByRole("region", { name: "Contribution timeline" });
    expect(screen.getByLabelText("Repository contribution metrics").compareDocumentPosition(timeline) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(timeline.compareDocumentPosition(screen.getByRole("region", { name: "Commit frequency", exact: true })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

it("loads overlapping pages once, groups months newest first, and never changes summary totals when appending", async () => {
    vi.mocked(fetchRepositoryContributions).mockResolvedValueOnce(contributionSnapshot()).mockResolvedValueOnce(contributionSnapshot("repo-a", {
        items: [contributionEvent(2), contributionEvent(3)], next_cursor: null,
    }));
    render(<RepositoryContributionsView repositoryId="repo-a" />);
    await screen.findByText("Commit 1");
    fireEvent.click(screen.getByRole("button", { name: "Load more commits" }));
    expect(await screen.findByText("Commit 3")).toBeInTheDocument();
    expect(screen.getAllByText("Commit 2")).toHaveLength(1);
    expect(screen.getAllByRole("heading", { level: 5 }).map((element) => element.textContent)).toEqual(["October 2026", "September 2026"]);
    expect(within(screen.getByRole("list", { name: "Commits in October 2026" })).getAllByRole("listitem").map((element) => element.textContent)).toEqual([expect.stringContaining("Commit 1"), expect.stringContaining("Commit 2")]);
    expect(screen.getByText("Showing 3 of 3 retrieved commits.")).toBeInTheDocument();
    expect(screen.getByLabelText("Additions: 24")).toBeInTheDocument();
    expect(fetchRepositoryContributions).toHaveBeenLastCalledWith("repo-a", {
        start: "2026-07-21", end: "2026-10-18", cursor: `${"a".repeat(32)}:2`, limit: 20,
    }, expect.any(AbortSignal));
    expect(screen.queryByRole("button", { name: "Load more commits" })).not.toBeInTheDocument();
});

it("keeps working counts/chart/timeline when lines and author identities are unavailable; labels subset coverage", async () => {
    const data = contributionSnapshot("repo-a", { status: "partial", reason: "scan_limit", history_complete: false });
    data.metrics = { ...data.metrics!, additions: null, deletions: null, distinct_authors: null, known_authors: 1, unknown_author_commits: 1 };
    data.items[0] = contributionEvent(1, { author: { name: null, login: null }, additions: null, deletions: null, html_url: null, message: null });
    vi.mocked(fetchRepositoryContributions).mockResolvedValue(data);
    render(<RepositoryContributionsView repositoryId="repo-a" />);
    expect(await screen.findByText(/Partial history · limited to 500 commits/)).toBeInTheDocument();
    expect(screen.getByLabelText("Repository contribution metrics")).toHaveTextContent("Commits3");
    expect(screen.getByLabelText("Repository contribution metrics")).toHaveTextContent("1 known; 1 commits unattributed");
    expect(screen.getByRole("img", { name: /3 retrieved commits; daily peak 1/ })).toBeInTheDocument();
    expect(screen.getByText(/Zero buckets may have uncovered activity/)).toBeInTheDocument();
    expect(screen.getByText("Commit message unavailable")).toBeInTheDocument();
    expect(screen.getByText(/Author unavailable/)).toBeInTheDocument();
    expect(screen.getByText(/GitHub link unavailable/)).toBeInTheDocument();
    expect(screen.getByText("Diff proportions unavailable")).toBeInTheDocument();
    expect(screen.queryByText("No commits in this period.")).not.toBeInTheDocument();
});

it("distinguishes complete zero, partial zero, provider pending/unsupported/unavailable, and failed requests", async () => {
    const zero = contributionSnapshot("repo-a", { metrics: { commit_count: 0, additions: 0, deletions: 0, distinct_authors: 0, known_authors: 0, unknown_author_commits: 0 },
        frequency: contributionSnapshot().frequency.map((bucket) => ({ ...bucket, commits: 0 })), items: [], next_cursor: null });
    vi.mocked(fetchRepositoryContributions).mockResolvedValueOnce(zero)
        .mockResolvedValueOnce({ ...zero, status: "partial", history_complete: false, reason: "scan_limit" });
    const view = render(<RepositoryContributionsView repositoryId="repo-a" />);
    expect(await screen.findByText("No commits in this period.")).toBeInTheDocument();
    expect(screen.getByLabelText("Additions: 0")).toHaveTextContent("+0");
    fireEvent.click(screen.getByRole("button", { name: "Refresh contributions" }));
    expect(await screen.findByText("No commit records returned. Window coverage may be incomplete.")).toBeInTheDocument();
    view.unmount();
    for (const status of ["pending", "unsupported", "unavailable"] as const) {
        vi.mocked(fetchRepositoryContributions).mockResolvedValueOnce(contributionSnapshot("repo-a", { status, history_complete: false, metrics: null, frequency: [], items: [], next_cursor: null, retry_after_seconds: status === "pending" ? 30 : null }));
        const instance = render(<RepositoryContributionsView repositoryId="repo-a" />);
        await screen.findByText("Commit frequency unavailable.");
        expect(screen.queryByText("No commits in this period.")).not.toBeInTheDocument();
        expect(screen.queryByLabelText("Additions: 0")).not.toBeInTheDocument();
        if (status === "pending") expect(screen.getByText("Try again in 30 seconds.")).toBeInTheDocument();
        instance.unmount();
    }
    vi.mocked(fetchRepositoryContributions).mockRejectedValueOnce(new ContributionReadError("unavailable")).mockResolvedValueOnce(zero);
    render(<RepositoryContributionsView repositoryId="repo-a" />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Contributions are temporarily unavailable");
    fireEvent.click(screen.getByRole("button", { name: "Retry contributions" }));
    expect(await screen.findByText("No commits in this period.")).toBeInTheDocument();
});

it("preserves rows on page errors, retries the same cursor, and reloads page one after expiry", async () => {
    vi.mocked(fetchRepositoryContributions).mockResolvedValueOnce(contributionSnapshot())
        .mockRejectedValueOnce(new ContributionReadError("unavailable"))
        .mockRejectedValueOnce(new ContributionReadError("snapshot_expired"))
        .mockResolvedValueOnce(contributionSnapshot("repo-a", { snapshot_id: "b".repeat(32), items: [contributionEvent(3)], next_cursor: null }));
    render(<RepositoryContributionsView repositoryId="repo-a" />);
    await screen.findByText("Commit 1");
    fireEvent.click(screen.getByRole("button", { name: "Load more commits" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("More commits could not be loaded");
    expect(screen.getByText("Commit 1")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /3 commits; daily peak 1/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry loading commits" }));
    expect(await screen.findByRole("button", { name: "Reload contributions" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Load more commits" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reload contributions" }));
    expect(await screen.findByText("Commit 3")).toBeInTheDocument();
    expect(screen.queryByText("Commit 1")).not.toBeInTheDocument();
    expect(fetchRepositoryContributions).toHaveBeenLastCalledWith("repo-a", { start: undefined, end: undefined, cursor: undefined, limit: undefined }, expect.any(AbortSignal));
});

it("rejects a changed snapshot or repeated cursor without mixing events", async () => {
    for (const overrides of [{ snapshot_id: "b".repeat(32) }, { next_cursor: `${"a".repeat(32)}:2` }]) {
        vi.mocked(fetchRepositoryContributions).mockResolvedValueOnce(contributionSnapshot()).mockResolvedValueOnce(contributionSnapshot("repo-a", { ...overrides, items: [contributionEvent(3)] }));
        const instance = render(<RepositoryContributionsView repositoryId="repo-a" />);
        await screen.findByText("Commit 1");
        fireEvent.click(screen.getByRole("button", { name: "Load more commits" }));
        await screen.findByRole("alert");
        expect(screen.queryByText("Commit 3")).not.toBeInTheDocument();
        expect(screen.getByText("Commit 1")).toBeInTheDocument();
        instance.unmount();
    }
});

it("hides old repository/account data immediately and ignores late initial or pagination responses", async () => {
    let finishA!: (data: RepositoryContributions) => void;
    let finishMore!: (data: RepositoryContributions) => void;
    vi.mocked(fetchRepositoryContributions).mockImplementationOnce(() => new Promise((resolve) => { finishA = resolve; }))
        .mockResolvedValueOnce(contributionSnapshot("repo-b", { items: [contributionEvent(2)] }))
        .mockImplementationOnce(() => new Promise((resolve) => { finishMore = resolve; }))
        .mockResolvedValue(contributionSnapshot("repo-c", { items: [contributionEvent(3)], next_cursor: null }));
    const view = render(<RepositoryContributionsView repositoryId="repo-a" />);
    view.rerender(<RepositoryContributionsView repositoryId="repo-b" />);
    await screen.findByText("Commit 2");
    fireEvent.click(screen.getByRole("button", { name: "Load more commits" }));
    view.rerender(<RepositoryContributionsView repositoryId="repo-c" />);
    expect(screen.queryByText("Commit 2")).not.toBeInTheDocument();
    await screen.findByText("Commit 3");
    await act(async () => { finishA(contributionSnapshot()); finishMore(contributionSnapshot("repo-b", { items: [contributionEvent(1)] })); });
    expect(screen.queryByText("Commit 1")).not.toBeInTheDocument();
    userId = "person-b";
    view.rerender(<RepositoryContributionsView repositoryId="repo-c" />);
    expect(screen.queryByText("Commit 3")).not.toBeInTheDocument();
    await screen.findByText("Commit 3");
    userId = undefined;
    view.rerender(<RepositoryContributionsView repositoryId="repo-c" />);
    expect(screen.queryByText("Commit 3")).not.toBeInTheDocument();
    expect(screen.getByText("Sign in to view repository contributions.")).toBeInTheDocument();
});

it("uses UTC year/month groups, proportional diff lengths, exact zero and safe long plain text", async () => {
    expect(contributionDiff(8, 2)).toEqual({ additions: 80, deletions: 20 });
    expect(contributionDiff(0, 0)).toEqual({ additions: 0, deletions: 0 });
    expect(contributionDiff(null, 2)).toBeNull();
    expect(mergeContributionEvents([contributionEvent(1)], [contributionEvent(1)])).toHaveLength(1);
    expect(contributionMonths([contributionEvent(1, { committed_at: "2025-12-31T23:59:00Z" }), contributionEvent(2, { committed_at: "2026-01-01T00:00:00Z" })]).map((month) => month.label)).toEqual(["January 2026", "December 2025"]);
    const message = `<script>alert('plain text')</script>${"long".repeat(100)}\n\nA detailed commit message.`;
    vi.mocked(fetchRepositoryContributions).mockResolvedValue(contributionSnapshot("repo-a", { items: [contributionEvent(1, { message })], next_cursor: null }));
    render(<RepositoryContributionsView repositoryId="repo-a" />);
    await screen.findByText(message.split("\n")[0]);
    fireEvent.click(screen.getByText("Full commit message"));
    expect(screen.getByText(/A detailed commit message\./)).toBeInTheDocument();
    const diff = screen.getByRole("img", { name: /8 additions, 2 deletions/ });
    expect(diff.children[0]).toHaveStyle({ width: "80%" });
    expect(diff.children[1]).toHaveStyle({ width: "20%" });
    expect(document.querySelector("script")).toBeNull();
});
