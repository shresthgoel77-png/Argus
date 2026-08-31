import Link from "next/link";
import type { Incident } from "@/lib/api";

function getStatusBadgeColor(status: string): string {
  if (status === "resolved") return "bg-emerald-900/40 border-emerald-700 text-emerald-300";
  if (status === "open" || status === "investigating" || status === "investigated" || status === "rca_complete" || status === "remediation_proposed" || status === "remediating") return "bg-amber-900/40 border-amber-700 text-amber-300";
  if (status === "remediation_failed" || status === "remediation_rejected" || status === "execution_failed") return "bg-rose-900/40 border-rose-700 text-rose-300";
  return "bg-slate-900/40 border-slate-700 text-slate-300";
}

type Props = { incidents: Incident[]; error: string | null };

export default function IncidentList({ incidents, error }: Props) {
  return (
    <section className="rounded-xl border border-slate-700 bg-slate-900 p-5 shadow-sm">
      <h2 className="text-lg font-semibold">Recent Incidents</h2>
      {error ? (
        <p className="mt-3 text-sm text-rose-300">Unable to load incidents: {error}</p>
      ) : incidents.length === 0 ? (
        <p className="mt-3 text-sm text-slate-400">No incidents recorded yet.</p>
      ) : (
        <ul className="mt-3 divide-y divide-slate-700">
          {incidents.slice(0, 10).map((incident) => (
            <li key={incident.id}>
              <Link href={`/incidents/${incident.id}`} className="block py-3 hover:bg-slate-800">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium text-sky-300">{incident.type}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs uppercase text-slate-300">{incident.severity}</span>
                    <span className={`text-xs uppercase px-2 py-1 rounded border font-medium ${getStatusBadgeColor(incident.status)}`}>
                      {incident.status}
                    </span>
                  </div>
                </div>
                <p className="mt-1 text-sm text-slate-400">{new Date(incident.timestamp).toLocaleString()}</p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
