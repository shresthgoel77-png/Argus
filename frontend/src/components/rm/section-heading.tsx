import * as React from "react";
import { cn } from "@/lib/utils";

export interface SectionHeadingProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "title"> {
  eyebrow?: React.ReactNode;
  title: React.ReactNode;
  description?: React.ReactNode;
}

/** Consistent eyebrow, title, and supporting description for page sections. */
const SectionHeading = ({ eyebrow, title, description, className, ...props }: SectionHeadingProps) => (
  <div className={cn("space-y-2", className)} {...props}>
    {eyebrow ? <p className="text-xs font-semibold uppercase tracking-wider text-accent">{eyebrow}</p> : null}
    <h2 className="text-2xl font-semibold tracking-tight text-foreground">{title}</h2>
    {description ? <p className="max-w-2xl text-sm text-muted-foreground">{description}</p> : null}
  </div>
);

export { SectionHeading };
