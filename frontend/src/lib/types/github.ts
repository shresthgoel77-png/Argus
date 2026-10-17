export interface GitHubConnection {
    id: string;
    installation_id: number;
    account_login: string;
    account_type: string;
    status: string;
    created_at: string;
}

export interface AvailableRepository {
    github_repo_id: number;
    full_name: string;
    private: boolean;
    default_branch: string | null;
    already_added: boolean;
}

export interface Repository {
    id: string;
    full_name: string;
    private: boolean;
    default_branch: string | null;
    monitoring_enabled: boolean;
    monitoring_status?: string | null;
    monitoring_checks?: Record<string, { status: string; error_message: string | null; checked_at: string | null }> | null;
    last_monitoring_at?: string | null;
    created_at: string;
}

export interface RepositoryCheckResult {
    correlation_id: string;
    status: string;
    checks: Record<string, {
        status: string;
        error_message?: string | null;
        checked_at?: string | null;
    }>;
    reason?: string | null;
}
