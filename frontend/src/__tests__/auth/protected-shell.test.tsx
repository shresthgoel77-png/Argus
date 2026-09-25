import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ProtectedShell } from "../../components/auth/protected-shell";
import { useAuth } from "../../lib/auth/use-auth";
import { getAuthLoginPath } from "../../lib/auth/config";

// Mock dependencies
vi.mock("../../lib/auth/use-auth", () => ({
    useAuth: vi.fn(),
}));

vi.mock("../../lib/auth/config", () => ({
    getAuthLoginPath: vi.fn(),
}));

// Mock Next.js router
const mockReplace = vi.fn();
vi.mock("next/navigation", () => ({
    useRouter: () => ({
        replace: mockReplace,
    }),
}));

describe("ProtectedShell", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(getAuthLoginPath).mockReturnValue("/sign-in"); // mock clerk enabled path
    });

    it("renders loading skeleton when auth is loading", () => {
        vi.mocked(useAuth).mockReturnValue({
            isLoading: true,
            isAuthenticated: false,
            user: null,
            refresh: vi.fn(),
            login: vi.fn(),
            logout: vi.fn(),
        });

        render(
            <ProtectedShell>
                <div data-testid="protected-content">Secret Content</div>
            </ProtectedShell>
        );

        expect(screen.getByText("Checking authentication")).toBeInTheDocument();
        expect(screen.queryByTestId("protected-content")).not.toBeInTheDocument();
        expect(mockReplace).not.toHaveBeenCalled();
    });

    it("redirects to login path when unauthenticated and not loading", () => {
        vi.mocked(useAuth).mockReturnValue({
            isLoading: false,
            isAuthenticated: false,
            user: null,
            refresh: vi.fn(),
            login: vi.fn(),
            logout: vi.fn(),
        });

        render(
            <ProtectedShell>
                <div data-testid="protected-content">Secret Content</div>
            </ProtectedShell>
        );

        expect(screen.queryByTestId("protected-content")).not.toBeInTheDocument();
        expect(mockReplace).toHaveBeenCalledWith("/sign-in");
    });

    it("renders children when authenticated and not loading", () => {
        vi.mocked(useAuth).mockReturnValue({
            isLoading: false,
            isAuthenticated: true,
            user: { id: "123", email: "test@example.com", display_name: "Test", is_active: true, created_at: "2026-01-01" },
            refresh: vi.fn(),
            login: vi.fn(),
            logout: vi.fn(),
        });

        render(
            <ProtectedShell>
                <div data-testid="protected-content">Secret Content</div>
            </ProtectedShell>
        );

        expect(screen.getByTestId("protected-content")).toBeInTheDocument();
        expect(mockReplace).not.toHaveBeenCalled();
    });
});
