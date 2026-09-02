import type { DetectionStatus, Health } from "@/lib/api";

type Props = { health: Health | null; detection: DetectionStatus | null; error: string | null };
function timeAgo(timestamp: string | null) {
  if (!timestamp) return "never run yet";
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(timestamp).getTime()) / 1000));
  return seconds < 60 ? `${seconds}s ago` : `${Math.floor(seconds / 60)}m ago`;
}
export default function HealthBadge({ health, detection, error }: Props) {
  const connected = health?.status === "ok" && health?.db === "connected" && !error;
  return <section className="rounded-xl border border-slate-700 bg-slate-900 p-5 shadow-sm"><h2 className="text-lg font-semibold">System Health</h2><p className={`mt-3 font-medium ${connected ? "text-emerald-400" : "text-rose-400"}`}>Backend: {connected ? "Connected" : "Unreachable"}</p>{connected && detection ? <div className="mt-3 space-y-1 text-sm text-slate-300"><p>Detection last ran: {timeAgo(detection.last_run_at)}</p><p>Poll interval: {detection.poll_interval_seconds}s</p><p>New incidents in last pass: {detection.last_run_new_incidents}</p>{detection.last_error && <p className="text-rose-300 break-words line-clamp-3">Last detection error: {detection.last_error}</p>}</div> : <p className="mt-3 text-sm text-slate-400">{error ?? "Checking backend status…"}</p>}</section>;
}
