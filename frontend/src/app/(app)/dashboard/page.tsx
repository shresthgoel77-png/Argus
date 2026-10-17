import AppOverviewPage from "../overview/page";
import { auth } from "@clerk/nextjs/server";

/**
 * Keep the established overview screen as the dashboard entry point.
 * The route alias preserves the existing app layout and protected behavior.
 */
export default async function DashboardPage() {
    await auth.protect();

    return <AppOverviewPage />;
}
