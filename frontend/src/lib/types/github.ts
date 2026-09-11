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
    created_at: string;
}
