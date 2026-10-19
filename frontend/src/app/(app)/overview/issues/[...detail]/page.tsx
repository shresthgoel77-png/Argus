import { auth } from "@clerk/nextjs/server";
import { LegacyWorkItemsEntry } from "@/components/activity/legacy-work-items-entry";

export default async function IssuesDetailPage({ params }: { params: Promise<{ detail: string[] }> }) {
    await auth.protect();
    const { detail } = await params;
    return <LegacyWorkItemsEntry view="issues" detail={detail} />;
}
