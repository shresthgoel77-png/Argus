import type { ReactNode } from "react";
import { auth } from "@clerk/nextjs/server";

import { AppSidebar } from "@/components/layout/app-sidebar";
import { AppTopbar } from "@/components/layout/app-topbar";
import { ProtectedShell } from "@/components/auth/protected-shell";

/**
 * Preserve signed-out navigation for client pages. Protected data is authenticated
 * and ownership-scoped by the backend; server pages also check auth individually.
 */
export default async function AppLayout({ children }: { children: ReactNode }) {
    await auth.protect();

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
