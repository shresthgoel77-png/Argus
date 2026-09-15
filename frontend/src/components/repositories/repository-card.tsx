"use client";

import * as React from "react";
import Link from "next/link";
import { Loader2 } from "lucide-react";

import { Repository } from "@/lib/types/github";
import { RepositoryHealthSnapshot } from "@/lib/types/health";
import { getRepositoryHealth } from "@/lib/api/health";
import { setMonitoringEnabled } from "@/lib/api/repositories";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";

export interface RepositoryCardProps {
    repository: Repository;
    onToggle: () => void;
}

function getScoreVariant(score: number) {
    if (score >= 80) return "success";
    if (score >= 50) return "warning";
    return "destructive";
}

export function RepositoryCard({ repository, onToggle }: RepositoryCardProps) {
    const [isPending, setIsPending] = React.useState(false);
    const [health, setHealth] = React.useState<RepositoryHealthSnapshot | null>(null);
    const [isLoadingHealth, setIsLoadingHealth] = React.useState(repository.monitoring_enabled);

    React.useEffect(() => {
        let active = true;
        if (repository.monitoring_enabled) {
            void getRepositoryHealth(repository.id.toString()).then((res) => {
                if (active) {
                    setHealth(res);
                    setIsLoadingHealth(false);
                }
            });
        }
        return () => {
            active = false;
        };
    }, [repository.id, repository.monitoring_enabled]);

    const handleToggle = async (checked: boolean) => {
        setIsPending(true);
        await setMonitoringEnabled(repository.id.toString(), checked);
        setIsPending(false);
        onToggle();
    };

    return (
        <div className="flex items-center justify-between gap-4 rounded-lg border bg-card p-6 transition-all hover:bg-muted/50">
            <div className="flex flex-col gap-2">
                <div className="flex items-center gap-3">
                    <Link
                        href={`/overview/repositories/${repository.id}`}
                        className="font-semibold transition-colors hover:text-primary hover:underline"
                    >
                        {repository.full_name}
                    </Link>
                    {repository.monitoring_enabled && (
                        isLoadingHealth ? (
                            <Loader2 className="size-4 animate-spin text-muted-foreground" />
                        ) : health ? (
                            <Badge variant={getScoreVariant(health.overall_score)}>
                                Score: {health.overall_score}
                            </Badge>
                        ) : (
                            <Badge variant="secondary">Not yet checked</Badge>
                        )
                    )}
                </div>
                <span className="text-xs text-muted-foreground">
                    {repository.private ? "Private Repository" : "Public Repository"}
                </span>
            </div>
            <div className="flex items-center gap-3">
                <span className="text-sm font-medium text-muted-foreground mr-2">Monitoring</span>
                <Switch
                    checked={repository.monitoring_enabled}
                    onCheckedChange={handleToggle}
                    disabled={isPending}
                />
            </div>
        </div>
    );
}
