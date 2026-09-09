export interface AuthUser {
    id: string;
    email: string;
    display_name: string | null;
    is_active: boolean;
    created_at: string;
}
