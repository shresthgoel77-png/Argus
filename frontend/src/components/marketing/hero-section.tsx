import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";

export function HeroSection() {
    return (
        <section className="flex flex-col items-center gap-8 px-6 pb-24 pt-20 text-center md:pb-32 md:pt-28 lg:px-8">
            <h1 className="max-w-3xl text-4xl font-bold tracking-tight text-foreground sm:text-5xl md:text-6xl">
                GitHub has the data.{" "}
                <span className="text-accent">RepoMedic</span> turns it into
                engineering intelligence.
            </h1>

            <p className="max-w-2xl text-lg leading-relaxed text-muted-foreground">
                Continuous monitoring for CI/CD health, dependency drift, security
                advisories, and code-quality signals — surfaced as actionable findings
                in a dashboard and a GitHub bot that meets your team where they work.
            </p>

            <div className="flex flex-col gap-3 sm:flex-row">
                <Link href="/login" className={buttonVariants({ size: "lg" })}>
                    Get started free
                </Link>
                <Link href="#how-it-works" className={buttonVariants({ variant: "outline", size: "lg" })}>
                    See how it works
                </Link>
            </div>
        </section>
    );
}
