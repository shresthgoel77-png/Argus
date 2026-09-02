"use client";
import { useState } from "react";
import { runDetectionPass, simulateBadDeployment, simulateReset, sendRazorpayDemoWebhook, simulateWarmUp, resetDemoData } from "@/lib/api";

type Props = { onCompleted: () => void };

export default function DemoControls({ onCompleted }: Props) {
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function perform(action: "bad-deployment" | "reset" | "detection") {
    setBusy(action); setMessage(null);
    try {
      if (action === "bad-deployment") {
        const result = await simulateBadDeployment();
        setMessage(`Bad deployment triggered: ${result.commit_sha}`);
      } else if (action === "reset") {
        const result = await simulateReset();
        setMessage(`Reset completed: ${result.commit_sha}`);
      } else {
        const result = await runDetectionPass();
        setMessage(`Detection pass completed: ${result.new_incidents.length} new incident(s).`);
      }
      onCompleted();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(null);
    }
  }

  async function performRazorpay(variant: "valid" | "tampered" | "duplicate") {
    setBusy(`razorpay-${variant}`);
    setMessage(null);
    try {
      const result = await sendRazorpayDemoWebhook(variant);
      setMessage(`Razorpay ${variant} result: status=${result.result?.status}, event_id=${result.event_id}`);
      onCompleted();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(null);
    }
  }

  async function performRehearsal(action: "warm-up" | "reset-demo") {
    if (action === "reset-demo") {
      if (!window.confirm("WARNING: This will destructively delete all demo data from the database. Are you sure?")) {
        return;
      }
    }
    setBusy(`rehearsal-${action}`);
    setMessage(null);
    try {
      if (action === "warm-up") {
        const result = await simulateWarmUp();
        setMessage(`Warm up completed: sent ${result.requests_sent} requests. 2xx: ${result.results_summary["2xx"]}, 5xx: ${result.results_summary["5xx"]}`);
      } else {
        const result = await resetDemoData();
        setMessage(`Reset completed: Tables cleared: ${result.tables_cleared.join(", ")}`);
      }
      onCompleted();
    } catch (error: any) {
      if (error?.message?.includes("403")) {
        setMessage("Reset unavailable \u2014 set DEMO_MODE=true to enable");
      } else {
        setMessage(error instanceof Error ? error.message : String(error));
      }
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="rounded-xl border border-slate-700 bg-slate-900 p-5 shadow-sm">
      <h2 className="text-lg font-semibold">Demo Controls</h2>
      <div className="mt-3 flex flex-wrap gap-3">
        <button disabled={busy !== null} onClick={() => perform("bad-deployment")} className="rounded bg-rose-600 px-4 py-2 text-sm font-medium disabled:opacity-50">
          {busy === "bad-deployment" ? "Triggering…" : "Trigger Bad Deployment"}
        </button>
        <button disabled={busy !== null} onClick={() => perform("reset")} className="rounded bg-slate-700 px-4 py-2 text-sm font-medium disabled:opacity-50">
          {busy === "reset" ? "Resetting…" : "Reset"}
        </button>
        <button disabled={busy !== null} onClick={() => perform("detection")} className="rounded bg-sky-700 px-4 py-2 text-sm font-medium disabled:opacity-50">
          {busy === "detection" ? "Running…" : "Run Detection Pass"}
        </button>
      </div>

      <h3 className="text-md font-medium mt-5 mb-2 text-slate-300">Razorpay Simulation</h3>
      <div className="flex flex-wrap gap-3">
        <button disabled={busy !== null} onClick={() => performRazorpay("valid")} className="rounded bg-emerald-700 px-4 py-2 text-sm font-medium disabled:opacity-50">
          {busy === "razorpay-valid" ? "Sending…" : "Send Valid Webhook"}
        </button>
        <button disabled={busy !== null} onClick={() => performRazorpay("tampered")} className="rounded bg-amber-700 px-4 py-2 text-sm font-medium disabled:opacity-50">
          {busy === "razorpay-tampered" ? "Sending…" : "Send Tampered Webhook"}
        </button>
        <button disabled={busy !== null} onClick={() => performRazorpay("duplicate")} className="rounded bg-purple-700 px-4 py-2 text-sm font-medium disabled:opacity-50">
          {busy === "razorpay-duplicate" ? "Sending…" : "Send Duplicate Webhook"}
        </button>
      </div>

      <h3 className="text-md font-medium mt-5 mb-2 text-slate-300">Rehearsal Tools</h3>
      <div className="flex flex-wrap gap-3 rounded border border-dashed border-slate-600 p-3">
        <button disabled={busy !== null} onClick={() => performRehearsal("warm-up")} className="rounded bg-slate-600 px-4 py-2 text-sm font-medium disabled:opacity-50 hover:bg-slate-500">
          {busy === "rehearsal-warm-up" ? "Warming Up…" : "Warm Up Traffic"}
        </button>
        <button disabled={busy !== null} onClick={() => performRehearsal("reset-demo")} className="rounded bg-rose-900 border border-rose-500 px-4 py-2 text-sm font-medium disabled:opacity-50 hover:bg-rose-800">
          {busy === "rehearsal-reset-demo" ? "Resetting Demo…" : "Reset Demo Data"}
        </button>
      </div>

      {message && <p className="mt-4 break-words text-sm text-slate-300" role="status">{message}</p>}
    </section>
  );
}
