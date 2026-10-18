import * as React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ActivityFeedList } from "@/components/activity/activity-feed-list";
import { SourceFilter } from "@/components/activity/source-filter";
import { listRepositoryActivity } from "@/lib/api/activity";
import type { ActivityItem, ActivitySource } from "@/lib/types/activity";

vi.mock("@/lib/api/activity", () => ({ listRepositoryActivity: vi.fn() }));

function HistoryHarness() {
    const [source, setSource] = React.useState<ActivitySource | "all">("all");
    return <><SourceFilter value={source} onChange={setSource} /><ActivityFeedList key={source} repositoryId="repo-a" sourceFilter={source} /></>;
}

it("preserves shared event history filtering, cursor navigation, bot expansion, and retry outside Activity", async () => {
    const event: ActivityItem = { source: "github_event", timestamp: "2026-10-17T10:00:00Z", title: "Deployment completed", summary: "Deployment succeeded", reference_id: "event-1" };
    const bot: ActivityItem = { source: "bot_interaction", timestamp: event.timestamp, title: "Bot interaction", summary: "CI checked", reference_id: "bot-1", details: { intent: "ci_status", status: "completed", question_text: "Is CI passing?", response_text: "Yes, CI is passing.", skip_reason: null, requester_github_login: "octocat" } };
    vi.mocked(listRepositoryActivity).mockImplementation(async (_id, params) => {
        if (params?.source === "bot_interaction") return { items: [bot], next_before: null };
        if (params?.before) return { items: [{ ...event, title: "Earlier health event", source: "health_changed" }], next_before: null };
        return { items: [event, bot], next_before: event.timestamp };
    });
    render(<HistoryHarness />);
    expect(await screen.findByText("Deployment completed")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Toggle details" }));
    expect(screen.getByText("Is CI passing?")).toBeInTheDocument();
    expect(screen.getByText("Yes, CI is passing.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByText("Earlier health event")).toBeInTheDocument();
    expect(listRepositoryActivity).toHaveBeenLastCalledWith("repo-a", { limit: "20", before: event.timestamp });
    fireEvent.click(screen.getByRole("button", { name: "Previous" }));
    expect(await screen.findByText("Deployment completed")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Bot Interactions" }));
    expect(await screen.findByText("Bot interaction")).toBeInTheDocument();
    expect(screen.queryByText("Deployment completed")).not.toBeInTheDocument();
    expect(listRepositoryActivity).toHaveBeenLastCalledWith("repo-a", { limit: "20", source: "bot_interaction" });
    vi.mocked(listRepositoryActivity).mockResolvedValueOnce(null);
    fireEvent.click(screen.getByRole("button", { name: "All Activity" }));
    expect(await screen.findByText("Activity feed is temporarily unavailable")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Deployment completed")).toBeInTheDocument();
});
