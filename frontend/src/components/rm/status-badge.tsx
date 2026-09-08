import * as React from "react";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type Severity = "critical" | "high" | "medium" | "low" | "info";
export type FindingStatus = "open" | "acknowledged" | "resolved" | "ignored";

export interface StatusBadgeProps extends Omit<BadgeProps, "children"> {
  severity?: Severity;
  status?: FindingStatus;
  label?: React.ReactNode;
}

const severityStyles: Record<Severity, string> = {
  critical: "border-transparent bg-destructive text-destructive-foreground",
  high: "border-transparent bg-warning text-warning-foreground",
  medium: "border-accent bg-accent/10 text-accent",
  low: "border-transparent bg-success text-success-foreground",
  info: "border-input bg-muted text-muted-foreground",
};

const statusStyles: Record<FindingStatus, string> = {
  open: "border-accent bg-accent/10 text-accent",
  acknowledged: "border-warning bg-warning/10 text-warning",
  resolved: "border-success bg-success/10 text-success",
  ignored: "border-input bg-muted text-muted-foreground",
};

/** Token-mapped indicator for finding severity or lifecycle status. */
const StatusBadge = ({ severity, status, label, className, ...props }: StatusBadgeProps) => {
  const value = severity ?? status;
  return <Badge variant="outline" className={cn("capitalize", value ? (severity ? severityStyles[severity] : statusStyles[status!]) : undefined, className)} {...props}>{label ?? value ?? "Unknown"}</Badge>;
};

export { StatusBadge };
