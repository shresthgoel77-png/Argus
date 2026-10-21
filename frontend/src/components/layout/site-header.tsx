"use client";

import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { MobileNav, type SiteNavItem } from "@/components/layout/mobile-nav";
import { getAuthLoginPath } from "@/lib/auth/config";
import { cn } from "@/lib/utils";

const navItems: SiteNavItem[] = [
  { label: "Platform", href: "#platform" },
  { label: "Solutions", href: "#solutions" },
  { label: "Resources", href: "#resources" },
];

export function SiteHeader() {
  return (
    <header className="absolute inset-x-0 top-0 z-10 bg-transparent text-white [&>div>button]:border-white/30 [&>div>button]:bg-white/15 [&>div>button]:text-white [&>div>button]:backdrop-blur-sm [&>div>button:hover]:bg-white/25">
      <div className="mx-auto flex h-16 w-full max-w-7xl items-center justify-between gap-6 px-6 lg:px-8">
        <Link
          href="/"
          className="flex items-center gap-2 rounded-md text-white transition-colors hover:text-white/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-blue-950"
          aria-label="RepoMedic home"
        >
          <span className="flex size-8 items-center justify-center rounded-md bg-accent text-sm font-bold text-accent-foreground">R</span>
          <span className="text-lg font-semibold tracking-tight">RepoMedic</span>
        </Link>

        <nav aria-label="Primary navigation" className="hidden items-center gap-1 md:flex">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-md px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-white/10 hover:text-white/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="hidden items-center gap-2 md:flex">
          <Link href={getAuthLoginPath()} className={cn(buttonVariants({ variant: "ghost" }), "text-white hover:bg-white/10 hover:text-white/80 focus-visible:ring-white focus-visible:ring-offset-blue-950")}>Sign in</Link>
          <Link href={getAuthLoginPath()} className={cn(buttonVariants(), "border border-white/25 bg-blue-500/90 text-white shadow-sm shadow-blue-300/30 backdrop-blur-sm hover:bg-blue-500 focus-visible:ring-white focus-visible:ring-offset-blue-950")}>Get started</Link>
        </div>
        <MobileNav items={navItems} />
      </div>
    </header>
  );
}
