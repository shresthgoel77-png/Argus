import { GitFork } from "lucide-react";

import { EmptyState } from "@/components/rm/empty-state";
import { SectionHeading } from "@/components/rm/section-heading";
import { Button } from "@/components/ui/button";

export default function RepositoriesPage() {
    return (
        <div className="space-y-6">
            <SectionHeading
                eyebrow="Workspace"
                title="Repositories"
                description="Manage the repositories that RepoMedic will monitor."
            />
            <EmptyState
                icon={<GitFork className="size-6" aria-hidden="true" />}
                title="No repositories connected yet"
                description="Connect a GitHub repository to begin monitoring its health and findings."
                action={<Button disabled>Connect a repository</Button>}
            />
        </div>
    );
}
