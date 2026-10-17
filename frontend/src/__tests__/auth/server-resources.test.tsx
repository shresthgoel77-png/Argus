import { beforeEach, describe, expect, it, vi } from "vitest";
import { auth } from "@clerk/nextjs/server";
import AppLayout from "@/app/(app)/layout";
import DashboardPage from "@/app/(app)/dashboard/page";
import IssuesPage from "@/app/(app)/overview/issues/page";
import PullRequestsPage from "@/app/(app)/overview/pull-requests/page";
import SettingsPage from "@/app/(app)/overview/settings/page";

vi.mock("@clerk/nextjs/server", () => ({
    auth: { protect: vi.fn() },
}));

// Call each server entrypoint directly, without middleware or a parent layout.
const resources = [
    ["app layout", () => AppLayout({ children: "content" })],
    ["dashboard", DashboardPage],
    ["issues", IssuesPage],
    ["pull requests", PullRequestsPage],
    ["settings", SettingsPage],
] as const;

describe.each(resources)("%s resource authentication", (_name, resource) => {
    beforeEach(() => vi.resetAllMocks());

    it("does not return content when Clerk denies access", async () => {
        const denied = new Error("Clerk sign-in redirect");
        vi.mocked(auth.protect).mockRejectedValue(denied);

        await expect(resource()).rejects.toBe(denied);
    });

    it("returns content after Clerk grants access", async () => {
        await expect(resource()).resolves.toBeTruthy();
        expect(auth.protect).toHaveBeenCalledOnce();
    });
});
