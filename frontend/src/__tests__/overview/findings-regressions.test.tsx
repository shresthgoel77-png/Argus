import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import FindingsPage from "@/app/(app)/overview/findings/page";
import { listFindings } from "@/lib/api/findings";

vi.mock("@/lib/api/findings", () => ({ listFindings: vi.fn() }));
vi.mock("@/lib/api/repositories", () => ({ getRepositories: vi.fn().mockResolvedValue([]) }));
vi.mock("@/app/(app)/overview/findings/finding-detail-dialog", () => ({ FindingDetailDialog: () => null }));

beforeEach(() => vi.clearAllMocks());

it("fetches each cursor once and resets pagination when filtering", async () => {
    const first = { items: [], total: 21, limit: 20, next_cursor: "page-two" };
    const last = { ...first, next_cursor: null };
    vi.mocked(listFindings).mockResolvedValue(last).mockResolvedValueOnce(first);
    await act(async () => { render(<FindingsPage />); });
    const next = await screen.findByRole("button", { name: "Next" });
    await waitFor(() => expect(next).toBeEnabled());
    expect(listFindings).toHaveBeenCalledTimes(1);
    fireEvent.click(next);
    await waitFor(() => expect(listFindings).toHaveBeenCalledWith({ limit: "20", cursor: "page-two" }));
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "open" } });
    await waitFor(() => expect(listFindings).toHaveBeenLastCalledWith({ limit: "20", status: "open" }));
}, 20_000);
