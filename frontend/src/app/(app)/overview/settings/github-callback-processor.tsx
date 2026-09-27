"use client";

import { useEffect, useRef } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { syncInstallation } from "@/lib/api/github";

export function GitHubCallbackProcessor() {
    const searchParams = useSearchParams();
    const router = useRouter();
    const processed = useRef(false);

    useEffect(() => {
        const installation_id = searchParams.get("installation_id");
        if (installation_id && !processed.current) {
            processed.current = true;

            async function processCallback() {
                try {
                    const result = await syncInstallation(installation_id!);
                    if (result) {
                        router.replace("/overview/settings");
                        router.refresh();
                    }
                } catch (error) {
                    console.error("Failed to sync GitHub installation", error);
                }
            }
            void processCallback();
        }
    }, [searchParams, router]);

    return null;
}
