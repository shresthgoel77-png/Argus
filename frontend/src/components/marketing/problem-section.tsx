import { SectionHeading } from "@/components/rm/section-heading";

export function ProblemSection() {
    return (
        <section className="mx-auto w-full max-w-3xl px-6 py-20 lg:px-8">
            <SectionHeading
                eyebrow="The problem"
                title="Repository health is invisible until something breaks"
            />

            <div className="mt-8 space-y-6 text-base leading-relaxed text-muted-foreground">
                <p>
                    Engineering teams generate thousands of signals every week — CI
                    pipelines pass or fail, dependencies age, security advisories land,
                    pull requests stall, and code-quality metrics shift. But these signals
                    live in separate tabs, separate tools, and separate mental models.
                </p>

                <p>
                    Without a unified view, problems compound silently. A pinned
                    dependency becomes a six-month-old vulnerability. A flaky workflow
                    burns hours before anyone notices the pattern. A stalled PR blocks a
                    release train that three other teams depend on.
                </p>

                <p>
                    The data already exists inside GitHub. What&apos;s missing is
                    something that watches continuously, connects the dots, and tells you
                    what actually needs attention — before it becomes an incident.
                </p>
            </div>
        </section>
    );
}
