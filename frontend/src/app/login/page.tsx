"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/lib/auth/use-auth";

export default function LoginPage() {
    const router = useRouter();
    const { isAuthenticated, isLoading, login } = useAuth();
    const [isLoggingIn, setIsLoggingIn] = useState(false);

    useEffect(() => {
        if (!isLoading && isAuthenticated) {
            router.replace("/app");
        }
    }, [isAuthenticated, isLoading, router]);

    async function handleLogin() {
        setIsLoggingIn(true);
        await login();
        router.replace("/app");
    }

    if (isLoading || isAuthenticated) {
        return (
            <main className="flex min-h-screen items-center justify-center p-6">
                <span className="text-sm text-muted-foreground">Loading...</span>
            </main>
        );
    }

    return (
        <main className="flex min-h-screen items-center justify-center bg-muted/30 p-6">
            <Card className="w-full max-w-sm">
                <CardHeader>
                    <CardTitle>Sign in to RepoMedic</CardTitle>
                    <CardDescription>Use the development identity to enter the app.</CardDescription>
                </CardHeader>
                <CardContent>
                    <Button className="w-full" onClick={handleLogin} loading={isLoggingIn}>
                        Continue as dev user
                    </Button>
                </CardContent>
            </Card>
        </main>
    );
}
