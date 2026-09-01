"use client";

import React, { useEffect, useState, useCallback, use } from "react";
import { getIncident, getIncidentEvidence, runInvestigation, runRCA, Incident, Evidence } from "@/lib/api";
import EvidencePanel from "@/components/EvidencePanel";
import TimelineView from "@/components/TimelineView";
import RCAPanel from "@/components/RCAPanel";
import RemediationPanel from "@/components/RemediationPanel";
import VerificationPanel from "@/components/VerificationPanel";
import GitHubPanel from "@/components/GitHubPanel";

// Manual Verification Steps:
// 1. Trigger realistic incident end-to-end via simulator.
// 2. Click "Run Investigation", UI updates on success.
// 3. Click "Run RCA", UI updates on success.
// 4. Panel UI correctly groups facts and AI outputs.

export default function IncidentDetailPage({ params }: { params: Promise<{ id: string }> }) {
    const { id } = use(params);
    const incidentId = parseInt(id, 10);

    const [incident, setIncident] = useState<Incident | null>(null);
    const [evidence, setEvidence] = useState<Evidence[]>([]);
    const [loading, setLoading] = useState(true);
    const [errorNotFound, setErrorNotFound] = useState(false);

    const [actionLoading, setActionLoading] = useState(false);
    const [actionError, setActionError] = useState<string | null>(null);

    const fetchData = useCallback(async () => {
        try {
            const inc = await getIncident(incidentId);
            setIncident(inc);

            try {
                const evRows = await getIncidentEvidence(incidentId);
                setEvidence(evRows);
            } catch (err) {
                // Ignoring evidence fetch error if incident fetch succeeded
            }
        } catch (err: any) {
            if (err.message && err.message.includes("404")) setErrorNotFound(true);
        } finally {
            setLoading(false);
        }
    }, [incidentId]);

    useEffect(() => {
        void fetchData();
    }, [fetchData]);

    if (loading) return <div className="p-8 text-slate-300">Loading incident...</div>;
    if (errorNotFound || !incident) return <div className="p-8 text-rose-300">Incident not found</div>;

    const handleRunInvestigation = async () => {
        setActionLoading(true);
        setActionError(null);
        try {
            await runInvestigation(incidentId);
            await fetchData();
        } catch (err: any) {
            setActionError(err.message || String(err));
        } finally {
            setActionLoading(false);
        }
    };

    const handleRunRCA = async () => {
        setActionLoading(true);
        setActionError(null);
        try {
            await runRCA(incidentId);
            await fetchData();
        } catch (err: any) {
            setActionError(err.message || String(err));
        } finally {
            setActionLoading(false);
        }
    };

    return (
        <main className="min-h-screen bg-slate-950 px-6 py-10 text-slate-100 space-y-8">
            <div className="mx-auto max-w-5xl">

                {/* Header */}
                <div className="border-b border-slate-800 pb-6 mb-6">
                    <div className="flex items-center justify-between">
                        <div>
                            <h1 className="text-3xl font-bold flex items-center gap-3">
                                {incident.type} <span className="text-lg font-medium text-slate-400">#{incident.id}</span>
                            </h1>
                            <p className="mt-2 text-slate-400 capitalize">
                                Service: <span className="font-semibold text-slate-300">{incident.service}</span> •
                                Severity: <span className="font-semibold text-slate-300 mx-1">{incident.severity}</span> •
                                Status: <span className="font-semibold text-slate-300 mx-1">{incident.status}</span>
                            </p>
                            <p className="mt-1 text-sm text-slate-500">
                                Created: {new Date(incident.timestamp).toLocaleString()}
                            </p>
                        </div>
                        <div className="flex gap-4">
                            <button
                                onClick={handleRunInvestigation}
                                disabled={incident.status !== "open" || actionLoading}
                                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed rounded font-medium transition"
                            >
                                {actionLoading && incident.status === "open" ? "Running..." : "Run Investigation"}
                            </button>
                            <button
                                onClick={handleRunRCA}
                                disabled={incident.status !== "investigated" || actionLoading}
                                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed rounded font-medium transition"
                            >
                                {actionLoading && incident.status === "investigated" ? "Running..." : "Run RCA"}
                            </button>
                        </div>
                    </div>
                    {actionError && (
                        <div className="mt-4 p-3 bg-rose-950/40 border border-rose-900 text-rose-300 rounded">
                            Error executing action: {actionError}
                        </div>
                    )}
                </div>

                {/* Content sections */}
                <div className="space-y-12">

                    <section>
                        <h2 className="text-2xl font-bold border-b border-slate-800 pb-2">Timeline</h2>
                        <TimelineView evidenceRows={evidence} />
                    </section>

                    <section>
                        <h2 className="text-2xl font-bold border-b border-slate-800 pb-2">Evidence</h2>
                        <EvidencePanel evidenceRows={evidence} />
                    </section>

                    <section>
                        <h2 className="text-2xl font-bold border-b border-slate-800 pb-2">AI RCA</h2>
                        <RCAPanel evidenceRows={evidence} />
                    </section>

                    <section>
                        <h2 className="text-2xl font-bold border-b border-slate-800 pb-2">Remediation</h2>
                        <RemediationPanel incidentId={incidentId} incidentStatus={incident.status} evidenceRows={evidence} onStatusChange={fetchData} />
                    </section>

                    <section>
                        <h2 className="text-2xl font-bold border-b border-slate-800 pb-2">Verification</h2>
                        <VerificationPanel incidentId={incidentId} incidentStatus={incident.status} evidenceRows={evidence} onStatusChange={fetchData} />
                    </section>

                    <section>
                        <h2 className="text-2xl font-bold border-b border-slate-800 pb-2">Incident Report</h2>
                        <GitHubPanel incidentId={incidentId} incidentStatus={incident.status} />
                    </section>

                </div>

            </div>
        </main>
    );
}
