"use client";

import * as React from "react";
import { useAuth } from "@/lib/auth/use-auth";
import { fetchUserContributions, type UserContributions } from "./user-contributions";

export function useUserContributions(year: number, revision: number) {
    const { user, isAuthenticated } = useAuth();
    const userId = isAuthenticated ? user?.id : undefined;
    const key = `${userId ?? "signed-out"}:${year}:${revision}`;
    const [pending] = React.useState(() => new Map<string, Promise<UserContributions>>());
    const [result, setResult] = React.useState<{ key: string; data: UserContributions }>();
    React.useEffect(() => {
        let active = true;
        async function read() {
            if (!userId) return;
            // Only deduplicate in-flight browser reads. Each settled reload revalidates
            // identity/access server-side before consulting its user/year/context cache.
            let request = pending.get(key);
            if (!request) { request = fetchUserContributions(year); pending.set(key, request); }
            const data = await request;
            if (pending.get(key) === request) pending.delete(key);
            if (active) setResult({ key, data });
        }
        void read();
        window.addEventListener("focus", read);
        return () => { active = false; window.removeEventListener("focus", read); };
    }, [key, pending, userId, year]);
    return result?.key === key ? result.data : undefined;
}
