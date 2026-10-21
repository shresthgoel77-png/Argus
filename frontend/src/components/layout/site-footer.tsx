import Link from "next/link";

import { satoshiBlack } from "@/app/fonts";

const footerGroups = [
  { title: "Product", links: ["Solutions"] },
  { title: "Legal", links: ["Privacy Policy", "Terms of Service"] },
];

export function SiteFooter() {
  return (
    <footer className="border-t bg-card">
      <div className="mx-auto grid w-full max-w-7xl gap-12 px-6 py-12 lg:grid-cols-[1.3fr_2fr] lg:px-8">
        <div className="space-y-4">
          <Link href="/" className="inline-flex items-center gap-2 rounded-md text-card-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <span className="flex size-8 items-center justify-center rounded-md bg-accent text-sm font-bold text-accent-foreground">A</span>
            <span className="text-lg font-semibold tracking-tight">Argus</span>
          </Link>
          <p className="max-w-xs text-sm leading-6 text-muted-foreground">
            Clearer signals for healthier repositories and more confident engineering teams.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-8">
          {footerGroups.map((group) => (
            <div key={group.title} className="space-y-4">
              <h2 className="text-sm font-semibold text-card-foreground">{group.title}</h2>
              <nav aria-label={`${group.title} links`} className="flex flex-col items-start gap-3">
                {group.links.map((link) => (
                  <Link
                    key={link}
                    href="#"
                    className="text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {link}
                  </Link>
                ))}
              </nav>
            </div>
          ))}
        </div>
      </div>
      <div className="bg-[#FFFFFF] px-6 lg:px-8">
        <div className="mx-auto w-full max-w-7xl py-8 text-center">
          <p className={`${satoshiBlack.className} inline-block whitespace-nowrap bg-[linear-gradient(90deg,#3B82F6_0%,#2563EB_50%,#1D4ED8_100%)] bg-clip-text text-[clamp(5rem,18vw,17rem)] font-black leading-none tracking-[-0.035em] text-transparent [font-synthesis:none]`}>
            ARGUS
          </p>
        </div>
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-2 border-t py-5 text-xs leading-5 text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <p>© {new Date().getFullYear()} Argus. All rights reserved.</p>
          <p>Built for teams that care about the details.</p>
        </div>
      </div>
    </footer>
  );
}
