import type { AIAnalysisResponse } from "./ai-analysis";
import type { FindingResponse } from "./findings";
import type { RepositoryHealthSnapshot } from "./health";

export interface OverviewActivityItem {
    source: string;
    timestamp: string;
    title: string;
    summary: string;
    reference_id: string;
}

export interface DashboardOverviewNeedsAttention {
    findings: FindingResponse[];
    health_snapshot: RepositoryHealthSnapshot | null;
    reasons: string[];
}

export interface DashboardOverviewTrendDelta {
    category: string;
    delta: number;
}

export interface DashboardOverviewVelocityItem {
    category: string;
    detected: number;
    resolved: number;
}

export interface DashboardOverviewTrends {
    window_days: number;
    health_trend: {
        overall_delta: number;
        category_deltas: DashboardOverviewTrendDelta[];
    };
    finding_velocity: {
        categories: DashboardOverviewVelocityItem[];
    };
}

export interface DashboardOverviewResponse {
    repository_id: string;
    health: RepositoryHealthSnapshot | null;
    needs_attention: DashboardOverviewNeedsAttention;
    activity_feed: OverviewActivityItem[];
    ai_summary: AIAnalysisResponse;
    trends: DashboardOverviewTrends;
    finding_category_counts: Record<string, number>;
}
