import {
    Workflow,
    Package,
    ShieldCheck,
    CircleDot,
    GitPullRequest,
    Code2,
} from "lucide-react";
import { SectionHeading } from "@/components/rm/section-heading";
import { StatCard } from "@/components/rm/stat-card";

const categories = [
    {
        label: "CI/CD Health",
        value: "97.2%",
        description: "Workflow success rate (7 d)",
        icon: Workflow,
    },
    {
        label: "Dependencies",
        value: "3",
        description: "Outdated packages flagged",
        icon: Package,
    },
    {
        label: "Security",
        value: "1 critical",
        description: "Advisories requiring action",
        icon: ShieldCheck,
    },
    {
        label: "Issues",
        value: "12",
        description: "Open issues needing triage",
        icon: CircleDot,
    },
    {
        label: "Pull Requests",
        value: "4.2 h",
        description: "Avg. time to first review",
        icon: GitPullRequest,
    },
    {
        label: "Code Quality",
        value: "A",
        description: "Composite quality grade",
        icon: Code2,
    },
] as const;

export function FeaturesSection() {
    return (
        <section className="mx-auto w-full max-w-5xl px-6 py-20 lg:px-8">
            <SectionHeading
                eyebrow="Monitoring categories"
                title="Six dimensions of repository health, always up to date"
                description="Each category is continuously analyzed and summarized into actionable findings. The values below are illustrative."
            />

            <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {categories.map((cat) => (
                    <StatCard
                        key={cat.label}
                        label={cat.label}
                        value={cat.value}
                        description={cat.description}
                        icon={cat.icon}
                    />
                ))}
            </div>
        </section>
    );
}
