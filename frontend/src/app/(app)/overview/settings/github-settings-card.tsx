"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getConnections, startInstall } from "@/lib/api/github";
import { GitHubConnection } from "@/lib/types/github";
import { Loader2, Plus } from "lucide-react";
import { EmptyState } from "@/components/rm/empty-state";

export function GitHubSettingsCard() {
    const [connections, setConnections] = useState<GitHubConnection[] | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isInstalling, setIsInstalling] = useState(false);

    useEffect(() => {
        async function fetchConnections() {
            const data = await getConnections();
            setConnections(data || []);
            setIsLoading(false);
        }
        fetchConnections();
    }, []);

    const handleConnectClick = async () => {
        setIsInstalling(true);
        const result = await startInstall();
        if (result && result.install_url) {
            window.location.href = result.install_url;
        } else {
            setIsInstalling(false);
        }
    };

    return (
        <Card>
            <CardHeader>
                <CardTitle>GitHub configuration</CardTitle>
                <CardDescription>GitHub App connection</CardDescription>
            </CardHeader>
            <CardContent>
                {isLoading ? (
                    <div className="flex justify-center p-4">
                        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                    </div>
                ) : connections && connections.length > 0 ? (
                    <div className="space-y-4">
                        <div className="rounded-md border">
                            {connections.map((conn) => (
                                <div key={conn.id} className="flex items-center justify-between border-b p-4 last:border-0">
                                    <div>
                                        <p className="font-medium">{conn.account_login}</p>
                                        <p className="text-sm text-muted-foreground capitalize">Status: {conn.status}</p>
                                    </div>
                                    <div className="flex h-2 w-2 rounded-full bg-green-500" title="Connected"></div>
                                </div>
                            ))}
                        </div>
                        <button
                            onClick={handleConnectClick}
                            disabled={isInstalling}
                            className="inline-flex h-9 items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground disabled:opacity-50"
                        >
                            {isInstalling ? (
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : (
                                <Plus className="mr-2 h-4 w-4" />
                            )}
                            Add another installation
                        </button>
                    </div>
                ) : (
                    <EmptyState
                        title="No GitHub Connection"
                        description="Connect your GitHub account to access your repositories."
                        action={
                            <button
                                onClick={handleConnectClick}
                                disabled={isInstalling}
                                className="inline-flex h-9 items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow transition-colors hover:bg-primary/90 disabled:opacity-50"
                            >
                                {isInstalling ? (
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                ) : (
                                    "Connect GitHub"
                                )}
                            </button>
                        }
                    />
                )}
            </CardContent>
        </Card>
    );
}
