import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider } from "../../lib/auth/auth-context";
import { isClerkEnabled } from "../../lib/auth/config";

// Mock config
vi.mock("../../lib/auth/config", () => ({
    isClerkEnabled: vi.fn(),
}));

// Mock next/dynamic since ClerkAuthProvider uses it for lazy loading
vi.mock("next/dynamic", () => ({
    default: () => {
        return function MockDynamic({ children }: { children: React.ReactNode }) {
            return <div data-testid="clerk-provider">{children}</div>;
        };
    }
}));

// We only need to mock the DevAuthProvider inner logic slightly if it tries to do things on mount,
// but since the component is in the same file as AuthProvider, we'll just let it render.
// To avoid API calls, we could let it render but mock the API, or just check the text content.
vi.mock("../../lib/api/auth", () => ({
    getCurrentUser: vi.fn().mockResolvedValue(null),
    devLogin: vi.fn(),
    logout: vi.fn(),
}));

describe("AuthProvider selection", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("renders ClerkAuthProvider when isClerkEnabled is true", () => {
        vi.mocked(isClerkEnabled).mockReturnValue(true);

        render(
            <AuthProvider>
                <div>App Content</div>
            </AuthProvider>
        );

        expect(screen.getByTestId("clerk-provider")).toBeInTheDocument();
    });

    it("renders DevAuthProvider when isClerkEnabled is false", () => {
        vi.mocked(isClerkEnabled).mockReturnValue(false);

        render(
            <AuthProvider>
                <div data-testid="dev-content">App Content</div>
            </AuthProvider>
        );

        // Since we didn't mock DevAuthProvider (it's internal), the clerk-provider should NOT be in the document
        expect(screen.queryByTestId("clerk-provider")).not.toBeInTheDocument();
        expect(screen.getByTestId("dev-content")).toBeInTheDocument();
    });
});
