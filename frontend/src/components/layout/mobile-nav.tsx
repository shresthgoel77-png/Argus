"use client";

import Link from "next/link";
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
};

export function MobileNav({ items }: MobileNavProps) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" size="icon" className="md:hidden" aria-label="Open navigation menu">
          <Menu className="size-5" aria-hidden="true" />
        </Button>
      </DialogTrigger>
      <DialogContent className="left-auto right-0 top-0 h-full max-w-sm translate-x-0 translate-y-0 rounded-none border-y-0 border-r-0 p-6 sm:rounded-l-lg">
        <DialogHeader>
          <DialogTitle className="text-left">RepoMedic</DialogTitle>
          <DialogDescription className="text-left">
            Engineering intelligence for the teams building what&apos;s next.
          </DialogDescription>
        </DialogHeader>
        <nav aria-label="Mobile navigation" className="flex flex-col gap-2">
          {items.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-md px-3 py-3 text-sm font-medium text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="mt-auto grid gap-3 border-t pt-6">
          <Button variant="outline" className="w-full">Sign in</Button>
          <Button className="w-full">Get started</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
