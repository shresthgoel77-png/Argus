import Link from "next/link";

import { satoshiBlack } from "@/app/fonts";

const footerGroups = [
  { title: "Product", links: ["Solutions"] },
  { title: "Legal", links: ["Privacy Policy", "Terms of Service"] },
];

export function SiteFooter() {
  return (
    <footer className="border-t bg-card">
      <div className="mx-auto grid w-full max-w-7xl gap-10 px-6 pb-8 pt-12 sm:grid-cols-2 lg:grid-cols-[0.8fr_1.2fr_1fr] lg:gap-12 lg:px-8">
        <div>
          <Link href="/" className="inline-flex items-center gap-2 rounded-md text-card-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <span className="flex size-8 items-center justify-center rounded-md bg-accent text-sm font-bold text-accent-foreground">A</span>
            <span className="text-lg font-semibold tracking-tight">Argus</span>
          </Link>
        </div>
        <div className="grid grid-cols-2 gap-4 sm:gap-8">
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
                {group.title === "Legal" && (
                  <p className="pt-1 text-sm text-muted-foreground">
                    Built with <span className="text-red-500">❤️</span> by SG
                  </p>
                )}
              </nav>
            </div>
          ))}
        </div>
        <div className="max-w-xs space-y-3 justify-self-end text-sm leading-6 text-muted-foreground sm:col-span-2 lg:col-span-1">
          <p>
            Clearer signals for healthier repositories. Built for teams that scale with confidence and care about the details.
          </p>
          <p className="text-xs leading-5">© {new Date().getFullYear()} Argus. All rights reserved.</p>
        </div>
      </div>
      <div className="bg-[#FFFFFF] px-6 lg:px-8">
        <div className="mx-auto w-full max-w-7xl overflow-hidden pt-8 text-center">
          {/* Trim only Satoshi's space below the letterforms; keep the wordmark in normal flow. */}
          <p className={`${satoshiBlack.className} mx-auto -mb-[0.106em] w-fit whitespace-nowrap bg-[linear-gradient(90deg,#4B92F5_0%,#2864E8_50%,#2143B5_100%)] bg-clip-text text-[clamp(5rem,18vw,17rem)] font-black leading-none tracking-[-0.035em] text-transparent [font-synthesis:none]`}>
            ARGUS
          </p>
        </div>
      </div>
    </footer>
  );
}
