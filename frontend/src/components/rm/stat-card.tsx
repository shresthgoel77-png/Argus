import * as React from "react";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";

export interface StatCardProps extends React.HTMLAttributes<HTMLDivElement> {
  label: React.ReactNode;
  value: React.ReactNode;
  description?: React.ReactNode;
  icon?: React.ElementType;
  trend?: React.ReactNode;
}

/** Compact metric card with an optional icon and contextual trend. */
const StatCard = ({ label, value, description, icon: Icon, trend, className, ...props }: StatCardProps) => (
  <Card className={cn("shadow-soft", className)} {...props}>
    <CardContent className="flex items-start justify-between gap-4 pt-6">
      <div className="min-w-0 space-y-1">
        <p className="text-sm font-medium text-muted-foreground">{label}</p>
        <p className="text-2xl font-semibold tracking-tight text-foreground">{value}</p>
        {description ? <p className="text-xs text-muted-foreground">{description}</p> : null}
      </div>
      {Icon ? <div className="flex size-10 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground"><Icon className="size-5" aria-hidden="true" /></div> : null}
      {trend ? <div className="text-xs font-medium text-success">{trend}</div> : null}
    </CardContent>
  </Card>
);

export { StatCard };
