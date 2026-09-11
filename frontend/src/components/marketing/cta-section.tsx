import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";

export function CtaSection() {
    return (
        <section className="border-t bg-card px-6 py-24 text-center lg:px-8">
            <div className="mx-auto max-w-2xl space-y-6">
                <h2 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
                    Ready to see what your repos are telling you?
                </h2>

                <p className="text-base leading-relaxed text-muted-foreground">
                    Start monitoring your repositories in minutes. No credit card
                    required, no code changes needed — just connect GitHub and go.
                </p>

                <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
                    <Link href="/login" className={buttonVariants({ size: "lg" })}>
                        Get started free
                    </Link>
                    <Link href="#how-it-works" className={buttonVariants({ variant: "outline", size: "lg" })}>
                        See how it works
                    </Link>
                </div>
            </div>
        </section>
    );
}
