import { beforeEach, expect, it, vi } from "vitest";
import { listRepositoryWorkItems } from "@/lib/api/repository-work-items";
vi.mock("@/lib/auth/clerk-token", () => ({ getClerkAuthorizationHeaders: vi.fn().mockResolvedValue({}) }));
beforeEach(() => vi.unstubAllGlobals());
it.each([
    [401, "not_authenticated", "Sign in to RepoMedic again"],
    [403, "github_permission_error", "repository permissions"],
    [502, "github_auth_error", "credentials were rejected"],
    [404, "not_found", "your RepoMedic account"],
    [409, "github_installation_unavailable", "Reconnect the same GitHub account"],
])("distinguishes failure %s %s", async (status, code, message) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code, message: code === "github_installation_unavailable" ? "Reconnect the same GitHub account" : "Request rejected" } }), { status })));
    await expect(listRepositoryWorkItems("owned-repo", "issues")).rejects.toThrow(message);
});
