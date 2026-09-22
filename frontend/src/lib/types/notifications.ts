export interface Notification {
    id: string;
    user_id: string;
    repository_id: string | null;
    notification_type: string;
    severity: string;
    title: string;
    message: string;
    reference_type: string;
    reference_id: string;
    read_at: string | null;
    email_status: string;
    email_sent_at: string | null;
    email_error_message: string | null;
    created_at: string;
}

export interface UnreadCountResponse { count: number; }