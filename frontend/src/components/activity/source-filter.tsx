"use client";

import * as React from "react";
import type { ActivitySource } from "@/lib/types/activity";

interface SourceFilterProps {
    value: ActivitySource | "all";
    onChange: (value: ActivitySource | "all") => void;
}

const SOURCES: { value: ActivitySource | "all"; label: string }[] = [
    { value: "all", label: "All Activity" },
    { value: "github_event", label: "GitHub Events" },
    { value: "finding_detected", label: "Findings Detected" },
    { value: "finding_resolved", label: "Findings Resolved" },
    { value: "health_changed", label: "Health Changes" },
    { value: "bot_interaction", label: "Bot Interactions" },
];

export function SourceFilter({ value, onChange }: SourceFilterProps) {
    return (
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter activity by source">
            {SOURCES.map((source) => (
                <button
                    key={source.value}
                    onClick={() => onChange(source.value)}
                    aria-pressed={value === source.value}
                    className={`rounded-full px-4 py-1.5 text-sm font-medium transition-all ${value === source.value
                            ? "bg-primary text-primary-foreground shadow-sm"
                            : "bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground"
                        }`}
                >
                    {source.label}
                </button>
            ))}
        </div>
    );
}
