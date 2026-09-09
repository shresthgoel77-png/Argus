import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { SectionHeading } from "@/components/rm/section-heading";

const settingsSections = [
    {
        title: "GitHub configuration",
        description: "GitHub App connection",
        message: "Available in a future update.",
    },
    {
        title: "AI provider and BYOK",
        description: "AI provider configuration",
        message: "Available in a future update.",
    },
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
