import { RepositoryWorkItems } from "@/components/repositories/repository-work-items";
import { SectionHeading } from "@/components/rm/section-heading";
import type { Repository } from "@/lib/types/github";

/**
 * Issues experience shared by the standalone route and repository-scoped embeds.
 * Omit selectedRepository only for the legacy standalone repository selector.
 */
export function IssuesFeature({ selectedRepository }: { selectedRepository?: Repository | null }) {
    return (
        <div className="space-y-6">
            <SectionHeading
                eyebrow="Review"
                title="Issues"
                description="Keep track of repository issues that may affect engineering health."
            />
            <RepositoryWorkItems kind="issues" selectedRepository={selectedRepository} />
        </div>
    );
}
