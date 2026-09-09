"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
    Activity,
    CircleDot,
    GitFork,
    GitPullRequest,
    LayoutDashboard,
    Search,
    Settings,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Separator } from "@/components/ui/separator";

type NavItem = {
    label: string;
    href: string;
    icon: React.ComponentType<{ className?: string }>;
};

const mainNavItems: NavItem[] = [
    { label: "Overview", href: "/app", icon: LayoutDashboard },
    { label: "Repositories", href: "/app/repositories", icon: GitFork },
    { label: "Findings", href: "/app/findings", icon: Search },
    { label: "Pull Requests", href: "/app/pull-requests", icon: GitPullRequest },
    { label: "Issues", href: "/app/issues", icon: CircleDot },
    { label: "Activity", href: "/app/activity", icon: Activity },
];

const bottomNavItems: NavItem[] = [
    { label: "Settings", href: "/app/settings", icon: Settings },
];

function NavLink({ item, pathname }: { item: NavItem; pathname: string }) {
    const isActive =
        item.href === "/app"
            ? pathname === "/app"
            : pathname.startsWith(item.href);

    return (
        <Link
            href={item.href}
            className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                isActive
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
            aria-current={isActive ? "page" : undefined}
        >
            <item.icon className="size-4 shrink-0" aria-hidden="true" />
            {item.label}
        </Link>
    );
}

export function AppSidebar() {
    const pathname = usePathname();

    return (
        <aside className="hidden lg:flex lg:w-60 lg:shrink-0 lg:flex-col lg:border-r lg:bg-card">
            {/* Logo */}
            <div className="flex h-14 items-center gap-2 px-4">
                <span className="flex size-7 items-center justify-center rounded-md bg-accent text-xs font-bold text-accent-foreground">
                    R
                </span>
                <span className="text-sm font-semibold tracking-tight">RepoMedic</span>
            </div>

            <Separator />

            {/* Main navigation */}
            <nav aria-label="App navigation" className="flex flex-1 flex-col gap-1 px-3 py-3">
                {mainNavItems.map((item) => (
                    <NavLink key={item.href} item={item} pathname={pathname} />
                ))}

                {/* Bottom-pinned items */}
                <div className="mt-auto">
                    <Separator className="mb-3" />
                    {bottomNavItems.map((item) => (
                        <NavLink key={item.href} item={item} pathname={pathname} />
                    ))}
                </div>
            </nav>
        </aside>
    );
}

export { mainNavItems, bottomNavItems, type NavItem };
