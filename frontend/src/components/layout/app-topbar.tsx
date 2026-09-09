"use client";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { AppMobileNav } from "@/components/layout/app-mobile-nav";
import { Menu } from "lucide-react";

export function AppTopbar() {
    return (
        <header className="sticky top-0 z-30 flex h-14 items-center gap-4 border-b bg-card/95 px-4 backdrop-blur lg:px-6">
            {/* Mobile nav trigger — visible only below lg */}
            <AppMobileNav
                trigger={
                    <Button
                        variant="outline"
                        size="icon"
                        className="size-9 lg:hidden"
                        aria-label="Open navigation menu"
                    >
                        <Menu className="size-5" aria-hidden="true" />
                    </Button>
                }
            />

            {/* Breadcrumb placeholder — Phase 6 will populate with real breadcrumbs */}
            <div className="flex-1">
                <h1 className="text-sm font-semibold text-foreground">Dashboard</h1>
            </div>

            {/* User affordance — generic placeholder, no fabricated identity */}
            <div className="flex items-center gap-3">
                <Avatar className="size-8">
                    <AvatarFallback className="text-xs">U</AvatarFallback>
                </Avatar>
            </div>
        </header>
    );
}
