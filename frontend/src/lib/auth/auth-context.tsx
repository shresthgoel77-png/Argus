
"use client";

import React, { createContext, type ReactNode } from "react";
import { AuthUser } from "./types";

export interface AuthContextType {
    user: AuthUser | null;
    isLoading: boolean;
    isAuthenticated: boolean;
    refresh: () => Promise<void>;
    login: () => Promise<void>;
    logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

import dynamic from "next/dynamic";

const ClerkAuthProvider = dynamic(
    () => import("./clerk-adapter").then((mod) => mod.ClerkAuthProvider),
    { ssr: false }
);

export function AuthProvider({ children }: { children: ReactNode }) {
    return <ClerkAuthProvider>{children}</ClerkAuthProvider>;
}
