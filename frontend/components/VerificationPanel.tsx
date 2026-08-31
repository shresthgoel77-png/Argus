import React, { useEffect, useState, useCallback } from "react";
import { Evidence, RemediationAction, VerificationResult, runVerification, getIncidentVerification, getIncidentRemediation } from "@/lib/api";

type Props = {
    incidentId: number;
    incidentStatus: string;
    evidenceRows: Evidence[];
    onStatusChange: () => void;
};

export default function VerificationPanel({ incidentId, incidentStatus, evidenceRows, onStatusChange }: Props) {
    const [verificationResult, setVerificationResult] = useState<VerificationResult | null>(null);
    const [remediation, setRemediation] = useState<RemediationAction | null>(null);
    const [loading, setLoading] = useState(false);
    const [errorMsg, setErrorMsg] = useState<string | null>(null);

    const fetchData = useCallback(async () => {
        try {
            const [verResult, remAction] = await Promise.all([
                getIncidentVerification(incidentId),
                getIncidentRemediation(incidentId),
            ]);
            setVerificationResult(verResult);
            setRemediation(remAction);
        } catch (err: any) {
            console.error("Error fetching verification data:", err);
        }
    }, [incidentId]);

    useEffect(() => {
        void fetchData();
    }, [fetchData]);

    const handleRunVerification = async () => {
        setLoading(true);
        setErrorMsg(null);
        try {
            await runVerification(incidentId);
            // Poll for the result since it may take time
            // Give server a moment to persist, then fetch
            await new Promise(resolve => setTimeout(resolve, 1000));
            await fetchData();
            onStatusChange();
        } catch (err: any) {
            setErrorMsg(err.message || String(err));
        } finally {
            setLoading(false);
        }
    };

    // Render state: incident not yet remediated
    if (incidentStatus === "open" || incidentStatus === "investigating" || 
        incidentStatus === "investigated" || incidentStatus === "rca_complete" ||
        incidentStatus === "remediation_proposed" || incidentStatus === "remediating" ||
        incidentStatus === "execution_failed") {
        return (
            <div className="mt-4 p-4 border border-slate-700 bg-slate-900 rounded text-slate-400">
                Verification will run once remediation succeeds
            </div>
        );
    }

    // Render state: remediation was rejected
    if (incidentStatus === "remediation_rejected") {
        return (
            <div className="mt-4 p-4 border border-slate-700 bg-slate-900 rounded text-slate-400">
                Remediation was rejected — verification not available
            </div>
        );
    }

    // Render state: remediation failed
    if (incidentStatus === "remediation_failed") {
        return (
            <div className="mt-4 p-5 border border-rose-900 bg-rose-950/30 rounded space-y-4">
                <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold text-rose-200">Recovery Verification Failed</h3>
                    <span className="text-xs px-3 py-1 rounded border border-rose-800 bg-rose-900/50 text-rose-200 uppercase tracking-widest font-medium">
                        FAILED
                    </span>
                </div>
                <p className="text-rose-300">
                    Remediation did not resolve the incident — recovery was not verified within the wait window.
                </p>
                
                {verificationResult && verificationResult.after_metrics && (
                    <div className="mt-4 pt-4 border-t border-rose-900">
                        <h4 className="text-sm font-semibold text-rose-400 uppercase tracking-wide mb-3">Observed State</h4>
                        {verificationResult.after_metrics && typeof verificationResult.after_metrics === 'object' && 'final_detector_result' in verificationResult.after_metrics && (
                            <div className="bg-slate-950/50 p-3 rounded text-sm mb-2">
                                <p className="text-rose-300">
                                    Detector Status: <span className="font-mono text-rose-200">
                                        {(verificationResult.after_metrics.final_detector_result as any)?.firing ? "FIRING" : "NOT FIRING"}
                                    </span>
                                </p>
                                {(verificationResult.after_metrics.final_detector_result as any)?.value !== undefined && (
                                    <p className="text-rose-300 mt-1">
                                        Value: <span className="font-mono text-rose-200">
                                            {(verificationResult.after_metrics.final_detector_result as any).value}
                                        </span>
                                    </p>
                                )}
                            </div>
                        )}
                        {verificationResult.after_metrics && typeof verificationResult.after_metrics === 'object' && 'final_health_status' in verificationResult.after_metrics && (
                            <p className="text-slate-400 text-sm">
                                Simulator Health: <span className="font-mono text-slate-300">
                                    {(verificationResult.after_metrics.final_health_status as string)}
                                </span>
                            </p>
                        )}
                    </div>
                )}
            </div>
        );
    }

    // Render state: remediated but not yet verified
    if (incidentStatus === "remediated" && !verificationResult) {
        return (
            <div className="mt-4 p-5 border border-slate-700 bg-slate-800 rounded space-y-4">
                <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold text-slate-100">Recovery Verification</h3>
                    <span className="text-xs px-3 py-1 rounded border border-amber-700 bg-amber-900/50 text-amber-200 uppercase tracking-widest font-medium">
                        PENDING
                    </span>
                </div>

                {loading ? (
                    <div className="space-y-3">
                        <div className="flex items-center gap-2">
                            <div className="animate-spin h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full"></div>
                            <p className="text-slate-300">
                                Checking recovery... this may take up to a minute
                            </p>
                        </div>
                        <p className="text-sm text-slate-400">
                            Polling detector and simulator health status to confirm incident is truly resolved.
                        </p>
                    </div>
                ) : (
                    <>
                        <p className="text-slate-400 text-sm">
                            Remediation has succeeded. Click below to verify that the underlying issue has actually been resolved.
                        </p>

                        {errorMsg && (
                            <div className="p-3 bg-rose-950/40 border border-rose-900 text-rose-300 rounded text-sm">
                                {errorMsg}
                            </div>
                        )}

                        <button
                            onClick={handleRunVerification}
                            disabled={loading}
                            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded font-medium disabled:opacity-50 transition"
                        >
                            Run Verification
                        </button>
                    </>
                )}
            </div>
        );
    }

    // Render state: resolved (verified successfully)
    if (incidentStatus === "resolved" && verificationResult && verificationResult.recovered) {
        const beforeMetrics = verificationResult.before_metrics;
        const afterMetrics = verificationResult.after_metrics;
        const finalDetectorResult = afterMetrics && typeof afterMetrics === 'object' && 'final_detector_result' in afterMetrics 
            ? (afterMetrics.final_detector_result as any)
            : null;
        const finalHealthStatus = afterMetrics && typeof afterMetrics === 'object' && 'final_health_status' in afterMetrics
            ? (afterMetrics.final_health_status as string)
            : null;

        return (
            <div className="mt-4 p-5 border border-emerald-900 bg-emerald-950/30 rounded space-y-4">
                <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold text-emerald-200">Recovery Verified</h3>
                    <span className="text-xs px-3 py-1 rounded border border-emerald-700 bg-emerald-900/50 text-emerald-200 uppercase tracking-widest font-medium">
                        PASSED
                    </span>
                </div>

                <p className="text-emerald-300">
                    ✓ Incident has been successfully resolved. The detector confirms normal operation and simulator is healthy.
                </p>

                <div className="grid grid-cols-2 gap-4 mt-4 pt-4 border-t border-emerald-900">
                    {/* Before Section */}
                    <div className="bg-slate-950/50 p-4 rounded border border-slate-700">
                        <h4 className="text-sm font-semibold text-amber-400 uppercase tracking-wide mb-2">Before</h4>
                        {beforeMetrics && typeof beforeMetrics === 'object' && (
                            <pre className="text-xs text-slate-300 whitespace-pre-wrap overflow-x-auto max-h-32">
                                {JSON.stringify(beforeMetrics, null, 2)}
                            </pre>
                        )}
                    </div>

                    {/* After Section */}
                    <div className="bg-slate-950/50 p-4 rounded border border-emerald-700">
                        <h4 className="text-sm font-semibold text-emerald-400 uppercase tracking-wide mb-2">After</h4>
                        <div className="space-y-2">
                            {finalDetectorResult && (
                                <div>
                                    <p className="text-xs text-slate-400 mb-1">Detector Result:</p>
                                    <p className="text-xs text-emerald-300 font-mono">
                                        {finalDetectorResult.firing ? "FIRING" : "RESOLVED"}
                                        {finalDetectorResult.value !== undefined && ` (value: ${finalDetectorResult.value})`}
                                    </p>
                                </div>
                            )}
                            {finalHealthStatus && (
                                <div>
                                    <p className="text-xs text-slate-400 mb-1">Simulator Health:</p>
                                    <p className="text-xs text-emerald-300 font-mono">{finalHealthStatus}</p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {remediation && remediation.result && typeof remediation.result === 'object' && 'commit_sha' in remediation.result && (
                    <div className="mt-3 p-3 bg-slate-950/50 rounded border border-slate-700 text-sm">
                        <p className="text-slate-400">
                            Rollback Executed: <span className="font-mono text-slate-300">{(remediation.result.commit_sha as string)}</span>
                        </p>
                    </div>
                )}

                <p className="text-xs text-slate-500 italic">
                    Verified at: {new Date(verificationResult.checked_at).toLocaleString()}
                </p>
            </div>
        );
    }

    // Fallback
    return (
        <div className="mt-4 p-4 border border-slate-700 bg-slate-900 rounded text-slate-400">
            Verification data unavailable
        </div>
    );
}

/*
Manual Verification Test Steps:
1. Trigger a realistic incident end-to-end via the simulator:
   - Click "Trigger Bad Deployment" on dashboard
   - Run Detection, Investigation, RCA, and Propose Remediation
2. Approve and Execute the remediation:
   - Click Approve and then Execute Remediation
   - Wait for the incident status to change to "remediated"
3. Run Verification:
   - Navigate to the incident detail page
   - Scroll to the Verification section
   - Click "Run Verification" button
   - Wait up to 60 seconds for the verification to complete
   - The UI should show a loading spinner with "Checking recovery... this may take up to a minute"
4. Confirm Results:
   - Once complete, verify the PASSED badge appears
   - Confirm the Before/After comparison displays correctly
   - Before block should show the original incident metrics
   - After block should show the detector result and simulator health
   - The rollback commit SHA should be visible
   - Dashboard should show incident status as "resolved" with a green badge
*/
