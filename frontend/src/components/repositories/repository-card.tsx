"use client";

import * as React from "react";
import { Repository } from "@/lib/types/github";
import { Switch } from "@/components/ui/switch";
import { setMonitoringEnabled } from "@/lib/api/repositories";

export interface RepositoryCardProps {
    repository: Repository;
    onToggle: () => void;
}

export function RepositoryCard({ repository, onToggle }: RepositoryCardProps) {
    const [isPending, setIsPending] = React.useState(false);

    const handleToggle = async (checked: boolean) => {
        setIsPending(true);
        await setMonitoringEnabled(repository.id, checked);
        setIsPending(false);
        onToggle();
    };

    return (
        <div className="flex items-center justify-between gap-4 rounded-lg border bg-card p-6 transition-all">
            <div className="flex flex-col gap-1">
                <span className="font-semibold">{repository.full_name}</span>
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
