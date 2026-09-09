import { Heart, AlertTriangle, CheckCircle2, Clock } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { SectionHeading } from "@/components/rm/section-heading";
import { StatCard } from "@/components/rm/stat-card";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

interface Metric {
    label: string;
    value: string;
    description: string;
    icon: LucideIcon;
    trend?: string;
}

const metrics: Metric[] = [
    {
        label: "Repo Health Score",
        value: "82/100",
        description: "Composite — updated daily",
        icon: Heart,
    },
    {
        label: "Open Findings",
        value: "7",
        description: "3 critical · 2 high · 2 medium",
        icon: AlertTriangle,
    },
    {
        label: "Resolved This Week",
        value: "14",
        description: "↑ 40% vs. last week",
        icon: CheckCircle2,
        trend: "+40%",
    },
    {
        label: "Avg. Resolution Time",
        value: "1.6 d",
        description: "Down from 2.3 d last month",
        icon: Clock,
    },
];

/* Simple illustrative bar data — heights represent relative values */
const bars = [
    { label: "Mon", height: "60%" },
    { label: "Tue", height: "45%" },
    { label: "Wed", height: "80%" },
    { label: "Thu", height: "35%" },
    { label: "Fri", height: "70%" },
    { label: "Sat", height: "20%" },
    { label: "Sun", height: "50%" },
] as const;

export function DashboardPreviewSection() {
    return (
        <section className="mx-auto w-full max-w-5xl px-6 py-20 lg:px-8">
            <SectionHeading
                eyebrow="Dashboard"
                title="Your repository health at a glance"
                description="A unified view of every signal RepoMedic tracks — from CI success rates to dependency freshness. The dashboard below is illustrative."
            />

            <Card className="mt-10 overflow-hidden shadow-card">
                <CardHeader className="border-b bg-muted/50 pb-3">
                    <div className="flex items-center justify-between">
                        <p className="text-sm font-semibold text-foreground">
                            acme-corp / web-platform
                        </p>
                        <Badge variant="secondary" className="text-xs">
                            Preview
                        </Badge>
                    </div>
                </CardHeader>

                <CardContent className="space-y-6 pt-6">
                    {/* Stat cards row */}
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                        {metrics.map((m) => (
                            <StatCard
                                key={m.label}
                                label={m.label}
                                value={m.value}
                                description={m.description}
                                icon={m.icon}
                                trend={m.trend}
                            />
                        ))}
                    </div>

                    {/* Illustrative bar chart */}
                    <div className="space-y-2">
                        <p className="text-xs font-medium text-muted-foreground">
                            Findings resolved per day (illustrative)
                        </p>
                        <div className="flex h-32 items-end gap-2">
                            {bars.map((bar) => (
                                <div
                                    key={bar.label}
                                    className="flex flex-1 flex-col items-center gap-1"
                                >
                                    <div className="flex h-full w-full items-end rounded-sm bg-accent/10">
                                        <div
                                            className="w-full rounded-sm bg-accent"
                                            style={{ height: bar.height }}
                                        />
                                    </div>
                                    <span className="text-[10px] text-muted-foreground">
                                        {bar.label}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                </CardContent>
            </Card>
        </section>
    );
}
