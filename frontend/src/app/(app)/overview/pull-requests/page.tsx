import { auth } from "@clerk/nextjs/server";
import { LegacyWorkItemsEntry } from "@/components/activity/legacy-work-items-entry";

export default async function PullRequestsPage() {
    await auth.protect();
    return <LegacyWorkItemsEntry view="pull-requests" />;
}
