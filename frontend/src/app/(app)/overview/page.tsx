import { Activity, AlertTriangle, HeartPulse, ShieldAlert } from "lucide-react";

import { EmptyState } from "@/components/rm/empty-state";
import { SectionHeading } from "@/components/rm/section-heading";

export default function AppOverviewPage() {
    return (
        <div className="space-y-6">
            <SectionHeading
                eyebrow="Workspace"
                title="Overview"
                description="A health check across your connected repositories and engineering activity."
            />

            <div className="grid gap-4 xl:grid-cols-2">
                <section className="space-y-3" aria-labelledby="health-score-heading">
                    <h2 id="health-score-heading" className="text-lg font-semibold tracking-tight">Health score</h2>
                    <EmptyState
                        icon={<HeartPulse className="size-6" aria-hidden="true" />}
                        title="No health score yet"
                        description="Connect a repository to start measuring repository health."
                    />
                </section>

                <section className="space-y-3" aria-labelledby="attention-heading">
                    <h2 id="attention-heading" className="text-lg font-semibold tracking-tight">Needs attention</h2>
                    <EmptyState
                        icon={<AlertTriangle className="size-6" aria-hidden="true" />}
                        title="Nothing needs attention"
                        description="Prioritized work will appear here once repository data is available."
                    />
                </section>

                <section className="space-y-3" aria-labelledby="critical-findings-heading">
                    <h2 id="critical-findings-heading" className="text-lg font-semibold tracking-tight">Critical and high findings</h2>
                    <EmptyState
                        icon={<ShieldAlert className="size-6" aria-hidden="true" />}
                        title="No findings to review"
                        description="Critical and high-severity findings will appear after a repository is connected."
                    />
                </section>

                <section className="space-y-3" aria-labelledby="recent-activity-heading">
                    <h2 id="recent-activity-heading" className="text-lg font-semibold tracking-tight">Recent activity</h2>
                    <EmptyState
                        icon={<Activity className="size-6" aria-hidden="true" />}
                        title="No recent activity"
                        description="Repository events and reviews will appear here when activity is available."
                    />
                </section>
            </div>
        </div>
    );
}
