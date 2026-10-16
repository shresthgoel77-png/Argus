import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AppOverviewPage from "@/app/(app)/overview/page";
import { getDashboardOverview, getRepositories } from "@/lib/api/repositories";
import type { DashboardOverviewResponse } from "@/lib/types/overview";
import type { Repository } from "@/lib/types/github";

vi.mock("@/lib/api/repositories", () => ({
    getDashboardOverview: vi.fn(),
    getRepositories: vi.fn(),
}));

vi.mock("@/components/overview/needs-attention-list", () => ({ NeedsAttentionList: () => null }));
vi.mock("@/components/overview/category-intelligence-cards", () => ({ CategoryIntelligenceCards: () => null }));
vi.mock("@/components/overview/recent-activity-preview", () => ({ RecentActivityPreview: () => null }));
vi.mock("@/components/overview/repository-ai-summary-panel", () => ({ RepositoryAISummaryPanel: () => null }));
vi.mock("@/components/overview/trend-visualization", () => ({ TrendVisualization: () => null }));

describe("Overview monitoring status compatibility", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("renders safely when an older API omits assessment fields", async () => {
        const repository: Repository = {
            id: "repo-id",
            full_name: "owner/repo",
            private: false,
            default_branch: "main",
            monitoring_enabled: true,
            created_at: "2026-01-01T00:00:00Z",
        };
        const overview: DashboardOverviewResponse = {
            repository_id: "repo-id",
            health: null,
            needs_attention: { findings: [], health_snapshot: null, reasons: [] },
            activity_feed: [],
            ai_summary: { exists: false },
            trends: {
                window_days: 30,
                health_trend: { overall_delta: 0, category_deltas: [] },
                finding_velocity: { categories: [] },
            },
            finding_category_counts: {},
        };
        vi.mocked(getRepositories).mockResolvedValue([repository]);
        vi.mocked(getDashboardOverview).mockResolvedValue(overview);

        await act(async () => { render(<AppOverviewPage />); });

        expect(
            await screen.findByRole("heading", { name: "Assessment status: unknown" }),
        ).toBeInTheDocument();
        expect(screen.getByText("A complete health score is unavailable until every required check succeeds.")).toBeInTheDocument();
    });
});
