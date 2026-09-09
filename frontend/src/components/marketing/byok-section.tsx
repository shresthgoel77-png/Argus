import { KeyRound, ShieldCheck, Layers } from "lucide-react";
import { SectionHeading } from "@/components/rm/section-heading";
import { Card, CardContent } from "@/components/ui/card";

const points = [
    {
        icon: KeyRound,
        title: "Your keys, your control",
        description:
            "Provide your own API key from OpenAI, Anthropic, Google, or any compatible provider. RepoMedic never stores or proxies your prompts through our infrastructure.",
    },
    {
        icon: ShieldCheck,
        title: "Encrypted at rest",
        description:
            "Keys are encrypted using AES-256 before being stored. They are only decrypted in-memory at the moment of use and never written to logs or telemetry.",
    },
    {
        icon: Layers,
        title: "Provider-agnostic design",
        description:
            "Switch providers at any time without reconfiguring your monitoring. RepoMedic abstracts the AI layer so your findings stay consistent regardless of the model behind them.",
    },
] as const;

export function ByokSection() {
    return (
        <section className="mx-auto w-full max-w-3xl px-6 py-20 lg:px-8">
            <SectionHeading
                eyebrow="Bring your own key"
                title="AI-powered analysis with full key ownership"
                description="RepoMedic uses large language models to analyze findings and generate remediation guidance. You control which provider and model to use."
            />

            <div className="mt-10 space-y-4">
                {points.map((point) => (
                    <Card key={point.title} className="shadow-soft">
                        <CardContent className="flex items-start gap-4 pt-6">
                            <div className="flex size-10 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
                                <point.icon className="size-5" aria-hidden="true" />
                            </div>
                            <div className="min-w-0 space-y-1">
                                <h3 className="text-sm font-semibold text-foreground">
                                    {point.title}
                                </h3>
                                <p className="text-sm leading-relaxed text-muted-foreground">
                                    {point.description}
                                </p>
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </section>
    );
}
