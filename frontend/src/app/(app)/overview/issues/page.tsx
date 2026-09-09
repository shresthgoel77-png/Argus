import { CircleDot } from "lucide-react";

import { EmptyState } from "@/components/rm/empty-state";
import { SectionHeading } from "@/components/rm/section-heading";

export default function IssuesPage() {
    return (
        <div className="space-y-6">
            <SectionHeading
                eyebrow="Review"
                title="Issues"
                description="Keep track of repository issues that may affect engineering health."
            />
            <EmptyState
                icon={<CircleDot className="size-6" aria-hidden="true" />}
                title="No issues to show"
                description="Issue activity will appear here after a repository is connected."
            />
        </div>
    );
}
