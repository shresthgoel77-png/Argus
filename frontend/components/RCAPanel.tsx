import React from "react";
import { Evidence } from "@/lib/api";

type Props = {
    evidenceRows: Evidence[];
};

export default function RCAPanel({ evidenceRows }: Props) {
    const rcaEvidence = evidenceRows.find((e) => e.category === "ai_rca");

    if (!rcaEvidence) {
        return (
            <div className="mt-4 p-4 border border-slate-700 bg-slate-900 rounded text-slate-400">
                RCA not yet run
            </div>
        );
    }

    const rca = rcaEvidence.content as any;
    const confidenceColor =
        rca.confidence === "high" ? "bg-green-600" :
            rca.confidence === "medium" ? "bg-amber-600" : "bg-rose-600";

    return (
        <div className="mt-4 p-5 border border-slate-700 bg-slate-800 rounded space-y-4">
            <div className="flex items-center gap-3">
                <h3 className="text-xl font-semibold text-slate-100">Root Cause Analysis</h3>
                {rca.confidence && (
                    <span className={`px-2 py-1 text-xs font-medium rounded text-white ${confidenceColor} capitalize`}>
                        {rca.confidence} Confidence
                    </span>
                )}
            </div>

            <div>
                <h4 className="text-sm font-semibold text-slate-400 uppercase tracking-wide">Summary</h4>
                <p className="mt-1 text-slate-200">{rca.summary}</p>
            </div>

            <div>
                <h4 className="text-sm font-semibold text-slate-400 uppercase tracking-wide">Root Cause</h4>
                <p className="mt-1 text-slate-200">{rca.root_cause}</p>
            </div>

            {rca.affected_components && rca.affected_components.length > 0 && (
                <div>
                    <h4 className="text-sm font-semibold text-slate-400 uppercase tracking-wide">Affected Components</h4>
                    <ul className="mt-1 list-disc list-inside text-slate-200">
                        {rca.affected_components.map((c: string, idx: number) => (
                            <li key={idx}>{c}</li>
                        ))}
                    </ul>
                </div>
            )}

            {rca.recommended_fix && (
                <div>
                    <h4 className="text-sm font-semibold text-slate-400 uppercase tracking-wide">Recommended Fix</h4>
                    <p className="mt-1 text-slate-200">{rca.recommended_fix}</p>
                </div>
            )}
        </div>
    );
}
