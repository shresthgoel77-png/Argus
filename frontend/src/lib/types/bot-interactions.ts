export interface BotInteraction {
    id: string;
    repository_id: string;
    intent: string;
    question_text: string;
    status: string;
    skip_reason: string | null;
    response_text: string | null;
    requester_github_login: string;
    created_at: string;
    github_reply_comment_id: number | null;
}

export interface BotInteractionListResponse {
    items: BotInteraction[];
    total: number;
    limit: number;
    next_cursor?: string | null;
}