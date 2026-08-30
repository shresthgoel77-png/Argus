import React from "react";
import { Evidence } from "@/lib/api";

type Props = {
    evidenceRows: Evidence[];
};

export default function TimelineView({ evidenceRows }: Props) {
    const timelineEvidence = evidenceRows.find((e) => e.category === "timeline");
    const events = timelineEvidence?.content?.events || timelineEvidence?.content || [];

    if (!Array.isArray(events) || events.length === 0) {
        return (
            <div className="mt-4 p-4 border border-slate-700 bg-slate-900 rounded text-slate-400">
                No timeline events available.
            </div>
        );
    }

    return (
        <div className="space-y-4 mt-4">
            {events.map((event: any, idx: number) => {
                const time = event.timestamp || event.time || event.created_at || "Unknown Time";
                const desc = event.description || event.message || JSON.stringify(event);
                return (
                    <div key={idx} className="flex gap-4 p-3 border-l-2 border-slate-600 bg-slate-800/50 rounded-r">
                        <span className="text-sm font-mono text-slate-400 shrink-0">{new Date(time).toLocaleTimeString()}</span>
                        <span className="text-sm text-slate-200">{desc}</span>
                    </div>
                );
            })}
        </div>
    );
}
