import { RepositoryWorkItems } from "@/components/repositories/repository-work-items";
import { SectionHeading } from "@/components/rm/section-heading";

export default function IssuesPage() {
    return (
        <div className="space-y-6">
            <SectionHeading
                eyebrow="Review"
                title="Issues"
                description="Keep track of repository issues that may affect engineering health."
            />
            <RepositoryWorkItems kind="issues" />
        </div>
    );
}
