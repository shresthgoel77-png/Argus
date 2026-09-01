import React, { useEffect, useState, useCallback } from "react";
import { getIncidentReport, IncidentReport } from "@/lib/api";

type Props = {
    incidentId: number;
    incidentStatus: string;
};

export default function GitHubPanel({ incidentId, incidentStatus }: Props) {
    const [report, setReport] = useState<IncidentReport | null>(null);
    const [loading, setLoading] = useState(false);
    const [errorMsg, setErrorMsg] = useState<string | null>(null);
    const [requiresRCA, setRequiresRCA] = useState(false);

    const fetchReport = useCallback(async () => {
        setLoading(true);
        setErrorMsg(null);
        setRequiresRCA(false);
        try {
            const data = await getIncidentReport(incidentId);
            setReport(data);
        } catch (err: any) {
            // Handle 409 status code logic correctly through error boundaries
            const msg = err.message || String(err);
            if (msg.includes("409")) {
                setRequiresRCA(true);
            } else if (msg.includes("404")) {
                setErrorMsg("Incident not found.");
            } else {
                setErrorMsg(msg);
            }
        } finally {
            setLoading(false);
        }
    }, [incidentId]);

    // Initial fetch
    useEffect(() => {
        void fetchReport();
    }, [fetchReport, incidentStatus]);

    // Loading state inline spinner for clean UI
    const renderSpinner = () => (
        <div className="flex items-center gap-2">
            <div className="animate-spin h-4 w-4 border-2 border-slate-500 border-t-transparent rounded-full"></div>
            <span className="text-sm text-slate-400 font-medium">Generating report...</span>
        </div>
    );

    // State 1: 409 requires RCA message (as expected behavior)
    if (requiresRCA) {
        return (
            <div className="mt-4 p-5 border border-slate-700 bg-slate-800 rounded">
                <div className="flex items-center justify-between">
                    <div>
                        <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
                            <svg className="w-5 h-5 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                            Incident Report
                        </h3>
                        <p className="text-slate-400 text-sm mt-1">Run RCA to generate a report.</p>
                    </div>
                </div>
            </div>
        );
    }

    // State 2: General Error
    if (errorMsg && !loading) {
        return (
            <div className="mt-4 p-4 border border-rose-900 bg-rose-950/30 text-rose-300 rounded text-sm flex justify-between items-center">
                <span>Failed to load report: {errorMsg}</span>
                <button
                    onClick={fetchReport}
                    className="px-3 py-1 bg-rose-900 hover:bg-rose-800 rounded transition text-xs font-medium"
                >
                    Retry
                </button>
            </div>
        );
    }

    // State 3: Report Display
    return (
        <div className="mt-4 p-5 border border-slate-700 bg-slate-800 rounded space-y-4">
            <div className="flex items-center justify-between border-b border-slate-700 pb-3">
                <div className="flex items-center gap-3">
                    <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
                        <svg className="w-5 h-5 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        Incident Report
                    </h3>
                    {loading && renderSpinner()}
                </div>

                <button
                    onClick={fetchReport}
                    disabled={loading}
                    className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded text-sm font-medium transition disabled:opacity-50 flex items-center gap-2"
                >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    Regenerate
                </button>
            </div>

            {report ? (
                <div className="bg-slate-900 border border-slate-700 rounded-md overflow-hidden relative">
                    {/* The plain monospace block as requested */}
                    <pre className="p-4 overflow-y-auto max-h-[600px] text-sm text-slate-300 whitespace-pre-wrap font-mono leading-relaxed custom-scrollbar">
                        {report.markdown}
                    </pre>
                </div>
            ) : (
                !loading && <div className="text-slate-400 text-sm">No report available.</div>
            )}

            {report && (
                <p className="text-xs text-slate-500 italic">
                    Last updated: {new Date(report.generated_at).toLocaleString()}
                </p>
            )}
        </div>
    );
}
