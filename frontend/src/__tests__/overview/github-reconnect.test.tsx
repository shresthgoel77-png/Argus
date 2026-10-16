import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { GitHubSettingsCard } from "@/app/(app)/overview/settings/github-settings-card";
import { getConnections, startInstall } from "@/lib/api/github";
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/api/github", () => ({ getConnections: vi.fn(), startInstall: vi.fn() }));
beforeEach(() => vi.resetAllMocks());
it("binds reconnection to the selected existing connection", async () => {
    vi.mocked(getConnections).mockResolvedValue([{ id: "owned-connection", account_login: "expected-owner", status: "active" }] as Awaited<ReturnType<typeof getConnections>>);
    vi.mocked(startInstall).mockResolvedValue({ install_url: "https://github.com/apps/fixture/installations/new?state=signed-fixture" });
    const popup = { location: { href: "about:blank" }, close: vi.fn() };
    const open = vi.spyOn(window, "open").mockReturnValue(popup as unknown as Window);
    render(<GitHubSettingsCard />);
    fireEvent.click(await screen.findByRole("button", { name: "Reconnect expected-owner" }));
    await waitFor(() => expect(startInstall).toHaveBeenCalledExactlyOnceWith("owned-connection"));
    expect(popup.location.href).toContain("state=signed-fixture");
    open.mockRestore();
});
