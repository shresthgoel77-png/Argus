import { auth } from "@clerk/nextjs/server";
import { IssuesFeature } from "@/components/repositories/issues-feature";

export default async function IssuesPage() {
    await auth.protect();

    return <IssuesFeature />;
}
