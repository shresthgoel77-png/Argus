"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import {
    mainNavItems,
    bottomNavItems,
    type NavItem,
} from "@/components/layout/app-sidebar";

type AppMobileNavProps = {
    trigger: React.ReactNode;
};

function MobileNavLink({ item, pathname }: { item: NavItem; pathname: string }) {
    const isActive =
        item.href === "/overview"
            ? pathname === "/overview"
            : pathname.startsWith(item.href);

    return (
        <Link
            href={item.href}
            className={cn(
                "flex items-center gap-3 rounded-md px-3 py-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                isActive
                    ? "bg-accent text-accent-foreground"
                    : "text-foreground hover:bg-muted",
            )}
            aria-current={isActive ? "page" : undefined}
        >
            <item.icon className="size-4 shrink-0" aria-hidden="true" />
            {item.label}
        </Link>
    );
}

export function AppMobileNav({ trigger }: AppMobileNavProps) {
    const pathname = usePathname();

    return (
        <Dialog>
            <DialogTrigger asChild>{trigger}</DialogTrigger>
            <DialogContent className="right-auto left-0 top-0 h-full max-w-[280px] translate-x-0 translate-y-0 rounded-none border-y-0 border-l-0 p-0 sm:rounded-r-lg">
                {/* Header */}
                <DialogHeader className="px-4 pt-4">
                    <DialogTitle className="flex items-center gap-2 text-left">
                        <span className="flex size-7 items-center justify-center rounded-md bg-accent text-xs font-bold text-accent-foreground">
                            R
                        </span>
                        RepoMedic
                    </DialogTitle>
                    <DialogDescription className="text-left">
                        Navigation
                    </DialogDescription>
                </DialogHeader>

                {/* Navigation */}
                <nav aria-label="Mobile app navigation" className="flex flex-1 flex-col gap-1 px-3 py-2">
                    {mainNavItems.map((item) => (
                        <MobileNavLink key={item.href} item={item} pathname={pathname} />
                    ))}

                    <div className="mt-auto">
                        <Separator className="mb-2" />
                        {bottomNavItems.map((item) => (
                            <MobileNavLink key={item.href} item={item} pathname={pathname} />
                        ))}
                    </div>
                </nav>
            </DialogContent>
        </Dialog>
    );
}
