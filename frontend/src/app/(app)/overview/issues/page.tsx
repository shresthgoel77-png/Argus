import { auth } from "@clerk/nextjs/server";
import { LegacyWorkItemsEntry } from "@/components/activity/legacy-work-items-entry";

export default async function IssuesPage() {
    await auth.protect();
    return <LegacyWorkItemsEntry view="issues" />;
}
