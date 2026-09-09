import Link from "next/link";

import { Button } from "@/components/ui/button";
import { MobileNav, type SiteNavItem } from "@/components/layout/mobile-nav";

const navItems: SiteNavItem[] = [
  { label: "Platform", href: "#platform" },
  { label: "Solutions", href: "#solutions" },
  { label: "Resources", href: "#resources" },
];

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur">
      <div className="mx-auto flex h-16 w-full max-w-7xl items-center justify-between gap-6 px-6 lg:px-8">
        <Link
          href="/"
          className="flex items-center gap-2 rounded-md text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
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
              className="rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="hidden items-center gap-2 md:flex">
          <Button variant="ghost">Sign in</Button>
          <Button>Get started</Button>
        </div>
        <MobileNav items={navItems} />
      </div>
    </header>
  );
}
