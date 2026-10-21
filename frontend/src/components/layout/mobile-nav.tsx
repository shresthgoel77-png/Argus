"use client";

import Link from "next/link";
import { useState, type MouseEventHandler } from "react";
import { Menu } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

export type SiteNavItem = {
  label: string;
  href: string;
};

type MobileNavProps = {
  items: SiteNavItem[];
  onSectionClick?: MouseEventHandler<HTMLAnchorElement>;
};

export function MobileNav({ items, onSectionClick }: MobileNavProps) {
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="icon" className="md:hidden" aria-label="Open navigation menu">
          <Menu className="size-5" aria-hidden="true" />
        </Button>
      </DialogTrigger>
      <DialogContent className="left-auto right-0 top-0 h-full max-w-sm translate-x-0 translate-y-0 rounded-none border-y-0 border-r-0 p-6 sm:rounded-l-lg">
        <DialogHeader>
          <DialogTitle className="text-left">Argus</DialogTitle>
          <DialogDescription className="text-left">
            Engineering intelligence for the teams building what&apos;s next.
          </DialogDescription>
        </DialogHeader>
        <nav aria-label="Mobile navigation" className="flex flex-col gap-2">
          {items.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={(event) => {
                onSectionClick?.(event);
                if (event.defaultPrevented) setOpen(false);
              }}
              className="rounded-md px-3 py-3 text-sm font-medium text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="mt-auto grid gap-3 border-t pt-6">
          <a
            href="https://github.com/shresthgoel77-png/Argus"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="GitHub Repository"
            className="flex items-center justify-center justify-self-center rounded-full p-2 text-slate-700 transition-all duration-200 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <svg className="w-5 h-5 fill-current" viewBox="0 0 24 24" aria-hidden="true">
              <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
            </svg>
          </a>
          <Button className="w-full">Get started</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
