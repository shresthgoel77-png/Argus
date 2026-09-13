"use client";

import { useState } from "react";
import { Search, SlidersHorizontal } from "lucide-react";

import { EmptyState } from "@/components/rm/empty-state";
import { SectionHeading } from "@/components/rm/section-heading";
import { Button } from "@/components/ui/button";

const STATUSES = ["All statuses", "open", "acknowledged", "resolved", "ignored"];
const SEVERITIES = ["All severities", "critical", "high", "medium", "low", "info"];
const CATEGORIES = ["All categories", "Security", "Performance", "Code Quality", "Maintenance"];

export default function FindingsPage() {
    const [statusIndex, setStatusIndex] = useState(0);
    const [severityIndex, setSeverityIndex] = useState(0);
    const [categoryIndex, setCategoryIndex] = useState(0);

    return (
        <div className="space-y-6">
            <SectionHeading
                eyebrow="Review"
                title="Findings"
                description="Review code health findings across your connected repositories."
            />
            <div className="flex flex-wrap items-center gap-2" aria-label="Finding filters">
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setStatusIndex((prev) => (prev + 1) % STATUSES.length)}
                >
                    <SlidersHorizontal className="size-4" aria-hidden="true" />
                    {statusIndex === 0 ? "Filter by status" : `Status: ${STATUSES[statusIndex].charAt(0).toUpperCase() + STATUSES[statusIndex].slice(1)}`}
                </Button>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setSeverityIndex((prev) => (prev + 1) % SEVERITIES.length)}
                >
                    {severityIndex === 0 ? "All severities" : `Severity: ${SEVERITIES[severityIndex].charAt(0).toUpperCase() + SEVERITIES[severityIndex].slice(1)}`}
                </Button>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCategoryIndex((prev) => (prev + 1) % CATEGORIES.length)}
                >
                    {CATEGORIES[categoryIndex]}
                </Button>
            </div>
            <EmptyState
                icon={<Search className="size-6" aria-hidden="true" />}
                title="No findings available"
                description="Findings will appear here after connected repositories have been analyzed."
            />
        </div>
    );
}
