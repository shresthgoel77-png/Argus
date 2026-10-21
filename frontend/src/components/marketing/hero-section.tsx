"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function HeroSection() {
    const [scrolled, setScrolled] = useState(false);

    useEffect(() => {
        const updateScrolled = () => setScrolled(window.scrollY > 20);
        updateScrolled();
        window.addEventListener("scroll", updateScrolled, { passive: true });
        return () => window.removeEventListener("scroll", updateScrolled);
    }, []);

    return (
        <section
            className="relative z-0 flex min-h-screen w-full flex-col items-center gap-6 bg-white px-6 pb-24 pt-[max(6rem,14vh)] text-center lg:px-8"
        >
            <div
                aria-hidden="true"
                className={cn(
                    "pointer-events-none absolute inset-x-0 top-0 z-0 overflow-hidden transition-all duration-300 ease-out motion-reduce:transition-none",
                    scrolled ? "bottom-2.5 mx-2.5 rounded-b-2xl md:bottom-4 md:mx-4 md:rounded-b-3xl" : "bottom-0 mx-0 rounded-none",
                )}
                style={{
                    backgroundImage: "url('/Herobg.png')",
                    backgroundSize: "cover",
                    backgroundPosition: "center bottom",
                    backgroundRepeat: "no-repeat",
                }}
            />
            <h1 className="relative z-10 max-w-4xl text-3xl font-bold tracking-tight text-white [text-shadow:0_2px_12px_rgba(0,0,0,0.18)] sm:text-5xl md:text-6xl">
                GitHub has the data.{" "}
                <span className="text-sky-200">RepoMedic</span> turns it into
                engineering intelligence.
            </h1>

            <p className="relative z-10 max-w-2xl text-pretty text-base leading-relaxed text-white/90 [text-shadow:0_2px_8px_rgba(0,0,0,0.3)] sm:text-lg">
                Continuous monitoring for CI/CD health, dependency drift, security
                advisories, and code-quality signals — surfaced as actionable findings.
            </p>

            <div className="relative z-10 flex flex-col gap-3 sm:flex-row">
                <Link href="/login" className={cn(buttonVariants({ size: "lg" }), "border border-white/25 bg-blue-600 text-white shadow-lg shadow-blue-950/30 hover:bg-blue-500 focus-visible:ring-white focus-visible:ring-offset-blue-950")}>
                    Get started free
                </Link>
                <Link href="#how-it-works" className={cn(buttonVariants({ variant: "outline", size: "lg" }), "border-white/30 bg-white/15 text-white shadow-lg backdrop-blur-md hover:bg-white/25 hover:text-white focus-visible:ring-white focus-visible:ring-offset-blue-950")}>
                    See how it works
                </Link>
            </div>
        </section>
    );
}
