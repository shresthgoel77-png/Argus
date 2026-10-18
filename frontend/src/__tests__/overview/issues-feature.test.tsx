import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { IssuesFeature } from "@/components/repositories/issues-feature";
import { getRepositories } from "@/lib/api/repositories";
import { listRepositoryWorkItems } from "@/lib/api/repository-work-items";
import type { Repository } from "@/lib/types/github";

vi.mock("@/lib/api/repositories", () => ({ getRepositories: vi.fn() }));
vi.mock("@/lib/api/repository-work-items", () => ({
    listRepositoryWorkItems: vi.fn(),
    previewFindingIssue: vi.fn(),
    createFindingIssue: vi.fn(),
}));

const repositoryA = { id: "repo-a", full_name: "owner/a", monitoring_enabled: true } as Repository;
const repositoryB = { id: "repo-b", full_name: "owner/b", monitoring_enabled: false } as Repository;
const item = (number: number, title: string) => ({
    number,
    title,
    state: "open",
    html_url: `https://github.com/owner/repo/issues/${number}`,
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

it("renders the reusable Issues body with explicit repository scope and ignores unrelated hub URL state", async () => {
    window.history.replaceState({}, "", "/overview/activity?tab=pull-requests&repo=repo-b");
    vi.mocked(listRepositoryWorkItems).mockResolvedValue([item(1, "Issue for A")]);

    render(<IssuesFeature selectedRepository={repositoryA} />);

    expect(screen.getByRole("heading", { name: "Issues" })).toBeInTheDocument();
    expect(await screen.findByText("Issue for A")).toBeInTheDocument();
    expect(getRepositories).not.toHaveBeenCalled();
    expect(listRepositoryWorkItems).toHaveBeenCalledExactlyOnceWith("repo-a", "issues");
    expect(screen.queryByRole("combobox", { name: "Select repository" })).not.toBeInTheDocument();
});

it("hides the previous repository immediately and ignores its late response after switching scope", async () => {
    let resolveA!: (items: Awaited<ReturnType<typeof listRepositoryWorkItems>>) => void;
    let resolveB!: (items: Awaited<ReturnType<typeof listRepositoryWorkItems>>) => void;
    vi.mocked(listRepositoryWorkItems).mockImplementation((repositoryId) => new Promise((resolve) => {
        if (repositoryId === "repo-a") resolveA = resolve;
        else resolveB = resolve;
    }));

    const view = render(<IssuesFeature selectedRepository={repositoryA} />);
    await waitFor(() => expect(listRepositoryWorkItems).toHaveBeenCalledWith("repo-a", "issues"));

    view.rerender(<IssuesFeature selectedRepository={repositoryB} />);
    expect(screen.getByLabelText("Loading GitHub issues")).toBeInTheDocument();
    expect(screen.queryByText("Issue for A")).not.toBeInTheDocument();
    await waitFor(() => expect(listRepositoryWorkItems).toHaveBeenCalledWith("repo-b", "issues"));

    await act(async () => resolveB([item(2, "Issue for B")]));
    expect(await screen.findByText("Issue for B")).toBeInTheDocument();

    await act(async () => resolveA([item(1, "Late issue for A")]));
    expect(screen.queryByText("Late issue for A")).not.toBeInTheDocument();
    expect(screen.getByText("Issue for B")).toBeInTheDocument();
});
