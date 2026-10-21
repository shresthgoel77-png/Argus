"use client";

/**
 * Clerk auth adapter — boundary module.
 *
 * This is the ONLY file in the frontend that imports Clerk hooks/components.
 * It maps Clerk's session state into the application's internal AuthContextType
 * so every downstream component uses the same `useAuth()` interface.
 */

import React, { useEffect, useMemo, type ReactNode } from "react";
import { ClerkProvider, useUser, useClerk, useAuth as useClerkAuth } from "@clerk/nextjs";
import { AuthContext, type AuthContextType } from "./auth-context";
import type { AuthUser } from "./types";
import { clearClerkTokenGetter, setClerkTokenGetter } from "./clerk-token";

// ---------------------------------------------------------------------------
// Bridge: subscribes to Clerk hooks and exposes AuthContextType
// ---------------------------------------------------------------------------

function ClerkAuthBridge({ children }: { children: ReactNode }) {
    const { user, isLoaded } = useUser();
    const clerk = useClerk();
    const { getToken } = useClerkAuth();

    useEffect(() => {
        setClerkTokenGetter(getToken);
        return () => clearClerkTokenGetter(getToken);
    }, [getToken]);

    const authUser: AuthUser | null = useMemo(() => {
        if (!user) return null;
        return {
            id: user.id,
            email: user.primaryEmailAddress?.emailAddress ?? "",
            display_name: user.fullName ?? user.firstName ?? null,
            is_active: true,
            created_at: user.createdAt?.toISOString() ?? new Date().toISOString(),
        };
    }, [user]);

    const value: AuthContextType = useMemo(
        () => ({
            user: authUser,
            isLoading: !isLoaded,
            isAuthenticated: !!authUser,
            refresh: async () => {
                // Clerk manages its own session refresh — no-op here.
            },
            login: async () => {
                clerk.redirectToSignIn();
            },
            logout: async () => {
                await clerk.signOut();
            },
        }),
        [authUser, isLoaded, clerk],
    );

    if (!isLoaded) return null;

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ---------------------------------------------------------------------------
// Provider wrapper: mounts ClerkProvider + bridge
// ---------------------------------------------------------------------------

export function ClerkAuthProvider({ children }: { children: ReactNode }) {
    const publishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
    if (!publishableKey) {
        throw new Error(
            "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY is required to use Argus.",
        );
    }

    return (
        <ClerkProvider publishableKey={publishableKey}>
            <ClerkAuthBridge>{children}</ClerkAuthBridge>
        </ClerkProvider>
    );
}
