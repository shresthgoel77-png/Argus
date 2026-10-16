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
    const monitoringStatus = repository.monitoring_status ?? "unknown";
    const [isPending, setIsPending] = React.useState(false);
    const [toggleError, setToggleError] = React.useState<string | null>(null);
    const [health, setHealth] = React.useState<RepositoryHealthSnapshot | null>(null);
    const [isLoadingHealth, setIsLoadingHealth] = React.useState(
        repository.monitoring_enabled && monitoringStatus === "success",
    );

    React.useEffect(() => {
        let active = true;
        if (repository.monitoring_enabled && monitoringStatus === "success") {
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
    }, [repository.id, repository.monitoring_enabled, monitoringStatus]);

    const handleToggle = async (checked: boolean) => {
        setIsPending(true);
        setToggleError(null);
        const updated = await setMonitoringEnabled(repository.id, checked);
        setIsPending(false);
        if (updated) {
            onToggle();
        } else {
            setToggleError("Monitoring could not be updated. Please try again.");
        }
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
                        monitoringStatus === "queued" || monitoringStatus === "running" || isLoadingHealth ? (
                            <Loader2 className="size-4 animate-spin text-muted-foreground" />
                        ) : monitoringStatus === "success" && health ? (
                            <Badge variant={getScoreVariant(health.overall_score)}>
                                Score: {health.overall_score}
                            </Badge>
                        ) : (
                            <Badge variant="secondary">
                                {monitoringStatus.replace(/_/g, " ")}
                            </Badge>
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
            {toggleError && <p className="w-full text-sm text-destructive" role="alert">{toggleError}</p>}
        </div>
    );
}
