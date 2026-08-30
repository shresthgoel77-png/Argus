import React, { useEffect, useState, useCallback } from "react";
import { Evidence, RemediationAction, proposeRemediation, approveRemediation, rejectRemediation, executeRemediation, getIncidentRemediation } from "@/lib/api";

type Props = {
    incidentId: number;
    incidentStatus: string;
    evidenceRows: Evidence[];
    onStatusChange: () => void;
};

export default function RemediationPanel({ incidentId, incidentStatus, evidenceRows, onStatusChange }: Props) {
    const [action, setAction] = useState<RemediationAction | null>(null);
    const [loading, setLoading] = useState(false);
    const [nameInput, setNameInput] = useState("");
    const [errorMsg, setErrorMsg] = useState<string | null>(null);

    const rcaEvidence = evidenceRows.find((e) => e.category === "ai_rca");
    const recommendation = rcaEvidence?.content?.recommended_remediation;

    const fetchAction = useCallback(async () => {
        try {
            const data = await getIncidentRemediation(incidentId);
            setAction(data);
        } catch (err: any) {
            // Could be 404 which is fine (no action proposed yet)
            console.error(err);
        }
    }, [incidentId]);

    useEffect(() => {
        void fetchAction();
    }, [fetchAction]);

    const handleAction = async (routine: () => Promise<any>) => {
        setLoading(true);
        setErrorMsg(null);
        try {
            await routine();
            await fetchAction();
            onStatusChange();
        } catch (err: any) {
            setErrorMsg(err.message || String(err));
        } finally {
            setLoading(false);
        }
    };

    const handlePropose = () => handleAction(() => proposeRemediation(incidentId));
    const handleApprove = () => handleAction(() => approveRemediation(action!.id, nameInput));
    const handleReject = () => handleAction(() => rejectRemediation(action!.id, nameInput));
    const handleExecute = () => handleAction(() => executeRemediation(action!.id));

    if (!recommendation && !action) {
        return (
            <div className="mt-4 p-4 border border-slate-700 bg-slate-900 rounded text-slate-400">
                Remediation pending RCA
            </div>
        );
    }

    // Always show the basic AI recommendation details top-level so users know what's up
    const displayActionType = action ? action.action_type : (recommendation?.action_type || "Unknown");
    const displayParams = action ? action.params : recommendation?.params;

    return (
        <div className="mt-4 p-5 border border-slate-700 bg-slate-800 rounded space-y-4">
            <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-slate-100">Remediation Action</h3>
                {action && (
                    <span className="text-xs px-2 py-1 rounded border font-medium border-slate-600 bg-slate-700 text-slate-300 uppercase tracking-widest">
                        Status: {action.status}
                    </span>
                )}
            </div>

            <p className="text-slate-300">
                Type: <span className="font-mono text-indigo-300">{displayActionType}</span>
                {action?.risk_level && (
                    <> • Risk: <span className="font-semibold text-rose-300 uppercase">{action.risk_level}</span></>
                )}
            </p>

            {(!action && recommendation?.rationale) && (
                <div>
                    <h4 className="text-sm font-semibold text-slate-400 uppercase tracking-wide mt-3">Rationale</h4>
                    <p className="mt-1 text-sm text-slate-300">{recommendation.rationale}</p>
                </div>
            )}

            {displayParams && Object.keys(displayParams).length > 0 && (
                <pre className="text-xs bg-slate-950 p-3 rounded text-slate-300 mt-2 whitespace-pre-wrap overflow-x-auto">
                    {JSON.stringify(displayParams, null, 2)}
                </pre>
            )}

            {errorMsg && (
                <div className="p-3 bg-rose-950/40 border border-rose-900 text-rose-300 rounded text-sm">
                    {errorMsg}
                </div>
            )}

            <div className="pt-4 mt-4 border-t border-slate-700">
                {!action && incidentStatus === "rca_complete" && (
                    <button
                        onClick={handlePropose}
                        disabled={loading}
                        className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 rounded font-medium disabled:opacity-50"
                    >
                        {loading ? "Proposing..." : "Propose Remediation"}
                    </button>
                )}

                {action?.status === "pending_approval" && (
                    <div className="space-y-3">
                        <input
                            type="text"
                            placeholder="Enter your name"
                            value={nameInput}
                            onChange={(e) => setNameInput(e.target.value)}
                            className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded text-sm min-w-[200px]"
                        />
                        <div className="flex gap-3">
                            <button
                                onClick={handleApprove}
                                disabled={loading || !nameInput.trim()}
                                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 rounded font-medium disabled:opacity-50 text-sm"
                            >
                                Approve
                            </button>
                            <button
                                onClick={handleReject}
                                disabled={loading || !nameInput.trim()}
                                className="px-4 py-2 bg-rose-600 hover:bg-rose-700 rounded font-medium disabled:opacity-50 text-sm"
                            >
                                Reject
                            </button>
                        </div>
                    </div>
                )}

                {action?.status === "approved" && (
                    <button
                        onClick={handleExecute}
                        disabled={loading}
                        className="px-4 py-2 bg-amber-600 hover:bg-amber-700 rounded font-medium disabled:opacity-50 text-slate-950"
                    >
                        {loading ? "Executing..." : "Execute Remediation"}
                    </button>
                )}

                {action?.status === "executed" && action.result && (
                    <div className="p-4 bg-emerald-950/30 border border-emerald-900 rounded text-emerald-300 font-medium text-sm flex flex-col gap-2">
                        <div className="flex items-center gap-2">
                            <span>Remediation executed successfully</span>
                        </div>
                        {action.result.commit_sha && (
                            <span className="font-mono text-xs opacity-75">SHA: {action.result.commit_sha}</span>
                        )}
                    </div>
                )}

                {action?.status === "execution_failed" && action.result && (
                    <div className="p-4 bg-rose-950/30 border border-rose-900 rounded text-rose-300 text-sm font-medium">
                        Execution Failed: {action.result.error || "Unknown Error"}
                        {/* Out of scope: manual retry */}
                    </div>
                )}

                {action?.status === "execution_unsupported" && (
                    <div className="p-4 bg-amber-950/30 border border-amber-900 rounded text-amber-300 text-sm font-medium">
                        This remediation type isn't implemented in this build
                    </div>
                )}

                {action?.status === "rejected" && (
                    <div className="text-slate-400 font-medium">
                        Remediation rejected by <span className="text-slate-300">{action.approved_by}</span>
                    </div>
                )}
            </div>
        </div>
    );
}
