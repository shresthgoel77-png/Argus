"use client";

/*
Manual test: start backend, simulator, and frontend; click Trigger Bad Deployment
and confirm its returned commit SHA; click Run Detection Pass and confirm its
real incident count; click Reset and confirm its returned commit SHA. The health
and incident panels refresh from the live services every five seconds.
*/
import { useCallback, useEffect, useState } from "react";
import DemoControls from "@/components/DemoControls";
import HealthBadge from "@/components/HealthBadge";
import IncidentList from "@/components/IncidentList";
import {
  getDetectionStatus,
  getHealth,
  listIncidents,
  type DetectionStatus,
  type Health,
  type Incident,
} from "@/lib/api";

const activeStatuses = new Set(["open", "investigating", "investigated", "rca_complete"]);

export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [detection, setDetection] = useState<DetectionStatus | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [incidentsError, setIncidentsError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [healthResult, detectionResult, incidentsResult] = await Promise.allSettled([
      getHealth(), getDetectionStatus(), listIncidents(),
    ]);
    if (healthResult.status === "fulfilled" && detectionResult.status === "fulfilled") {
      setHealth(healthResult.value);
      setDetection(detectionResult.value);
      setHealthError(null);
    } else {
      setHealth(null);
      setDetection(null);
      const failed = healthResult.status === "rejected"
        ? healthResult.reason
        : detectionResult.status === "rejected"
          ? detectionResult.reason
          : new Error("Detection status unavailable");
      setHealthError(failed instanceof Error ? failed.message : String(failed));
    }
    if (incidentsResult.status === "fulfilled") {
      setIncidents(incidentsResult.value);
      setIncidentsError(null);
    } else {
      setIncidents([]);
      setIncidentsError(incidentsResult.reason instanceof Error ? incidentsResult.reason.message : String(incidentsResult.reason));
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 5_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const activeIncident = incidents.find((incident) => activeStatuses.has(incident.status));

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-10 text-slate-100">
      <div className="mx-auto max-w-5xl">
        <h1 className="text-3xl font-bold">AI Reliability Engineer</h1>
        <p className="mt-2 text-slate-400">Live reliability dashboard</p>
        <div className="mt-8 grid gap-5 md:grid-cols-2">
          <HealthBadge health={health} detection={detection} error={healthError} />
          <DemoControls onCompleted={() => void refresh()} />
        </div>
        <section className="mt-5 rounded-xl border border-slate-700 bg-slate-900 p-5 shadow-sm">
          <h2 className="text-lg font-semibold">Active Incident</h2>
          {activeIncident ? (
            <div className="mt-3">
              <p className="font-medium text-rose-300">{activeIncident.type} · {activeIncident.severity}</p>
              <p className="mt-1 text-sm text-slate-300">{activeIncident.status} since {new Date(activeIncident.timestamp).toLocaleString()}</p>
            </div>
          ) : incidentsError ? (
            <p className="mt-3 text-sm text-rose-300">Unable to determine active incidents: {incidentsError}</p>
          ) : (
            <p className="mt-3 text-sm text-slate-400">No active incidents.</p>
          )}
        </section>
        <div className="mt-5"><IncidentList incidents={incidents} error={incidentsError} /></div>
      </div>
    </main>
  );
}
