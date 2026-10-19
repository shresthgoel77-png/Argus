import { StrictMode } from "react";
import { LegacyWorkItemsEntry } from "@/components/activity/legacy-work-items-entry";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { AppSidebar, isAppNavActive } from "@/components/layout/app-sidebar";
import { AppMobileNav } from "@/components/layout/app-mobile-nav";
import { legacyActivityUrl, readWorkspaceSelection, workItemDetailUrl } from "@/components/activity/workspace-selection";
import type { Repository } from "@/lib/types/github";

const { replace } = vi.hoisted(() => ({ replace: vi.fn() }));
vi.mock("next/navigation", () => ({ usePathname: () => "/overview/activity", useRouter: () => ({ replace }) }));
const repositories = [{ id: "a", full_name: "owner/a" }, { id: "b", full_name: "owner/b", monitoring_enabled: true }] as Repository[];

it("retains desktop/mobile navigation order, active Activity and bottom Settings", () => {
    render(<><AppSidebar /><AppMobileNav trigger={<button>Open menu</button>} /></>);
    const desktop = screen.getByRole("navigation", { name: "App navigation" });
    expect(within(desktop).getAllByRole("link").map(link => link.textContent)).toEqual(["Overview", "Repositories", "Findings", "Activity", "Settings"]);
    expect(within(desktop).getByRole("link", { name: "Settings" }).parentElement).toHaveClass("mt-auto");
    expect(within(desktop).getByRole("link", { name: "Activity" })).toHaveAttribute("aria-current", "page");
    fireEvent.click(screen.getByRole("button", { name: "Open menu" }));
    const mobile = screen.getByRole("navigation", { name: "Mobile app navigation" });
    expect(within(mobile).getAllByRole("link").map(link => link.textContent)).toEqual(["Overview", "Repositories", "Findings", "Activity", "Settings"]);
    expect(within(mobile).getByRole("link", { name: "Settings" }).parentElement).toHaveClass("mt-auto");
    expect(within(mobile).getByRole("link", { name: "Activity" })).toHaveAttribute("aria-current", "page");
    for (const path of ["/overview/activity", "/overview/issues/17", "/overview/pull-requests"]) expect(isAppNavActive("/overview/activity", path)).toBe(true);
    expect(isAppNavActive("/overview", "/overview/activity")).toBe(false);
    expect(isAppNavActive("/overview/activity", "/overview/issues-other")).toBe(false);
});

it("preserves legacy scope, repeated filters, sorting, paging and fragments with a fixed destination", () => {
    const path = legacyActivityUrl("https://local/overview/issues?repo=b&tab=contributions&label=bug&label=help&sort=updated&page=3&next=https://evil.test#item", "issues", ["17"]);
    const url = new URL(path, "https://local");
    expect(url.pathname).toBe("/overview/activity");
    expect(url.searchParams.get("tab")).toBe("issues");
    expect(url.searchParams.get("repo")).toBe("b");
    expect(url.searchParams.getAll("label")).toEqual(["bug", "help"]);
    expect(url.searchParams.get("sort")).toBe("updated");
    expect(url.searchParams.get("page")).toBe("3");
    expect(url.hash).toBe("#item");
    expect(workItemDetailUrl(url.searchParams, repositories[1], "issues")).toBe("https://github.com/owner/b/issues/17");
    const legacy = new URL(legacyActivityUrl("https://local/overview/pull-requests", "pull-requests"), "https://local");
    expect(readWorkspaceSelection(legacy.searchParams, repositories, "").repository).toBe(repositories[1]);
});

it("rejects ambiguous, malformed and unscoped details without selecting another repository", () => {
    for (const query of ["item=17", "repo=missing&item=17", "repo=a&repo=b&item=17"]) {
        expect(readWorkspaceSelection(new URLSearchParams(query), repositories, "a").repository).toBeUndefined();
    }
    for (const query of ["item=0", "item=-1", "item=javascript:alert(1)", "item=17&item=18", "item=1/2", "item=999999999999999999999"]) {
        expect(workItemDetailUrl(new URLSearchParams(query), repositories[0], "issues")).toBeNull();
    }
    const conflict = new URL(legacyActivityUrl("https://local/overview/issues?repo=a&item=18", "issues", ["17"]), "https://local");
    expect(workItemDetailUrl(conflict.searchParams, repositories[0], "issues")).toBeNull();
    expect(workItemDetailUrl(new URLSearchParams("item=17"), repositories[0], "pull-requests")).toBe("https://github.com/owner/a/pull/17");
});


it("replaces the legacy history entry once even with Strict Mode effects", () => {
    window.history.replaceState(null, "", "/overview/issues/17?repo=b#details");
    render(<StrictMode><LegacyWorkItemsEntry view="issues" detail={["17"]} /></StrictMode>);
    expect(replace).toHaveBeenCalledExactlyOnceWith("/overview/activity?repo=b&tab=issues&item=17#details");
});
