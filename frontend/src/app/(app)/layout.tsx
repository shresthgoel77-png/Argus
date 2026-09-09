import type { ReactNode } from "react";

import { AppSidebar } from "@/components/layout/app-sidebar";
import { AppTopbar } from "@/components/layout/app-topbar";

/**
 * Authenticated app shell layout.
 *
 * SECURITY NOTE — TEMPORARY STATE:
 * This route group is currently UNPROTECTED and publicly reachable.
 * This is an intentional temporary state during early development.
 *
 * TODO (Phase 3): Add authentication check / route protection here.
 * Phase 3 will wrap this layout with an auth guard that redirects
 * unauthenticated users to the login page. Until then, all /app/*
 * routes are accessible without authentication.
 */
export default function AppLayout({ children }: { children: ReactNode }) {
    return (
        <div className="flex h-screen overflow-hidden">
            {/* Sidebar — fixed left column, hidden on mobile */}
            <AppSidebar />

            {/* Main content area */}
            <div className="flex flex-1 flex-col overflow-hidden">
                <AppTopbar />
                <main className="flex-1 overflow-y-auto p-4 lg:p-6">{children}</main>
            </div>
        </div>
    );
}
