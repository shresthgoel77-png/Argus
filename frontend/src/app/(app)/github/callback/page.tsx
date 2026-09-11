"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { completeInstall } from "@/lib/api/github";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, AlertCircle, CheckCircle2 } from "lucide-react";

export default function GitHubCallbackPage() {
    const searchParams = useSearchParams();
    const router = useRouter();
    const [status, setStatus] = useState<"loading" | "success" | "error">("loading");

    useEffect(() => {
        const handleCallback = async () => {
            const installation_id = searchParams.get("installation_id");
            const setup_action = searchParams.get("setup_action");
            const state = searchParams.get("state");

            if (!installation_id || !setup_action || !state) {
                console.error("Missing required URL parameters", { installation_id, setup_action, state });
                setStatus("error");
                return;
            }

            const result = await completeInstall({ installation_id, setup_action, state });

            if (result) {
                setStatus("success");
                // Short delay to show success state before redirecting
                setTimeout(() => {
                    router.push("/overview/settings");
                }, 1500);
            } else {
                setStatus("error");
            }
        };

        handleCallback();
    }, [searchParams, router]);

    return (
        <div className="flex h-[calc(100vh-4rem)] items-center justify-center p-4">
            <Card className="w-full max-w-md">
                <CardHeader>
                    <CardTitle>Connecting GitHub</CardTitle>
                    <CardDescription>
                        {status === "loading" && "Please wait while we finalize your GitHub App installation."}
                        {status === "success" && "Successfully connected to GitHub."}
                        {status === "error" && "Failed to connect to GitHub."}
                    </CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col items-center justify-center py-6">
                    {status === "loading" && (
                        <Loader2 className="h-10 w-10 animate-spin text-muted-foreground" />
                    )}
                    {status === "success" && (
                        <CheckCircle2 className="h-10 w-10 text-green-500" />
                    )}
                    {status === "error" && (
                        <div className="flex flex-col items-center text-center">
                            <AlertCircle className="h-10 w-10 text-destructive mb-4" />
                            <p className="text-sm text-muted-foreground mb-4">
                                There was a problem finalizing your connection. Please ensure you authorized the app correctly.
                            </p>
                            <button
                                onClick={() => router.push("/overview/settings")}
                                className="inline-flex h-9 items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow transition-colors hover:bg-primary/90"
                            >
                                Return to Settings
                            </button>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
