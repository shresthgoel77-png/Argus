"use client";

import { FormEvent, useEffect, useState } from "react";
import { CheckCircle2, Loader2, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
    AIConnectionApiError,
    AI_PROVIDER_OPTIONS,
    createOrReplaceAIConnection,
    deleteAIConnection,
    getAIConnectionStatus,
} from "@/lib/api/ai-connection";
import { AIConnectionStatus, AIProviderKey } from "@/lib/types/ai-connection";

function formatValidatedAt(value?: string) {
    if (!value) return "Unknown";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function getErrorMessage(error: unknown, fallback: string) {
    return error instanceof AIConnectionApiError ? error.message : fallback;
}

export function AIConnectionSettings() {
    const [status, setStatus] = useState<AIConnectionStatus | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [isRemoving, setIsRemoving] = useState(false);
    const [provider, setProvider] = useState<AIProviderKey>(AI_PROVIDER_OPTIONS[0].key);
    const [model, setModel] = useState(AI_PROVIDER_OPTIONS[0].models[0]);
    const [apiKey, setApiKey] = useState("");
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    const selectedProvider = AI_PROVIDER_OPTIONS.find((option) => option.key === provider) ?? AI_PROVIDER_OPTIONS[0];

    const refreshStatus = async () => {
        setIsLoading(true);
        setErrorMessage(null);
        try {
            setStatus(await getAIConnectionStatus());
        } catch (error) {
            setStatus(null);
            setErrorMessage(getErrorMessage(error, "The AI connection status could not be loaded."));
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        let isActive = true;
        getAIConnectionStatus()
            .then((nextStatus) => {
                if (isActive) setStatus(nextStatus);
            })
            .catch((error: unknown) => {
                if (isActive) {
                    setStatus(null);
                    setErrorMessage(getErrorMessage(error, "The AI connection status could not be loaded."));
                }
            })
            .finally(() => {
                if (isActive) setIsLoading(false);
            });

        return () => {
            isActive = false;
        };
    }, []);

    const handleProviderChange = (nextProvider: AIProviderKey) => {
        const nextOption = AI_PROVIDER_OPTIONS.find((option) => option.key === nextProvider) ?? AI_PROVIDER_OPTIONS[0];
        setProvider(nextProvider);
        setModel(nextOption.models[0]);
    };

    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        const submittedApiKey = apiKey;
        setApiKey("");
        setErrorMessage(null);
        setIsSaving(true);
        try {
            setStatus(await createOrReplaceAIConnection({ provider, model, apiKey: submittedApiKey }));
        } catch (error) {
            setErrorMessage(getErrorMessage(error, "The AI connection could not be saved."));
        } finally {
            setIsSaving(false);
        }
    };

    const handleRemove = async () => {
        if (!window.confirm("Remove this AI connection? You will need to validate the API key again to reconnect.")) return;

        setIsRemoving(true);
        setErrorMessage(null);
        try {
            await deleteAIConnection();
            await refreshStatus();
        } catch (error) {
            setErrorMessage(getErrorMessage(error, "The AI connection could not be removed."));
        } finally {
            setIsRemoving(false);
        }
    };

    return (
            <Card id="ai-connection">
            <CardHeader>
                <CardTitle>AI provider and BYOK</CardTitle>
                <CardDescription>Validate a provider key for AI-powered workspace features.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
                {errorMessage ? <p className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive" role="alert">{errorMessage}</p> : null}

                <div aria-live="polite" className="rounded-md border p-4">
                    {isLoading ? (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" />Loading AI connection status...</div>
                    ) : status?.configured ? (
                        <div className="space-y-3">
                            <div className="flex items-center gap-2 font-medium"><CheckCircle2 className="size-4 text-emerald-600" />AI connection configured</div>
                            <dl className="grid gap-2 text-sm sm:grid-cols-3">
                                <div><dt className="text-muted-foreground">Provider</dt><dd>{status.provider}</dd></div>
                                <div><dt className="text-muted-foreground">Model</dt><dd>{status.model}</dd></div>
                                <div><dt className="text-muted-foreground">Last validated</dt><dd>{formatValidatedAt(status.lastValidatedAt)}</dd></div>
                            </dl>
                            <Button type="button" variant="destructive" size="sm" loading={isRemoving} onClick={() => void handleRemove()}>
                                <Trash2 className="size-4" />Remove connection
                            </Button>
                        </div>
                    ) : errorMessage ? (
                        <p className="text-sm text-muted-foreground">Status unavailable</p>
                    ) : (
                        <p className="text-sm text-muted-foreground">Not configured</p>
                    )}
                </div>

                <form className="space-y-4" onSubmit={(event) => void handleSubmit(event)}>
                    <div className="grid gap-4 sm:grid-cols-2">
                        <label className="space-y-2 text-sm font-medium">
                            Provider
                            <select className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm" value={provider} onChange={(event) => handleProviderChange(event.target.value)} disabled={isSaving}>
                                {AI_PROVIDER_OPTIONS.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}
                            </select>
                        </label>
                        <label className="space-y-2 text-sm font-medium">
                            Model
                            <select className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm" value={model} onChange={(event) => setModel(event.target.value)} disabled={isSaving}>
                                {selectedProvider.models.map((option) => <option key={option} value={option}>{option}</option>)}
                            </select>
                        </label>
                    </div>
                    <label className="block space-y-2 text-sm font-medium">
                        API key
                        <Input type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} autoComplete="off" spellCheck={false} required disabled={isSaving} aria-describedby="ai-key-help" />
                        <span id="ai-key-help" className="block text-xs font-normal text-muted-foreground">The key is validated and then cleared. It is never shown again.</span>
                    </label>
                    <Button type="submit" loading={isSaving} disabled={!apiKey}>Save and validate</Button>
                </form>
            </CardContent>
        </Card>
    );
}