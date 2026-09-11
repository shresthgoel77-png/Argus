import { GitBranch, Activity, Search, LayoutDashboard } from "lucide-react";
import { SectionHeading } from "@/components/rm/section-heading";

const steps = [
    {
        icon: GitBranch,
        title: "Connect GitHub",
        description:
            "Install the RepoMedic GitHub App on your organization or repositories. No code changes required.",
    },
    {
        icon: Activity,
        title: "Continuous monitoring",
        description:
            "RepoMedic watches workflows, dependencies, advisories, issues, and pull requests around the clock.",
    },
    {
        icon: Search,
        title: "Actionable findings",
        description:
            "AI-powered analysis surfaces what matters — severity-ranked findings with context and remediation guidance.",
    },
    {
        icon: LayoutDashboard,
        title: "Dashboard & bot",
        description:
            "Review findings in a unified dashboard or interact with @RepoMedic directly in GitHub issues and PRs.",
    },
] as const;

export function HowItWorksSection() {
    return (
        <section id="how-it-works" className="border-y bg-card px-6 py-20 lg:px-8">
            <div className="mx-auto max-w-5xl">
                <SectionHeading
                    eyebrow="How it works"
                    title="From repository data to engineering clarity in four steps"
                    className="text-center"
                />

                <div className="mt-14 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
                    {steps.map((step, i) => (
                        <div key={step.title} className="relative flex flex-col items-center text-center">
                            {/* Connector line — hidden on first item and mobile */}
                            {i > 0 && (
                                <div
                                    className="absolute -left-4 top-5 hidden h-px w-8 bg-border lg:block"
                                    aria-hidden="true"
                                />
                            )}

                            <div className="flex size-10 items-center justify-center rounded-md bg-muted text-muted-foreground">
                                <step.icon className="size-5" aria-hidden="true" />
                            </div>

                            <span className="mt-3 text-xs font-semibold uppercase tracking-wider text-accent">
                                Step {i + 1}
                            </span>

                            <h3 className="mt-2 text-base font-semibold text-foreground">
                                {step.title}
                            </h3>

                            <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                                {step.description}
                            </p>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
}
