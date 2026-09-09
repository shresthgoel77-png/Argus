import { SectionHeading } from "@/components/rm/section-heading";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

const interactions = [
    {
        prompt: "@RepoMedic what's the health of our CI pipelines this week?",
        response:
            "Your main branch workflow has a 94% success rate over the past 7 days (47/50 runs). Two failures were caused by a flaky integration test in `tests/api/test_auth.py` — it has failed 5 times in the last 30 days. One failure was a timeout in the Docker build step. I'd recommend investigating the flaky test first.",
    },
    {
        prompt: "@RepoMedic are there any critical dependency updates we're missing?",
        response:
            'You have 3 outdated dependencies with known vulnerabilities: `lodash@4.17.20` (prototype pollution, critical), `express@4.17.1` (open redirect, high), and `jsonwebtoken@8.5.1` (algorithm confusion, medium). I recommend prioritizing `lodash` — the fix is a minor version bump to 4.17.21.',
    },
    {
        prompt: "@RepoMedic summarize open PRs older than 5 days",
        response:
            'There are 4 PRs open longer than 5 days. #312 "Refactor auth middleware" (8 days, 0 reviews — assigned to @alice) is the most critical as it blocks two downstream PRs. #298 has approval but is waiting on a CI fix. The other two are draft PRs with no recent activity.',
    },
] as const;

export function GitHubBotSection() {
    return (
        <section className="border-y bg-card px-6 py-20 lg:px-8">
            <div className="mx-auto max-w-3xl">
                <SectionHeading
                    eyebrow="GitHub bot"
                    title="Ask @RepoMedic anything about your repository"
                    description="Mention @RepoMedic in any issue or PR comment to get instant, context-aware answers about your repository's health."
                />

                <div className="mt-10 space-y-6">
                    <Badge variant="secondary" className="text-xs">
                        Illustrative examples — not live functionality
                    </Badge>

                    {interactions.map((item, i) => (
                        <div key={i} className="space-y-3">
                            {/* User prompt */}
                            <div className="flex items-start gap-3">
                                <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-bold text-muted-foreground">
                                    U
                                </div>
                                <p className="rounded-lg border bg-background px-4 py-2.5 font-mono text-sm text-foreground">
                                    {item.prompt}
                                </p>
                            </div>

                            {/* Bot response */}
                            <div className="flex items-start gap-3 pl-10">
                                <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-bold text-accent-foreground">
                                    R
                                </div>
                                <Card className="flex-1 shadow-soft">
                                    <CardContent className="pt-4 text-sm leading-relaxed text-muted-foreground">
                                        {item.response}
                                    </CardContent>
                                </Card>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
}
