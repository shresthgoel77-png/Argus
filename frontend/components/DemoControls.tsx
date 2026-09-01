"use client";
import { useState } from "react";
import { runDetectionPass, simulateBadDeployment, simulateReset, sendRazorpayDemoWebhook } from "@/lib/api";

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

      {message && <p className="mt-4 break-words text-sm text-slate-300" role="status">{message}</p>}
    </section>
  );
}
