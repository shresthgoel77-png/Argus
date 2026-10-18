import { auth } from "@clerk/nextjs/server";
import { PullRequestsFeature } from "@/components/repositories/pull-requests-feature";

export default async function PullRequestsPage() {
    await auth.protect();

    return <PullRequestsFeature />;
}
