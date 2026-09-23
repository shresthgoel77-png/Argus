export interface FindingResponse {
    category: string;
    type: string;
    title: string;
    description: string;
    severity: string;
    source: string;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    evidence: Record<string, any>;
    id: string;
    repository_id: string;
    status: string;
    detected_at: string;
    updated_at: string;
    priority: string | null;
    acknowledged_at: string | null;
    resolved_at: string | null;
    resolution_source: string | null;
}

export interface FindingListResponse {
    items: FindingResponse[];
    total: number;
    limit: number;
    next_cursor?: string | null;
}

export interface FindingStatusUpdateRequest {
    status: "acknowledged" | "resolved" | "ignored" | "open";
}
