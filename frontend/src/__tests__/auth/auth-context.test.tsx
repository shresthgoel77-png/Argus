import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider } from "../../lib/auth/auth-context";

// Mock next/dynamic since ClerkAuthProvider uses it for lazy loading
vi.mock("next/dynamic", () => ({
    default: () => {
        return function MockDynamic({ children }: { children: React.ReactNode }) {
            return <div data-testid="clerk-provider">{children}</div>;
        };
    }
}));

describe("AuthProvider selection", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("always renders the Clerk provider", () => {

        render(
            <AuthProvider>
                <div data-testid="dev-content">App Content</div>
            </AuthProvider>
        );

        expect(screen.getByTestId("clerk-provider")).toBeInTheDocument();
        expect(screen.getByTestId("dev-content")).toBeInTheDocument();
    });
});
