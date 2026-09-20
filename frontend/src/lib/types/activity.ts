export type ActivitySource =
    | "github_event"
    | "finding_detected"
    | "finding_resolved"
    | "health_changed"
    | "bot_interaction";

export interface BotInteractionDetails {
    intent: string;
    status: string;
    skip_reason: string | null;
    response_text: string | null;
    requester_github_login: string;
    question_text: string;
}

export interface ActivityItem {
    source: ActivitySource;
    timestamp: string;
    title: string;
    summary: string;
    reference_id: string;
    details?: BotInteractionDetails | null;
}

export interface ActivityFeedResponse {
    items: ActivityItem[];
    next_before: string | null;
}

