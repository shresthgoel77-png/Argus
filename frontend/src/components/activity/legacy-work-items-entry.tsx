"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { legacyActivityUrl, type WorkspaceView } from "./workspace-selection";

/** No data reads here: the canonical workspace validates repository ownership. */
export function LegacyWorkItemsEntry({ view, detail }: { view: Exclude<WorkspaceView, "contributions">; detail?: string[] }) {
    const router = useRouter();
    const destination = React.useRef<string | null>(null);
    React.useEffect(() => {
        const next = legacyActivityUrl(window.location.href, view, detail);
        if (destination.current === next) return;
        destination.current = next;
        router.replace(next);
    }, [router, view, detail]);
    return <p role="status">Opening Activity...</p>;
}
