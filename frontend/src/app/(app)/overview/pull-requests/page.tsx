import { RepositoryWorkItems } from "@/components/repositories/repository-work-items";
import { SectionHeading } from "@/components/rm/section-heading";

export default function PullRequestsPage() {
    return (
        <div className="space-y-6">
            <SectionHeading
                eyebrow="Review"
                title="Pull requests"
                description="Track review status and repository health signals across pull requests."
            />
            <RepositoryWorkItems kind="pull-requests" />
        </div>
    );
}
