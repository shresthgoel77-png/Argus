import * as React from "react";
import { Inbox } from "lucide-react";
import { cn } from "@/lib/utils";

export interface EmptyStateProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "title"> {
  icon?: React.ReactNode;
  title?: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
}

/** Neutral empty state for dashboard surfaces that do not have content yet. */
const EmptyState = ({ icon, title = "Nothing here yet", description, action, className, ...props }: EmptyStateProps) => (
  <div className={cn("flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed bg-card px-6 py-12 text-center", className)} {...props}>
    <div className="flex size-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
      {icon ?? <Inbox className="size-6" aria-hidden="true" />}
    </div>
    <div className="space-y-1">
      <h3 className="font-semibold text-foreground">{title}</h3>
      {description ? <p className="max-w-sm text-sm text-muted-foreground">{description}</p> : null}
    </div>
    {action ? <div className="pt-1">{action}</div> : null}
  </div>
);

export { EmptyState };
