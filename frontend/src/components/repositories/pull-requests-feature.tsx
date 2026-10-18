import { RepositoryWorkItems } from "@/components/repositories/repository-work-items";
import { SectionHeading } from "@/components/rm/section-heading";
import type { Repository } from "@/lib/types/github";

/**
 * Pull Requests experience shared by the standalone route and repository-scoped embeds.
 * Omit selectedRepository only for the legacy standalone repository selector.
 */
export function PullRequestsFeature({ selectedRepository }: { selectedRepository?: Repository | null }) {
    return (
        <div className="space-y-6">
            <SectionHeading
                eyebrow="Review"
                title="Pull requests"
                description="Track review status and repository health signals across pull requests."
            />
            <RepositoryWorkItems kind="pull-requests" selectedRepository={selectedRepository} />
        </div>
    );
}
