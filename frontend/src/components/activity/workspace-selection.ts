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
    const requestedRepository = repositoryValues.length === 1
        ? repositories.find((candidate) => candidate.id === repositoryValues[0]) : undefined;
    const hasDetail = params.getAll("item").length > 0;
    const repository = hasDetail ? requestedRepository : (requestedRepository
        ?? repositories.find((candidate) => candidate.id === existingId)
        ?? (params.getAll("legacy")[0] === "work-items" ? repositories.find((candidate) => candidate.monitoring_enabled) : undefined)
        ?? repositories[0]);
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
    url.searchParams.delete("legacy");
    return `${url.pathname}${url.search}${url.hash}`;
}

/** Legacy adapters preserve all context and fragments, but cannot choose a destination. */
export function legacyActivityUrl(href: string, view: Exclude<WorkspaceView, "contributions">, detail?: string[]) {
    const url = new URL(href);
    url.pathname = "/overview/activity";
    url.searchParams.set("tab", view);
    if (detail) {
        // Conflicting query/path identifiers fail validation instead of choosing one.
        const values = [...url.searchParams.getAll("item"), ...detail];
        url.searchParams.delete("item");
        for (const value of values) url.searchParams.append("item", value);
    }
    if (!url.searchParams.has("repo") && !url.searchParams.has("item")) url.searchParams.set("legacy", "work-items");
    return `${url.pathname}${url.search}${url.hash}`;
}

/** Detail capability remains the existing external GitHub experience, including closed items. */
export function workItemDetailUrl(params: Pick<URLSearchParams, "getAll">, repository: Repository | undefined, view: WorkspaceView) {
    const values = params.getAll("item");
    const base = repository && githubRepositoryUrl(repository.full_name);
    if (!base || view === "contributions" || values.length !== 1 || !/^[1-9]\d{0,14}$/.test(values[0])) return null;
    return `${base}/${view === "issues" ? "issues" : "pull"}/${values[0]}`;
}
