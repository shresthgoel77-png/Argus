import { act, cleanup, render, screen } from "@testing-library/react";
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
        cleanup();
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
        expect(screen.getByText("Health uses successfully assessed categories. Excluded categories do not affect the score.")).toBeInTheDocument();
    });

    const baseOverview = (): DashboardOverviewResponse => ({
        repository_id: "repo-id", health: null,
        needs_attention: { findings: [], health_snapshot: null, reasons: [] },
        activity_feed: [], ai_summary: { exists: false },
        trends: { window_days: 30, health_trend: { overall_delta: 0, category_deltas: [] }, finding_velocity: { categories: [] } },
        finding_category_counts: {}, monitoring_status: "partial_failure",
    });

    async function renderOverview(overview: DashboardOverviewResponse) {
        vi.mocked(getRepositories).mockResolvedValue([{
            id: "repo-id", full_name: "owner/repo", private: false,
            monitoring_enabled: true, created_at: "2026-01-01T00:00:00Z",
        }]);
        vi.mocked(getDashboardOverview).mockResolvedValue(overview);
        await act(async () => { render(<AppOverviewPage />); });
    }

    it.each([4, 5, 6])("shows numeric health and dynamic %i/6 coverage", async (count) => {
        const overview = baseOverview();
        const categories = ["security", "dependencies", "issues", "pull_requests", "code_quality", "ci_cd"] as const;
        overview.health = {
            overall_score: 98, category_scores: { code_quality: 90 }, reasons: [],
            computed_at: "2026-10-17T10:00:00Z", previous_score: null,
            coverage: {
                assessed_categories: categories.slice(0, count),
                excluded_categories: count < 6 ? { ci_cd: { status: "unavailable", reason: "GitHub has no workflow-run history to assess." } } : {},
            },
        };
        await renderOverview(overview);
        expect(screen.getByText("98")).toBeInTheDocument();
        if (count < 6) {
            expect(screen.getByRole("heading", { name: `Health score — partial coverage (${count}/6 categories assessed)` })).toBeInTheDocument();
            expect(screen.getByText(/Excluded ci cd: unavailable/)).toBeInTheDocument();
        } else {
            expect(screen.getByText("6/6 categories assessed.")).toBeInTheDocument();
        }
        expect(screen.getByRole("heading", { name: "Assessment status: partial failure" })).toBeInTheDocument();
        expect(screen.queryByText("No health score yet")).not.toBeInTheDocument();
    });

    it("labels fallback as historical with timestamp and unknown coverage", async () => {
        const overview = baseOverview();
        overview.last_recorded_health = {
            overall_score: 100, category_scores: { security: 100 }, reasons: [],
            computed_at: "2026-10-14T21:47:46Z", previous_score: null, coverage: null,
        };
        await renderOverview(overview);
        expect(screen.getByText("Last recorded score")).toBeInTheDocument();
        expect(screen.getByText("Historical")).toBeInTheDocument();
        expect(screen.getByText(/Recorded .*Historical score, not a current assessment. Coverage unknown./)).toBeInTheDocument();
        expect(screen.queryByText("No health score yet")).not.toBeInTheDocument();
    });

    it("shows the empty state only when neither current nor historical health exists", async () => {
        await renderOverview(baseOverview());
        expect(screen.getByText("No health score yet")).toBeInTheDocument();
        expect(screen.queryByText("Last recorded score")).not.toBeInTheDocument();
    });
});
