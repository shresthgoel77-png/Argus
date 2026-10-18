import type { Repository } from "@/lib/types/github";

export const workspaceViews = [
    { value: "contributions", label: "Contributions" },
    { value: "issues", label: "Issues" },
    { value: "pull-requests", label: "Pull Requests" },
] as const;

export type WorkspaceView = typeof workspaceViews[number]["value"];

export function readWorkspaceSelection(params: Pick<URLSearchParams, "getAll">, repositories: Repository[], existingId: string) {
    const repositoryValues = params.getAll("repo");
    const viewValues = params.getAll("tab");
    const repository = (repositoryValues.length === 1
        ? repositories.find((candidate) => candidate.id === repositoryValues[0]) : undefined)
        ?? repositories.find((candidate) => candidate.id === existingId)
        ?? repositories[0];
    const view = (viewValues.length === 1
        ? workspaceViews.find((candidate) => candidate.value === viewValues[0])?.value : undefined)
        ?? "contributions";
    return { repository, view };
}

/** Construct a fixed-origin link only from a plausible GitHub owner/repository pair. */
export function githubRepositoryUrl(fullName: string): string | null {
    const parts = fullName.split("/");
    if (parts.length !== 2 || !/^[a-z\d](?:[a-z\d-]*[a-z\d])?$/i.test(parts[0])
        || !/^[a-z\d_.-]+$/i.test(parts[1]) || parts[1] === "." || parts[1] === "..") return null;
    return `https://github.com/${parts.map(encodeURIComponent).join("/")}`;
}

/** Preserve unrelated query values and the fragment; never accept a navigation destination. */
export function workspaceUrl(href: string, repositoryId: string | undefined, view: WorkspaceView) {
    const url = new URL(href);
    if (repositoryId) url.searchParams.set("repo", repositoryId);
    else url.searchParams.delete("repo");
    url.searchParams.set("tab", view);
    return `${url.pathname}${url.search}${url.hash}`;
}
