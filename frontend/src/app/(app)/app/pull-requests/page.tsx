import { GitPullRequest } from "lucide-react";

import { EmptyState } from "@/components/rm/empty-state";
import { SectionHeading } from "@/components/rm/section-heading";

export default function PullRequestsPage() {
    return (
        <div className="space-y-6">
            <SectionHeading
                eyebrow="Review"
                title="Pull requests"
                description="Track review status and repository health signals across pull requests."
            />
            <EmptyState
                icon={<GitPullRequest className="size-6" aria-hidden="true" />}
                title="No pull requests to show"
                description="Pull request activity will appear here once a repository is connected."
            />
        </div>
    );
}
