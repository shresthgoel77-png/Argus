import Link from "next/link";
import type { Incident } from "@/lib/api";
type Props = { incidents: Incident[]; error: string | null };
export default function IncidentList({ incidents, error }: Props) {
  return <section className="rounded-xl border border-slate-700 bg-slate-900 p-5 shadow-sm"><h2 className="text-lg font-semibold">Recent Incidents</h2>{error ? <p className="mt-3 text-sm text-rose-300">Unable to load incidents: {error}</p> : incidents.length === 0 ? <p className="mt-3 text-sm text-slate-400">No incidents recorded yet.</p> : <ul className="mt-3 divide-y divide-slate-700">{incidents.slice(0, 10).map((incident) => <li key={incident.id}><Link href={`/incidents/${incident.id}`} className="block py-3 hover:bg-slate-800"><div className="flex flex-wrap items-center justify-between gap-2"><span className="font-medium text-sky-300">{incident.type}</span><span className="text-xs uppercase text-slate-300">{incident.severity} · {incident.status}</span></div><p className="mt-1 text-sm text-slate-400">{new Date(incident.timestamp).toLocaleString()}</p></Link></li>)}</ul>}</section>;
}
