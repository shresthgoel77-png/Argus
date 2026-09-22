"use client";

import { FormEvent, useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import {
    NotificationPreferencesApiError,
    getNotificationPreferences,
    updateNotificationPreferences,
    NotificationPreferences
} from "@/lib/api/notification-preferences";

type Severity = "critical" | "high" | "medium" | "low" | "info";

const SEVERITY_OPTIONS: { value: Severity; label: string }[] = [
    { value: "critical", label: "Critical" },
    { value: "high", label: "High" },
    { value: "medium", label: "Medium" },
    { value: "low", label: "Low" },
    { value: "info", label: "Info" },
];

function getErrorMessage(error: unknown, fallback: string) {
    return error instanceof NotificationPreferencesApiError ? error.message : fallback;
}

export function NotificationPreferencesSettings() {
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);

    // Preferences Form State
    const [emailEnabled, setEmailEnabled] = useState(false);
    const [minSeverityEmail, setMinSeverityEmail] = useState<Severity>("critical");
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    useEffect(() => {
        let isActive = true;
        getNotificationPreferences()
            .then((prefs) => {
                if (isActive) {
                    setEmailEnabled(prefs.email_enabled);
                    setMinSeverityEmail(prefs.min_severity_email);
                }
            })
            .catch((error: unknown) => {
                if (isActive) {
                    setErrorMessage(getErrorMessage(error, "Failed to load notification preferences."));
                }
            })
            .finally(() => {
                if (isActive) setIsLoading(false);
            });

        return () => {
            isActive = false;
        };
    }, []);

    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        setErrorMessage(null);
        setIsSaving(true);
        try {
            const updated = await updateNotificationPreferences({
                email_enabled: emailEnabled,
                min_severity_email: minSeverityEmail,
            });
            setEmailEnabled(updated.email_enabled);
            setMinSeverityEmail(updated.min_severity_email);
        } catch (error) {
            setErrorMessage(getErrorMessage(error, "Failed to save notification preferences."));
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <Card id="notification-preferences">
            <CardHeader>
                <CardTitle>Notification Preferences</CardTitle>
                <CardDescription>Configure how and when you want to be notified.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
                {errorMessage ? (
                    <p className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive" role="alert">
                        {errorMessage}
                    </p>
                ) : null}

                {isLoading ? (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground p-4">
                        <Loader2 className="size-4 animate-spin" />
                        Loading preferences...
                    </div>
                ) : (
                    <form className="space-y-6" onSubmit={(event) => void handleSubmit(event)}>
                        <div className="flex flex-row items-center justify-between rounded-lg border p-4">
                            <div className="space-y-0.5">
                                <label className="text-sm font-medium">Email Notifications</label>
                                <p className="text-sm text-muted-foreground">Receive workspace alerts via email.</p>
                            </div>
                            <Switch
                                checked={emailEnabled}
                                onCheckedChange={setEmailEnabled}
                                disabled={isSaving}
                            />
                        </div>

                        <div className="space-y-2">
                            <label className="text-sm font-medium">
                                Minimum Severity for Email
                                <select
                                    className="mt-2 flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50"
                                    value={minSeverityEmail}
                                    onChange={(e) => setMinSeverityEmail(e.target.value as Severity)}
                                    disabled={isSaving || !emailEnabled}
                                >
                                    {SEVERITY_OPTIONS.map((option) => (
                                        <option key={option.value} value={option.value}>{option.label}</option>
                                    ))}
                                </select>
                            </label>
                            <p className="text-xs text-muted-foreground">Only alerts with this severity or higher will trigger an email.</p>
                        </div>

                        <Button type="submit" loading={isSaving} disabled={isLoading || isSaving}>
                            Save preferences
                        </Button>
                    </form>
                )}
            </CardContent>
        </Card>
    );
}
