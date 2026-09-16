import * as React from "react";
import { FindingResponse, FindingStatusUpdateRequest } from "@/lib/types/findings";
import { updateFindingStatus } from "@/lib/api/findings";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AlertCircle, CheckCircle2, RotateCcw, XCircle, Loader2 } from "lucide-react";
import { AIAnalysisPanel } from "./ai-analysis-panel";

const StatusButton = ({
    status,
    label,
    icon: Icon,
    variant = "default",
    onClick,
    disabled
}: {
    status: FindingStatusUpdateRequest["status"];
    label: string;
    icon: React.ElementType;
    variant?: "default" | "destructive" | "outline" | "secondary" | "ghost" | "link";
    onClick: (status: FindingStatusUpdateRequest["status"]) => void;
    disabled: boolean;
}) => (
    <Button
        variant={variant}
        onClick={() => onClick(status)}
        disabled={disabled}
        className="gap-2"
    >
        {disabled ? <Loader2 className="size-4 animate-spin" /> : <Icon className="size-4" />}
        {label}
    </Button>
);

interface FindingDetailDialogProps {
    finding: FindingResponse | null;
    isOpen: boolean;
    onOpenChange: (open: boolean) => void;
    onUpdate: (updated: FindingResponse) => void;
}

export function FindingDetailDialog({ finding, isOpen, onOpenChange, onUpdate }: FindingDetailDialogProps) {
    const [isPending, setIsPending] = React.useState(false);
    const [error, setError] = React.useState<string | null>(null);

    React.useEffect(() => {
        if (!isOpen) {
            const timer = setTimeout(() => {
                setError(null);
                setIsPending(false);
            }, 300);
            return () => clearTimeout(timer);
        }
    }, [isOpen]);

    if (!finding) return null;

    const handleAction = async (status: FindingStatusUpdateRequest["status"]) => {
        setIsPending(true);
        setError(null);

        try {
            const updated = await updateFindingStatus(finding.id, status);
            if (!updated) {
                // An unsuccessful response will return null from the fetch wrapper
                setError("The finding's status could not be updated. It may have been modified by another process. Please try again.");
            } else {
                onUpdate(updated);
            }
        } catch {
            setError("An unexpected error occurred. Please try again.");
        } finally {
            setIsPending(false);
        }
    };

    function displayValue(value: string) {
        if (!value) return "";
        return value.replace(/[_-]/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
    }

    function formatDate(value: string | null) {
        if (!value) return "N/A";
        const date = new Date(value);
        return Number.isNaN(date.getTime()) ? "Date unavailable" : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
    }

    return (
        <Dialog open={isOpen} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
                <DialogHeader>
                    <div className="flex items-center justify-between gap-4">
                        <DialogTitle className="text-xl leading-tight">{finding.title}</DialogTitle>
                    </div>
                </DialogHeader>

                <div className="space-y-6 py-4">
                    {error && (
                        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive border border-destructive/20 flex gap-2 items-start" aria-live="assertive">
                            <AlertCircle className="size-5 shrink-0" />
                            <p>{error}</p>
                        </div>
                    )}

                    <div>
                        <h4 className="text-sm font-semibold mb-1 text-foreground">Description</h4>
                        <p className="text-sm text-muted-foreground whitespace-pre-wrap">{finding.description}</p>
                    </div>

                    <div>
                        <h4 className="text-sm font-semibold mb-2 text-foreground">Details</h4>
                        <div className="grid grid-cols-2 gap-y-3 gap-x-4 text-sm">
                            <div>
                                <span className="text-muted-foreground block mb-1">Category</span>
                                <Badge variant="secondary" className="capitalize">{finding.category.replace(/[_-]/g, " ")}</Badge>
                            </div>
                            <div>
                                <span className="text-muted-foreground block mb-1">Severity</span>
                                <span className="font-medium">{displayValue(finding.severity)}</span>
                            </div>
                            <div>
                                <span className="text-muted-foreground block mb-1">Priority</span>
                                <span className="font-medium">{finding.priority ? displayValue(finding.priority) : "Unassigned"}</span>
                            </div>
                            <div>
                                <span className="text-muted-foreground block mb-1">Status</span>
                                <span className="font-medium">{displayValue(finding.status)}</span>
                            </div>
                        </div>
                    </div>

                    <div>
                        <h4 className="text-sm font-semibold mb-2 text-foreground">Evidence</h4>
                        <div className="rounded-md border bg-muted/50 p-3 space-y-2 text-sm overflow-x-auto">
                            {finding.evidence && Object.keys(finding.evidence).length > 0 ? (
                                Object.entries(finding.evidence).map(([key, value]) => (
                                    <div key={key} className="flex flex-col gap-1 sm:flex-row sm:gap-4 border-b last:border-0 pb-2 mb-2 last:pb-0 last:mb-0 border-border/50">
                                        <span className="font-medium text-foreground min-w-32 break-all">{key}</span>
                                        <span className="text-muted-foreground break-all">{typeof value === 'object' ? JSON.stringify(value) : String(value)}</span>
                                    </div>
                                ))
                            ) : (
                                <span className="text-muted-foreground">No evidence provided.</span>
                            )}
                        </div>
                    </div>

                    <div>
                        <h4 className="text-sm font-semibold mb-2 text-foreground">Timeline</h4>
                        <ul className="space-y-1.5 text-sm text-muted-foreground">
                            <li><span className="font-medium text-foreground w-36 inline-block">Detected At:</span> {formatDate(finding.detected_at)}</li>
                            {finding.updated_at && finding.updated_at !== finding.detected_at && <li><span className="font-medium text-foreground w-36 inline-block">Updated At:</span> {formatDate(finding.updated_at)}</li>}
                            {finding.acknowledged_at && <li><span className="font-medium text-foreground w-36 inline-block">Acknowledged At:</span> {formatDate(finding.acknowledged_at)}</li>}
                            {finding.resolved_at && <li><span className="font-medium text-foreground w-36 inline-block">Resolved At:</span> {formatDate(finding.resolved_at)}</li>}
                            {finding.resolution_source && <li><span className="font-medium text-foreground w-36 inline-block">Resolution Source:</span> {finding.resolution_source}</li>}
                        </ul>
                    </div>

                    <AIAnalysisPanel findingId={finding.id} />
                </div>

                <DialogFooter className="gap-2 sm:gap-2">
                    {finding.status === "open" && (
                        <>
                            <StatusButton status="acknowledged" label="Acknowledge" icon={CheckCircle2} onClick={handleAction} disabled={isPending} />
                            <StatusButton status="resolved" label="Resolve" icon={CheckCircle2} onClick={handleAction} disabled={isPending} />
                            <StatusButton status="ignored" label="Ignore" icon={XCircle} variant="outline" onClick={handleAction} disabled={isPending} />
                        </>
                    )}
                    {finding.status === "acknowledged" && (
                        <>
                            <StatusButton status="resolved" label="Resolve" icon={CheckCircle2} onClick={handleAction} disabled={isPending} />
                            <StatusButton status="ignored" label="Ignore" icon={XCircle} variant="outline" onClick={handleAction} disabled={isPending} />
                            <StatusButton status="open" label="Reopen" icon={RotateCcw} variant="secondary" onClick={handleAction} disabled={isPending} />
                        </>
                    )}
                    {(finding.status === "resolved" || finding.status === "ignored") && (
                        <StatusButton status="open" label="Reopen" icon={RotateCcw} variant="secondary" onClick={handleAction} disabled={isPending} />
                    )}
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
