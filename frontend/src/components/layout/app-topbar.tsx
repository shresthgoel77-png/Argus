"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { AppMobileNav } from "@/components/layout/app-mobile-nav";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth/use-auth";
import { Menu } from "lucide-react";

export function AppTopbar() {
    const router = useRouter();
    const { user, isLoading, logout } = useAuth();
    const [isLoggingOut, setIsLoggingOut] = useState(false);

    async function handleLogout() {
        setIsLoggingOut(true);
        await logout();
        router.replace("/");
    }

    const identity = user?.display_name || user?.email;
    const avatarFallback = identity?.slice(0, 1).toUpperCase();

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

            {/* Breadcrumb placeholder */}
            <div className="flex-1">
                <h1 className="text-sm font-semibold text-foreground">Dashboard</h1>
            </div>

            {/* User affordance */}
            {isLoading ? (
                <div className="flex items-center gap-3" aria-label="Loading account">
                    <Skeleton className="size-8 rounded-full" />
                    <Skeleton className="hidden h-4 w-32 sm:block" />
                </div>
            ) : user ? (
                <div className="flex items-center gap-3">
                    <div className="hidden text-right sm:block">
                        <p className="text-sm font-medium text-foreground">{identity}</p>
                        {user.display_name ? <p className="text-xs text-muted-foreground">{user.email}</p> : null}
                    </div>
                    <Avatar className="size-8">
                        <AvatarFallback className="text-xs">{avatarFallback}</AvatarFallback>
                    </Avatar>
                    <Button variant="ghost" size="sm" onClick={handleLogout} loading={isLoggingOut}>
                        Log out
                    </Button>
                </div>
            ) : null}
        </header>
    );
}
