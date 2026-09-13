
"use client";

import React, { createContext, useCallback, useEffect, useState, ReactNode } from "react";
import { AuthUser } from "./types";
import { getCurrentUser, devLogin, logout as apiLogout } from "../api/auth";

export interface AuthContextType {
    user: AuthUser | null;
    isLoading: boolean;
    isAuthenticated: boolean;
    refresh: () => Promise<void>;
    login: () => Promise<void>;
    logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<AuthUser | null>(null);
    const [isLoading, setIsLoading] = useState<boolean>(true);

    const refresh = useCallback(async () => {
        setIsLoading(true);

        // Avoid unnecessary API call if we know user is not authenticated
        if (typeof window !== "undefined" && window.localStorage.getItem("auth-status") !== "authenticated") {
            setUser(null);
            setIsLoading(false);
            return;
        }

        try {
            const currentUser = await getCurrentUser();
            if (!currentUser && typeof window !== "undefined") {
                window.localStorage.removeItem("auth-status");
            }
            setUser(currentUser);
        } catch (error) {
            console.error("Failed to refresh user auth state:", error);
            if (typeof window !== "undefined") {
                window.localStorage.removeItem("auth-status");
            }
            setUser(null);
        } finally {
            setIsLoading(false);
        }
    }, []);

    const login = useCallback(async () => {
        try {
            await devLogin();
            if (typeof window !== "undefined") {
                window.localStorage.setItem("auth-status", "authenticated");
            }
            await refresh();
        } catch (error) {
            console.error("Failed to login:", error);
        }
    }, [refresh]);

    const logout = useCallback(async () => {
        try {
            await apiLogout();
            if (typeof window !== "undefined") {
                window.localStorage.removeItem("auth-status");
            }
            await refresh();
        } catch (error) {
            console.error("Failed to logout:", error);
        }
    }, [refresh]);

    // Determine initial auth state on mount
    useEffect(() => {
        // The refresh function synchronizes the initial auth state with the API.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        refresh();
    }, [refresh]);

    const value: AuthContextType = {
        user,
        isLoading,
        isAuthenticated: !!user,
        refresh,
        login,
        logout,
    };

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
