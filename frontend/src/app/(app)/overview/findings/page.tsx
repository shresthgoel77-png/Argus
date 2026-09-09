import { Search, SlidersHorizontal } from "lucide-react";

import { EmptyState } from "@/components/rm/empty-state";
import { SectionHeading } from "@/components/rm/section-heading";
import { Button } from "@/components/ui/button";

export default function FindingsPage() {
    return (
        <div className="space-y-6">
            <SectionHeading
                eyebrow="Review"
                title="Findings"
                description="Review code health findings across your connected repositories."
            />
            <div className="flex flex-wrap items-center gap-2" aria-label="Finding filters">
                <Button variant="outline" size="sm" disabled>
                    <SlidersHorizontal className="size-4" aria-hidden="true" />
                    Filter by status
                </Button>
                <Button variant="outline" size="sm" disabled>All severities</Button>
                <Button variant="outline" size="sm" disabled>All categories</Button>
            </div>
            <EmptyState
                icon={<Search className="size-6" aria-hidden="true" />}
                title="No findings available"
                description="Findings will appear here after connected repositories have been analyzed."
            />
        </div>
    );
}
