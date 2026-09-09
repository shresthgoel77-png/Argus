import Link from "next/link";

const footerGroups = [
  { title: "Product", links: ["Platform", "Changelog", "Roadmap"] },
  { title: "Company", links: ["About", "Careers", "Contact"] },
  { title: "Resources", links: ["Documentation", "Guides", "Support"] },
];

export function SiteFooter() {
  return (
    <footer className="border-t bg-card">
      <div className="mx-auto grid w-full max-w-7xl gap-12 px-6 py-12 lg:grid-cols-[1.3fr_2fr] lg:px-8">
        <div className="space-y-4">
          <Link href="/" className="inline-flex items-center gap-2 rounded-md text-card-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <span className="flex size-8 items-center justify-center rounded-md bg-accent text-sm font-bold text-accent-foreground">R</span>
            <span className="text-lg font-semibold tracking-tight">RepoMedic</span>
          </Link>
          <p className="max-w-xs text-sm leading-6 text-muted-foreground">
            Clearer signals for healthier repositories and more confident engineering teams.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-8 sm:grid-cols-3">
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
      <div className="border-t">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-2 px-6 py-6 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between lg:px-8">
          <p>© {new Date().getFullYear()} RepoMedic. All rights reserved.</p>
          <p>Built for teams that care about the details.</p>
        </div>
      </div>
    </footer>
  );
}
