import { SectionHeading } from "@/components/rm/section-heading";
import { StatusBadge } from "@/components/rm/status-badge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const findings = [
    {
        severity: "critical" as const,
        status: "open" as const,
        title: "lodash pinned at 4.17.20 with prototype pollution CVE",
        description:
            "CVE-2021-23337 affects lodash versions prior to 4.17.21. This is a prototype pollution vulnerability that can lead to command injection in certain contexts. Bump to ≥4.17.21.",
        category: "Dependencies",
    },
    {
        severity: "high" as const,
        status: "open" as const,
        title: "deploy.yml workflow has failed 6 of last 10 runs",
        description:
            "The main deployment workflow is failing at a 60% rate due to intermittent Docker build timeouts. Average failure duration: 14 minutes. Consider adding retry logic or increasing the build timeout.",
        category: "CI/CD",
    },
    {
        severity: "medium" as const,
        status: "acknowledged" as const,
        title: "GHSA-2024-xxxx: jsonwebtoken algorithm confusion",
        description:
            "GitHub Security Advisory for jsonwebtoken@8.5.1 allows an attacker to bypass signature verification by supplying an asymmetric key where a symmetric key is expected. Upgrade to ≥9.0.0.",
        category: "Security",
    },
] as const;

export function FindingPreviewSection() {
    return (
        <section className="border-y bg-card px-6 py-20 lg:px-8">
            <div className="mx-auto max-w-4xl">
                <SectionHeading
                    eyebrow="Findings"
                    title="Every signal ranked, explained, and ready to act on"
                    description="Findings are prioritized by severity and enriched with context so your team knows exactly what to fix first. The examples below are illustrative."
                />

                <div className="mt-10 space-y-4">
                    {findings.map((finding) => (
                        <Card key={finding.title} className="shadow-soft">
                            <CardHeader className="pb-3">
                                <div className="flex flex-wrap items-center gap-2">
                                    <StatusBadge severity={finding.severity} />
                                    <StatusBadge status={finding.status} />
                                    <Badge variant="secondary">{finding.category}</Badge>
                                </div>
                                <CardTitle className="mt-2 text-base">{finding.title}</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <p className="text-sm leading-relaxed text-muted-foreground">
                                    {finding.description}
                                </p>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            </div>
        </section>
    );
}
