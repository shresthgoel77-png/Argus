import * as React from "react";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import ActivityPage from "@/app/(app)/overview/activity/page";
import { githubRepositoryUrl, readWorkspaceSelection } from "@/components/activity/workspace-selection";
import { getRepositories } from "@/lib/api/repositories";
import { listRepositoryWorkItems } from "@/lib/api/repository-work-items";
import { listRepositoryActivity } from "@/lib/api/activity";
import type { Repository } from "@/lib/types/github";
import { fetchRepositoryContributions } from "@/lib/api/repository-contributions";
import { contributionSnapshot } from "../fixtures/repository-contributions";

// Model Next's documented native-history integration without a router/server.
vi.mock("next/navigation", () => ({
    useSearchParams: () => {
        const search = React.useSyncExternalStore((notify) => {
            window.addEventListener("popstate", notify);
            return () => window.removeEventListener("popstate", notify);
        }, () => window.location.search);
        return React.useMemo(() => new URLSearchParams(search), [search]);
    },
}));
vi.mock("@/lib/api/repositories", () => ({ getRepositories: vi.fn() }));
vi.mock("@/lib/api/repository-work-items", () => ({ listRepositoryWorkItems: vi.fn() }));
vi.mock("@/lib/api/activity", () => ({ listRepositoryActivity: vi.fn() }));
let currentUser: string | undefined = "workspace-user";
vi.mock("@/lib/auth/use-auth", () => ({ useAuth: () => ({ isAuthenticated: !!currentUser, user: currentUser ? { id: currentUser } : null }) }));
vi.mock("@/lib/api/repository-contributions", async (original) => ({ ...await original<typeof import("@/lib/api/repository-contributions")>(), fetchRepositoryContributions: vi.fn() }));
vi.mock("@/components/activity/use-activity-metadata", () => ({ useActivityMetadata: () => ({}) }));
vi.mock("@/components/activity/contribution-heatmap", () => ({ ContributionHeatmap: () => <section><h2>Your contribution heatmap</h2><p>Personal calendar unavailable</p></section> }));

const repositories: Repository[] = [
    { id: "repo-a", full_name: "acme/alpha", private: false, default_branch: "main", monitoring_enabled: false, created_at: "2026-01-01" },
    { id: "repo-b", full_name: "acme/beta", private: true, default_branch: "develop", monitoring_enabled: true, created_at: "2026-01-01" },
    { id: "repo-c", full_name: "other/charlie", private: false, default_branch: null, monitoring_enabled: false, created_at: "2026-01-01" },
];
const item = (title: string, draft = false) => ({ number: 17, title, state: "open", html_url: "https://github.com/acme/beta/issues/17", created_at: null, updated_at: "2026-10-17", user: { login: "octocat" }, labels: [{ name: "bug" }], draft });
function visit(query: string) { act(() => window.history.pushState(null, "", `/overview/activity${query}`)); }

beforeEach(() => {
    vi.restoreAllMocks();
    vi.resetAllMocks();
    currentUser = "workspace-user";
    window.history.replaceState(null, "", "/overview/activity");
    for (const method of ["pushState", "replaceState"] as const) {
        const original = window.history[method].bind(window.history);
        vi.spyOn(window.history, method).mockImplementation((...args) => {
            original(...args);
            window.dispatchEvent(new PopStateEvent("popstate"));
        });
    }
    vi.mocked(getRepositories).mockResolvedValue(repositories);
    vi.mocked(listRepositoryWorkItems).mockResolvedValue([]);
    vi.mocked(fetchRepositoryContributions).mockImplementation(async (id) => contributionSnapshot(id));
});

it("defaults to the first authorized repo and Contributions without work-item/event requests; searches without changing selection", async () => {
    render(<ActivityPage />);
    expect(screen.getByRole("status", { name: "Loading repositories" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Repository contributions" })).toBeInTheDocument();
    await waitFor(() => expect(fetchRepositoryContributions).toHaveBeenCalledWith("repo-a", expect.anything(), expect.any(AbortSignal)));
    expect(screen.getByRole("button", { name: "Select acme/alpha" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("combobox", { name: "Workspace view" })).toHaveValue("contributions");
    expect(screen.getAllByRole("option").map((option) => option.textContent)).toEqual(["Contributions", "Issues", "Pull Requests"]);
    expect(window.location.search).toBe("?repo=repo-a&tab=contributions");
    expect(screen.getByRole("heading", { name: "Your contribution heatmap" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Language footprint" })).toBeInTheDocument();
    expect(screen.getByText("Personal calendar unavailable")).toBeInTheDocument();
    expect(listRepositoryWorkItems).not.toHaveBeenCalled();
    expect(listRepositoryActivity).not.toHaveBeenCalled();
    expect(screen.queryByRole("group", { name: "Filter activity by source" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "  BETA " } });
    expect(within(screen.getByRole("list", { name: "Connected repositories" })).getAllByRole("button")).toHaveLength(1);
    expect(screen.getByRole("heading", { name: "acme/alpha" })).toBeInTheDocument();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "not-a-repo" } });
    expect(screen.getByText("No matching repositories")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Clear search" }));
    expect(within(screen.getByRole("list", { name: "Connected repositories" })).getAllByRole("button")).toHaveLength(3);
});

it("prefers URL scope, embeds complete Issues/PR rows, and fetches only the mounted detail", async () => {
    visit("?repo=repo-b&tab=issues&keep=1#workspace");
    vi.mocked(listRepositoryWorkItems).mockResolvedValueOnce([item("Investigate issue")]).mockResolvedValueOnce([item("Review draft", true)]);
    render(<ActivityPage />);
    expect(await screen.findByText("Investigate issue")).toBeInTheDocument();
    expect(screen.getByText("#17")).toBeInTheDocument();
    expect(screen.getByText(/opened by octocat/)).toHaveTextContent(/updated/);
    expect(screen.getByText("bug")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View on GitHub" })).toHaveAttribute("href", "https://github.com/acme/beta/issues/17");
    expect(screen.getByRole("link", { name: "Open acme/beta on GitHub" })).toHaveAttribute("rel", "noopener noreferrer");
    expect(listRepositoryWorkItems).toHaveBeenCalledExactlyOnceWith("repo-b", "issues");
    expect(getRepositories).toHaveBeenCalledTimes(1);
    expect(fetchRepositoryContributions).not.toHaveBeenCalled();
    expect(screen.getAllByRole("combobox")).toHaveLength(1);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "pull-requests" } });
    expect(await screen.findByText("Review draft")).toBeInTheDocument();
    expect(screen.getByText(/open · draft/)).toHaveTextContent(/opened by octocat/);
    expect(screen.queryByText("Investigate issue")).not.toBeInTheDocument();
    expect(listRepositoryWorkItems).toHaveBeenLastCalledWith("repo-b", "pull-requests");
    expect(window.location.href).toContain("keep=1");
    expect(window.location.hash).toBe("#workspace");
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "contributions" } });
    await screen.findByText("Complete history for this window.");
    expect(listRepositoryWorkItems).toHaveBeenCalledTimes(2);
});

it("restores history changes, validates duplicate/unknown URL values, and retains the last valid selection", async () => {
    visit("?repo=repo-b&tab=issues");
    render(<ActivityPage />);
    await screen.findByText("No open issues");
    visit("?repo=repo-c&tab=pull-requests");
    await screen.findByText("No open pull requests");
    // popstate is what Back/Forward emits; the browser suite exercises actual traversal.
    act(() => {
        window.history.replaceState(null, "", "/overview/activity?repo=repo-b&tab=issues");
        window.dispatchEvent(new PopStateEvent("popstate"));
    });
    await screen.findByText("No open issues");
    visit("?repo=unauthorized&tab=javascript%3Aalert(1)");
    expect(screen.getByRole("heading", { name: "acme/beta" })).toBeInTheDocument();
    expect(screen.getByRole("combobox")).toHaveValue("contributions");
    await waitFor(() => expect(window.location.search).toBe("?repo=repo-b&tab=contributions"));
    expect(listRepositoryWorkItems).not.toHaveBeenCalledWith("unauthorized", expect.anything());
    visit("?repo=repo-c&repo=repo-a&tab=issues&tab=pull-requests");
    expect(screen.getByRole("heading", { name: "acme/beta" })).toBeInTheDocument();
    expect(screen.getByRole("combobox")).toHaveValue("contributions");
});

it("discards late detail responses through rapid repository AND view switches", async () => {
    visit("?repo=repo-a&tab=issues");
    let resolveA!: (items: ReturnType<typeof item>[]) => void;
    let resolveB!: (items: ReturnType<typeof item>[]) => void;
    vi.mocked(listRepositoryWorkItems).mockImplementation((id) => id === "repo-a" ? new Promise((resolve) => { resolveA = resolve; }) : id === "repo-b" ? new Promise((resolve) => { resolveB = resolve; }) : Promise.resolve([item("Current C PR")]));
    render(<ActivityPage />);
    await waitFor(() => expect(listRepositoryWorkItems).toHaveBeenCalledWith("repo-a", "issues"));
    fireEvent.click(screen.getByRole("button", { name: "Select acme/beta" }));
    await waitFor(() => expect(listRepositoryWorkItems).toHaveBeenCalledWith("repo-b", "issues"));
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "contributions" } });
    fireEvent.click(screen.getByRole("button", { name: "Select other/charlie" }));
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "pull-requests" } });
    expect(await screen.findByText("Current C PR")).toBeInTheDocument();
    await act(async () => { resolveA([item("Late A")]); resolveB([item("Late B")]); });
    expect(screen.queryByText("Late A")).not.toBeInTheDocument();
    expect(screen.queryByText("Late B")).not.toBeInTheDocument();
    expect(screen.getByText("Current C PR")).toBeInTheDocument();
});

it("keeps detail errors distinct from empty data and retries the selected scope", async () => {
    visit("?repo=repo-b&tab=issues");
    vi.mocked(listRepositoryWorkItems).mockRejectedValueOnce(new Error("Access revoked. Review GitHub App permissions.")).mockResolvedValueOnce([]);
    render(<ActivityPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Access revoked");
    expect(screen.queryByText("No open issues")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("No open issues")).toBeInTheDocument();
    expect(listRepositoryWorkItems).toHaveBeenNthCalledWith(2, "repo-b", "issues");
});

it("revalidates revoked repositories on focus, falls back, and clears detail when all access disappears", async () => {
    visit("?repo=repo-b&tab=issues");
    render(<ActivityPage />);
    await screen.findByText("No open issues");
    vi.mocked(getRepositories).mockResolvedValueOnce([repositories[0], repositories[2]]);
    fireEvent(window, new Event("focus"));
    await waitFor(() => expect(screen.getByRole("heading", { name: "acme/alpha" })).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Select acme/beta" })).not.toBeInTheDocument();
    await waitFor(() => expect(listRepositoryWorkItems).toHaveBeenLastCalledWith("repo-a", "issues"));
    vi.mocked(getRepositories).mockResolvedValueOnce([]);
    fireEvent.click(screen.getByRole("button", { name: "Refresh repositories" }));
    expect(await screen.findByText("No connected repositories")).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    await waitFor(() => expect(window.location.search).toBe("?tab=issues"));
});

it("recovers from a repository discovery error and ignores obsolete discovery responses", async () => {
    let oldResponse!: (repos: Repository[]) => void;
    vi.mocked(getRepositories).mockImplementationOnce(() => new Promise((resolve) => { oldResponse = resolve; })).mockResolvedValueOnce(null).mockResolvedValueOnce(repositories);
    render(<ActivityPage />);
    fireEvent(window, new Event("focus"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Repositories are temporarily unavailable");
    await act(async () => oldResponse([repositories[2]]));
    expect(screen.getByRole("alert")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "acme/alpha" })).toBeInTheDocument();
    expect(listRepositoryWorkItems).not.toHaveBeenCalled();
});

it("validates selections and constructs safe GitHub links", () => {
    expect(readWorkspaceSelection(new URLSearchParams("repo=repo-b&tab=issues"), repositories, "repo-a")).toEqual({ repository: repositories[1], view: "issues" });
    expect(readWorkspaceSelection(new URLSearchParams("repo=missing"), repositories, "repo-c").repository).toBe(repositories[2]);
    expect(readWorkspaceSelection(new URLSearchParams(), repositories, "missing").repository).toBe(repositories[0]);
    expect(readWorkspaceSelection(new URLSearchParams("repo=repo-a"), [], "repo-a").repository).toBeUndefined();
    expect(githubRepositoryUrl("acme/repo.name_1")).toBe("https://github.com/acme/repo.name_1");
    for (const name of ["https://evil.test/a", "acme/..", "acme/.", "acme/a?redirect=evil", "acme/a#fragment", "acme/a/b", "acme\\evil/a", "//evil.test"]) expect(githubRepositoryUrl(name)).toBeNull();
});


it("never resolves detail links against a fallback repository and preserves invalid context", async () => {
    visit("?repo=missing&tab=issues&item=17");
    render(<ActivityPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("invalid or its repository is unavailable");
    expect(window.location.search).toBe("?repo=missing&tab=issues&item=17");
    expect(listRepositoryWorkItems).not.toHaveBeenCalled();
    expect(fetchRepositoryContributions).not.toHaveBeenCalled();
    visit("?repo=repo-b&tab=issues&item=17");
    expect(await screen.findByRole("link", { name: "Open item details on GitHub" })).toHaveAttribute("href", "https://github.com/acme/beta/issues/17");
    await screen.findByText("No open issues");
    vi.mocked(getRepositories).mockResolvedValueOnce([repositories[0]]);
    fireEvent(window, new Event("focus"));
    expect(await screen.findByRole("alert")).toHaveTextContent("invalid or its repository is unavailable");
    expect(screen.queryByRole("link", { name: "Open item details on GitHub" })).not.toBeInTheDocument();
    expect(listRepositoryWorkItems).toHaveBeenCalledExactlyOnceWith("repo-b", "issues");
    fireEvent.click(screen.getByRole("button", { name: "Select acme/alpha" }));
    expect(await screen.findByText("No open issues")).toBeInTheDocument();
    expect(window.location.search).toBe("?repo=repo-a&tab=issues");
});


it("clears workspace scope immediately across account changes and ignores the previous user's discovery", async () => {
    visit("?repo=repo-b&tab=issues&item=17");
    vi.mocked(listRepositoryWorkItems).mockResolvedValue([item("Private issue from first user")]);
    const page = render(<ActivityPage />);
    await screen.findByText("Private issue from first user");
    let resolveOld!: (repos: Repository[]) => void;
    vi.mocked(getRepositories).mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve; }));
    fireEvent(window, new Event("focus"));
    let resolveNew!: (repos: Repository[]) => void;
    vi.mocked(getRepositories).mockImplementationOnce(() => new Promise(resolve => { resolveNew = resolve; }));
    currentUser = "second-user";
    page.rerender(<ActivityPage />);
    expect(screen.queryByText("Private issue from first user")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Select acme/beta" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Open item details on GitHub" })).not.toBeInTheDocument();
    await waitFor(() => expect(getRepositories).toHaveBeenCalledTimes(3));
    await act(async () => resolveOld(repositories));
    expect(screen.queryByRole("button", { name: "Select acme/beta" })).not.toBeInTheDocument();
    await act(async () => resolveNew([repositories[2]]));
    expect(await screen.findByRole("alert")).toHaveTextContent("invalid or its repository is unavailable");
    expect(listRepositoryWorkItems).toHaveBeenCalledExactlyOnceWith("repo-b", "issues");
    currentUser = undefined;
    page.rerender(<ActivityPage />);
    expect(screen.queryByRole("button", { name: "Select other/charlie" })).not.toBeInTheDocument();
    expect(getRepositories).toHaveBeenCalledTimes(3);
});


it("labels invalid detail recovery with the actual destination view", async () => {
    visit("?repo=repo-b&tab=invalid&item=17");
    render(<ActivityPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("invalid or its repository is unavailable");
    expect(listRepositoryWorkItems).not.toHaveBeenCalled();
    expect(fetchRepositoryContributions).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Back to Contributions" }));
    expect(await screen.findByRole("heading", { name: "Repository contributions" })).toBeInTheDocument();
    expect(window.location.search).toBe("?repo=repo-b&tab=contributions");
});
