import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { SectionHeading } from "@/components/rm/section-heading";
import { GitHubSettingsCard } from "./github-settings-card";
import { AIConnectionSettings } from "./ai-connection-settings";
import { NotificationPreferencesSettings } from "./notification-preferences-settings";

const settingsSections = [
    {
        title: "Account settings",
        description: "Workspace and account preferences",
        message: "Available in a future update.",
    },
];

export default function SettingsPage() {
    return (
        <div className="space-y-6">
            <SectionHeading
                eyebrow="Workspace"
                title="Settings"
                description="Configure integrations and preferences for your RepoMedic workspace."
            />
            <div className="grid gap-4 lg:grid-cols-3">
                <GitHubSettingsCard />
                <AIConnectionSettings />
                <NotificationPreferencesSettings />
                {settingsSections.map((section) => (
                    <Card key={section.title}>
                        <CardHeader>
                            <CardTitle>{section.title}</CardTitle>
                            <CardDescription>{section.description}</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <p className="text-sm text-muted-foreground">{section.message}</p>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    );
}
