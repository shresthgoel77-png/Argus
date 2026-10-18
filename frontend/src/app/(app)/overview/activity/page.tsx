"use client";

import { Suspense } from "react";
import { ActivityWorkspace } from "@/components/activity/activity-workspace";

export default function ActivityPage() {
    return (
        <Suspense fallback={<p role="status">Loading Activity workspace…</p>}>
            <ActivityWorkspace />
        </Suspense>
    );
}
