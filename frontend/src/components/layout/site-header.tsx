"use client";

import Link from "next/link";
import { useEffect, useState, type MouseEvent } from "react";

import { buttonVariants } from "@/components/ui/button";
import { MobileNav, type SiteNavItem } from "@/components/layout/mobile-nav";
import { getAuthLoginPath } from "@/lib/auth/config";
import { cn } from "@/lib/utils";

const navItems: SiteNavItem[] = [
  { label: "How it works", href: "#how-it-works" },
  { label: "Categories", href: "#categories" },
  { label: "Features", href: "#features" },
];

function handleSectionClick(event: MouseEvent<HTMLAnchorElement>) {
  if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

  const hash = event.currentTarget.hash;
  const section = document.getElementById(hash.slice(1));
  if (!section) return;

  event.preventDefault();
  if (window.location.hash !== hash) window.history.pushState(null, "", hash);
  requestAnimationFrame(() => {
    window.scrollTo({
      top: section.getBoundingClientRect().top + window.scrollY - 88,
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
    });
  });
}

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
      "fixed left-1/2 z-50 -translate-x-1/2 border-0 border-transparent transition-all duration-300 ease-out motion-reduce:transition-none [&>div>button]:border-0",
      scrolled
        ? "top-3 w-[92%] max-w-4xl rounded-full bg-white/95 px-6 py-2.5 text-slate-900 shadow-lg backdrop-blur-md [&>div>button]:bg-transparent [&>div>button]:text-slate-900 [&>div>button:hover]:bg-slate-100"
        : "top-0 w-full max-w-full rounded-none bg-transparent text-white shadow-none [&>div>button]:bg-white/15 [&>div>button]:text-white [&>div>button]:backdrop-blur-sm [&>div>button:hover]:bg-white/25",
    )}>
      <div className={cn("mx-auto flex w-full items-center justify-between transition-all duration-300 ease-out motion-reduce:transition-none", scrolled ? "h-10 gap-2" : "h-16 max-w-7xl gap-6 px-6 lg:px-8")}>
        <Link
          href="/"
          className={cn("flex shrink-0 items-center gap-2 rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2", scrolled ? "text-slate-900 hover:text-slate-700 focus-visible:ring-blue-600 focus-visible:ring-offset-white" : "text-white hover:text-white/80 focus-visible:ring-white focus-visible:ring-offset-blue-950")}
          aria-label="Argus home"
        >
          <span className="flex size-8 items-center justify-center rounded-md bg-accent text-sm font-bold text-accent-foreground">A</span>
          <span className="text-lg font-semibold tracking-tight">Argus</span>
        </Link>

        <nav aria-label="Primary navigation" className="hidden items-center gap-1 md:flex">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={handleSectionClick}
              className={cn("rounded-md px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2", scrolled ? "text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus-visible:ring-blue-600" : "text-white hover:bg-white/10 hover:text-white/80 focus-visible:ring-white")}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="hidden items-center gap-2 md:flex">
          <a
            href="https://github.com/shresthgoel77-png/Argus"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="GitHub Repository"
            className={cn("inline-flex items-center justify-center rounded-full p-2 transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2", scrolled ? "text-slate-700 hover:bg-slate-100 hover:text-slate-900 focus-visible:ring-blue-600 focus-visible:ring-offset-white" : "text-white/90 hover:bg-white/10 hover:text-white focus-visible:ring-white focus-visible:ring-offset-blue-950")}
          >
            <svg className="w-5 h-5 fill-current" viewBox="0 0 24 24" aria-hidden="true">
              <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
            </svg>
          </a>
          <Link href={getAuthLoginPath()} className={cn(buttonVariants(), "border-0 bg-blue-600 text-white hover:bg-blue-500", scrolled ? "rounded-full px-5 py-2 focus-visible:ring-blue-600 focus-visible:ring-offset-white" : "shadow-sm shadow-blue-300/30 backdrop-blur-sm focus-visible:ring-white focus-visible:ring-offset-blue-950")}>Get started</Link>
        </div>
        <MobileNav items={navItems} onSectionClick={handleSectionClick} />
      </div>
    </header>
  );
}
