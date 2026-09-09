import type { ReactNode } from "react";

import { AppSidebar } from "@/components/layout/app-sidebar";
import { AppTopbar } from "@/components/layout/app-topbar";
import { ProtectedShell } from "@/components/auth/protected-shell";

/**
 * Client-side protection is appropriate while this app uses static dashboard data.
 * Server-side protection will be needed before introducing sensitive server-rendered data.
 */
export default function AppLayout({ children }: { children: ReactNode }) {
    return (
        <ProtectedShell>
            <div className="flex h-screen overflow-hidden">
                {/* Sidebar — fixed left column, hidden on mobile */}
                <AppSidebar />

                {/* Main content area */}
                <div className="flex flex-1 flex-col overflow-hidden">
                    <AppTopbar />
                    <main className="flex-1 overflow-y-auto p-4 lg:p-6">{children}</main>
                </div>
            </div>
        </ProtectedShell>
    );
}
