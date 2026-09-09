import { Activity } from "lucide-react";

import { EmptyState } from "@/components/rm/empty-state";
import { SectionHeading } from "@/components/rm/section-heading";

export default function ActivityPage() {
    return (
        <div className="space-y-6">
            <SectionHeading
                eyebrow="Workspace"
                title="Activity"
                description="See the latest events across your RepoMedic workspace."
            />
            <EmptyState
                icon={<Activity className="size-6" aria-hidden="true" />}
                title="No activity yet"
                description="Workspace events will appear here when repositories and reviews are connected."
            />
        </div>
    );
}
