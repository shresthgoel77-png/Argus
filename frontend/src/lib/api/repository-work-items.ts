import { getClerkAuthorizationHeaders } from "../auth/clerk-token";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface GitHubWorkItem {
    number: number;
    title: string;
    state: string;
    html_url: string;
    created_at: string | null;
    updated_at: string | null;
    user: { login?: string } | null;
    labels: { name?: string }[];
    draft: boolean | null;
}

export async function listRepositoryWorkItems(
    repositoryId: string,
    kind: "issues" | "pull-requests",
): Promise<GitHubWorkItem[]> {
    const headers = await getClerkAuthorizationHeaders();
    const response = await fetch(
        `${API_URL}/api/v1/repositories/${repositoryId}/${kind}?limit=100`,
        { headers: { "Content-Type": "application/json", ...headers }, credentials: "include", cache: "no-store" },
    );
    if (!response.ok) {
        let detail = "";
        let code = "";
        try {
            const body = await response.json() as { detail?: string; error?: { code?: string; message?: string } };
            code = body.error?.code ?? "";
            const message = body.detail || body.error?.message;
            detail = message ? `: ${message}` : "";
        } catch {
            detail = "";
        }
        if (response.status === 401) detail += ". Sign in to RepoMedic again; your Clerk session could not be authenticated.";
        else if (code === "github_permission_error") detail += ". Review the GitHub App's repository permissions in GitHub settings.";
        else if (code === "github_auth_error") detail += ". The server's GitHub App credentials were rejected; contact the administrator.";
        else if (code === "github_not_found") detail += ". Verify this repository is included in the GitHub installation.";
        else if (response.status === 404) detail += ". This repository is unavailable to your RepoMedic account. Check the selected repository and account.";
        throw new Error(`GitHub ${kind === "issues" ? "issues" : "pull requests"} could not be loaded (HTTP ${response.status})${detail}`);
    }
    return await response.json() as GitHubWorkItem[];
}

export interface FindingIssuePreview {
    repository: string;
    title: string;
    body: string;
    preview_token: string;
}

async function findingIssueRequest<T>(id: string, suffix: string, options: RequestInit = {}): Promise<T> {
    const headers = await getClerkAuthorizationHeaders();
    const response = await fetch(
        `${API_URL}/api/v1/findings/${id}/${suffix}`,
        { ...options, headers: { "Content-Type": "application/json", ...headers }, credentials: "include", cache: "no-store" },
    );
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || body.error?.message || `GitHub request failed (HTTP ${response.status}).`);
    return body as T;
}

export function previewFindingIssue(id: string): Promise<FindingIssuePreview> {
    return findingIssueRequest(id, "issue-preview");
}

export function createFindingIssue(id: string, previewToken: string): Promise<GitHubWorkItem> {
    return findingIssueRequest(id, "issue", {
        method: "POST", body: JSON.stringify({ approved: true, preview_token: previewToken }),
    });
}
