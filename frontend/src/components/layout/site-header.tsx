"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

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
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const updateScrolled = () => setScrolled(window.scrollY > 20);
    updateScrolled();
    window.addEventListener("scroll", updateScrolled, { passive: true });
    return () => window.removeEventListener("scroll", updateScrolled);
  }, []);

  return (
    <header className={cn(
      "fixed left-1/2 z-50 -translate-x-1/2 border transition-all duration-300 ease-out motion-reduce:transition-none",
      scrolled
        ? "top-3 w-[92%] max-w-4xl rounded-full border-slate-200/70 bg-white/95 px-6 py-2.5 text-slate-900 shadow-lg backdrop-blur-md [&>div>button]:border-slate-200 [&>div>button]:bg-transparent [&>div>button]:text-slate-900 [&>div>button:hover]:bg-slate-100"
        : "top-0 w-full max-w-full rounded-none border-transparent bg-transparent text-white [&>div>button]:border-white/30 [&>div>button]:bg-white/15 [&>div>button]:text-white [&>div>button]:backdrop-blur-sm [&>div>button:hover]:bg-white/25",
    )}>
      <div className={cn("mx-auto flex w-full items-center justify-between transition-all duration-300 ease-out motion-reduce:transition-none", scrolled ? "h-10 gap-2" : "h-16 max-w-7xl gap-6 px-6 lg:px-8")}>
        <Link
          href="/"
          className={cn("flex shrink-0 items-center gap-2 rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2", scrolled ? "text-slate-900 hover:text-slate-700 focus-visible:ring-blue-600 focus-visible:ring-offset-white" : "text-white hover:text-white/80 focus-visible:ring-white focus-visible:ring-offset-blue-950")}
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
              className={cn("rounded-md px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2", scrolled ? "text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus-visible:ring-blue-600" : "text-white hover:bg-white/10 hover:text-white/80 focus-visible:ring-white")}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="hidden items-center gap-2 md:flex">
          <Link href={getAuthLoginPath()} className={cn(buttonVariants({ variant: "ghost" }), scrolled ? "text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus-visible:ring-blue-600 focus-visible:ring-offset-white" : "text-white hover:bg-white/10 hover:text-white/80 focus-visible:ring-white focus-visible:ring-offset-blue-950")}>Sign in</Link>
          <Link href={getAuthLoginPath()} className={cn(buttonVariants(), "text-white hover:bg-blue-500", scrolled ? "rounded-full bg-blue-600 px-5 py-2 focus-visible:ring-blue-600 focus-visible:ring-offset-white" : "border border-white/25 bg-blue-500/90 shadow-sm shadow-blue-300/30 backdrop-blur-sm focus-visible:ring-white focus-visible:ring-offset-blue-950")}>Get started</Link>
        </div>
        <MobileNav items={navItems} />
      </div>
    </header>
  );
}
