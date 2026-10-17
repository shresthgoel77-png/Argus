export type HealthCategory =
    | "ci_cd"
    | "dependencies"
    | "security"
    | "issues"
    | "pull_requests"
    | "code_quality";

export interface RepositoryHealthSnapshot {
    overall_score: number;
    category_scores: Partial<Record<HealthCategory, number>>;
    reasons: string[];
    computed_at: string;
    previous_score: number | null;
    coverage?: {
        assessed_categories: HealthCategory[];
        excluded_categories: Partial<Record<HealthCategory, { status: string; reason: string }>>;
    } | null;
}

// Re-using RepositoryHealthSnapshot for history items as it matches exactly
export type HealthSnapshotHistoryItem = RepositoryHealthSnapshot;

export interface HealthSnapshotListResponse {
    items: HealthSnapshotHistoryItem[];
    total: number;
    limit: number;
    offset: number;
}
