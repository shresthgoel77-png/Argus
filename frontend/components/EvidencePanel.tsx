import React from "react";
import { Evidence } from "@/lib/api";

type Props = {
    evidenceRows: Evidence[];
};

export default function EvidencePanel({ evidenceRows }: Props) {
    const observedFacts = evidenceRows.filter(
        (e) => !e.category.includes("hypothesis") && !e.category.includes("error") && e.category !== "ai_rca" && e.category !== "timeline"
    );
    const hypotheses = evidenceRows.filter((e) => e.category.includes("hypothesis"));
    const errors = evidenceRows.filter((e) => e.category.includes("error"));

    if (evidenceRows.length === 0) {
        return (
            <div className="mt-4 p-4 border border-slate-700 bg-slate-900 rounded text-slate-300">
                No evidence collected yet — run investigation
            </div>
        );
    }

    const renderContent = (content: any) => {
        if (!content) return "No content";

        if (content.signal && (content.peak_value !== undefined)) {
            return (
                <div className="mt-2 bg-slate-950 p-4 rounded border border-slate-800">
                    <div className="flex justify-between items-center mb-2">
                        <span className="text-sm text-slate-400 capitalize font-medium">
                            {content.signal.replace(/_/g, " ")}
                        </span>
                        <span className="font-mono text-lg font-bold text-sky-400">
                            {Number(content.peak_value).toFixed(4)}
                        </span>
                    </div>
                    {content.window && (
                        <div className="text-xs text-slate-500 mb-2 font-mono">
                            Window: {new Date(content.window.start).toLocaleTimeString()} - {new Date(content.window.end).toLocaleTimeString()}
                        </div>
                    )}
                    <details className="mt-3 text-xs text-slate-500">
                        <summary className="cursor-pointer hover:text-slate-300">View Raw Data</summary>
                        <pre className="mt-2 max-h-32 overflow-y-auto whitespace-pre-wrap border border-slate-800 p-2 rounded bg-slate-950">
                            {JSON.stringify(content, null, 2)}
                        </pre>
                    </details>
                </div>
            );
        }

        return (
            <pre className="text-xs max-h-40 overflow-y-auto whitespace-pre-wrap mt-2 bg-slate-950 p-2 rounded">
                {JSON.stringify(content, null, 2)}
            </pre>
        );
    };

    return (
        <div className="space-y-6">
            {observedFacts.length > 0 && (
                <section>
                    <h3 className="text-lg font-semibold text-slate-200">Observed Facts</h3>
                    <div className="mt-3 space-y-4">
                        {observedFacts.map((ev) => (
                            <div key={ev.id} className="p-4 border border-slate-700 bg-slate-800 rounded">
                                <p className="font-medium text-slate-300 capitalize">{ev.category.replace(/_/g, " ")}</p>
                                {renderContent(ev.content)}
                            </div>
                        ))}
                    </div>
                </section>
            )}

            {hypotheses.length > 0 && (
                <section>
                    <h3 className="text-lg font-semibold text-slate-200">Hypotheses</h3>
                    <div className="mt-3 space-y-4">
                        {hypotheses.map((ev) => (
                            <div key={ev.id} className="p-4 border border-slate-700 bg-slate-800 rounded">
                                <p className="font-medium text-slate-300 capitalize">{ev.category.replace(/_/g, " ")}</p>
                                {renderContent(ev.content)}
                            </div>
                        ))}
                    </div>
                </section>
            )}

            {errors.length > 0 && (
                <section>
                    <h3 className="text-lg font-semibold text-rose-300">Collection Errors</h3>
                    <div className="mt-3 space-y-4">
                        {errors.map((ev) => (
                            <div key={ev.id} className="p-4 border border-rose-900/50 bg-rose-950/20 rounded">
                                <p className="font-medium text-rose-400 capitalize">{ev.category.replace(/_/g, " ")}</p>
                                {renderContent(ev.content)}
                            </div>
                        ))}
                    </div>
                </section>
            )}
        </div>
    );
}
