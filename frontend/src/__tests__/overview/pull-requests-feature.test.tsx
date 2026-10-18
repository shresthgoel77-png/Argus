import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { PullRequestsFeature } from "@/components/repositories/pull-requests-feature";
import { getRepositories } from "@/lib/api/repositories";
import { createFindingIssue, listRepositoryWorkItems } from "@/lib/api/repository-work-items";
import type { GitHubWorkItem } from "@/lib/api/repository-work-items";
import type { Repository } from "@/lib/types/github";

vi.mock("@/lib/api/repositories", () => ({ getRepositories: vi.fn() }));
vi.mock("@/lib/api/repository-work-items", () => ({
    listRepositoryWorkItems: vi.fn(),
    previewFindingIssue: vi.fn(),
    createFindingIssue: vi.fn(),
}));

const repositoryA = { id: "repo-a", full_name: "owner/a", monitoring_enabled: true } as Repository;
const repositoryB = { id: "repo-b", full_name: "owner/b", monitoring_enabled: false } as Repository;
const repositoryC = { id: "repo-c", full_name: "owner/c", monitoring_enabled: true } as Repository;
const pullRequest = (number: number, title: string): GitHubWorkItem => ({
    number,
    title,
    state: "open",
    html_url: `https://github.com/owner/repo/pull/${number}`,
    created_at: null,
    updated_at: null,
    user: null,
    labels: [],
    draft: null,
});

beforeEach(() => {
    vi.resetAllMocks();
    window.history.replaceState({}, "", "/");
});

it("renders the reusable Pull Requests experience for the explicit repository without consuming Issues URL state", async () => {
    window.history.replaceState({}, "", "/overview/activity?repo=repo-b&tab=issues&issue_status=closed&pr_state=closed");
    vi.mocked(listRepositoryWorkItems).mockResolvedValue([pullRequest(11, "PR for A")]);

    render(<PullRequestsFeature selectedRepository={repositoryA} />);

    expect(screen.getByRole("heading", { name: "Pull requests" })).toBeInTheDocument();
    expect(await screen.findByText("PR for A")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View on GitHub" })).toHaveAttribute("href", "https://github.com/owner/repo/pull/11");
    expect(getRepositories).not.toHaveBeenCalled();
    expect(listRepositoryWorkItems).toHaveBeenCalledExactlyOnceWith("repo-a", "pull-requests");
    expect(createFindingIssue).not.toHaveBeenCalled();
    expect(screen.queryByRole("combobox", { name: "Select repository" })).not.toBeInTheDocument();
});

it("hides resolved repository data on each switch and ignores the late response from the previous scope", async () => {
    let resolveB!: (items: GitHubWorkItem[]) => void;
    let resolveC!: (items: GitHubWorkItem[]) => void;
    vi.mocked(listRepositoryWorkItems).mockImplementation((repositoryId) => {
        if (repositoryId === "repo-a") return Promise.resolve([pullRequest(1, "PR for A")]);
        return new Promise((resolve) => {
            if (repositoryId === "repo-b") resolveB = resolve;
            else resolveC = resolve;
        });
    });

    const view = render(<PullRequestsFeature selectedRepository={repositoryA} />);
    expect(await screen.findByText("PR for A")).toBeInTheDocument();

    view.rerender(<PullRequestsFeature selectedRepository={repositoryB} />);
    expect(screen.getByLabelText("Loading GitHub pull requests")).toBeInTheDocument();
    expect(screen.queryByText("PR for A")).not.toBeInTheDocument();
    await waitFor(() => expect(listRepositoryWorkItems).toHaveBeenCalledWith("repo-b", "pull-requests"));

    view.rerender(<PullRequestsFeature selectedRepository={repositoryC} />);
    expect(screen.getByLabelText("Loading GitHub pull requests")).toBeInTheDocument();
    await waitFor(() => expect(listRepositoryWorkItems).toHaveBeenCalledWith("repo-c", "pull-requests"));

    await act(async () => resolveC([pullRequest(3, "PR for C")]));
    expect(await screen.findByText("PR for C")).toBeInTheDocument();

    await act(async () => resolveB([pullRequest(2, "Late PR for B")]));
    expect(screen.queryByText("Late PR for B")).not.toBeInTheDocument();
    expect(screen.getByText("PR for C")).toBeInTheDocument();
});
