"use client";

import { useEffect, useRef, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { completeInstall } from "@/lib/api/github";

export function GitHubCallbackProcessor() {
    const searchParams = useSearchParams();
    const router = useRouter();
    const processed = useRef(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const installation_id = searchParams.get("installation_id");
        if (installation_id && !processed.current) {
            processed.current = true;

            async function processCallback() {
                try {
                    const state = searchParams.get("state");
                    const setup_action = searchParams.get("setup_action");
                    if (!state || !setup_action) {
                        setError("Start GitHub reconnection from Settings so the callback includes signed state.");
                        return;
                    }
                    const result = await completeInstall({ installation_id: installation_id!, state, setup_action });
                    if (result) {
                        router.replace("/overview/settings");
                        router.refresh();
                    }
                } catch (error) {
                    setError(error instanceof Error ? error.message : "GitHub connection could not be verified.");
                }
            }
            void processCallback();
        }
    }, [searchParams, router]);

    return error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null;
}
