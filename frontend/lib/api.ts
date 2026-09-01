export type Health = { status: string; db: string };
export type DetectionStatus = { last_run_at: string | null; last_run_new_incidents: number; last_error: string | null; poll_interval_seconds: number };
export type Incident = { id: number; type: string; service: string; severity: string; timestamp: string; trigger: string; status: string; initial_metrics: Record<string, unknown> | null; resolved_at: string | null };
export type Evidence = { id: number; incident_id: number; category: string; content: any; created_at: string };
export type DetectionRun = { new_incidents: Incident[] };
export type SimulatorState = { bad_deployment_active: boolean;[key: string]: unknown };
export type SimulatorAction = { status: string; commit_sha: string;[key: string]: unknown };
export type RemediationAction = { id: number; incident_id: number; action_type: string; params: Record<string, any>; risk_level: string; approved: boolean; approved_by: string | null; executed_at: string | null; status: string; result: any; };
export type VerificationResult = { id: number; incident_id: number; before_metrics: Record<string, unknown> | null; after_metrics: Record<string, unknown> | null; recovered: boolean; checked_at: string; };
export type IncidentReport = { markdown: string; generated_at: string };


const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const simulatorUrl = process.env.NEXT_PUBLIC_SIMULATOR_URL ?? "http://localhost:9000";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, cache: "no-store" });
  const body = await response.text();
  let data: unknown = null;
  try { data = body ? JSON.parse(body) : null; } catch { data = body; }
  if (!response.ok) throw new Error(`Request failed (${response.status}): ${typeof data === "string" ? data : JSON.stringify(data)}`);
  return data as T;
}

export const getHealth = () => request<Health>(`${apiUrl}/health`);
export const getDetectionStatus = () => request<DetectionStatus>(`${apiUrl}/detection/status`);
export const listIncidents = (status?: string) => request<Incident[]>(`${apiUrl}/incidents${status ? `?status=${encodeURIComponent(status)}` : ""}`);
export const getIncident = (id: number) => request<Incident>(`${apiUrl}/incidents/${id}`);
export const runDetectionPass = () => request<DetectionRun>(`${apiUrl}/detection/run`, { method: "POST" });
export const simulateBadDeployment = () => request<SimulatorAction>(`${simulatorUrl}/simulate/bad-deployment`, { method: "POST" });
export const simulateReset = () => request<SimulatorAction>(`${simulatorUrl}/simulate/reset`, { method: "POST" });
export const getSimulateState = () => request<SimulatorState>(`${simulatorUrl}/simulate/state`);
export const getIncidentEvidence = (id: number) => request<Evidence[]>(`${apiUrl}/incidents/${id}/evidence`);
export const runInvestigation = (id: number) => request<any>(`${apiUrl}/investigation/run/${id}`, { method: "POST" });
export const runRCA = (id: number) => request<any>(`${apiUrl}/ai/rca/${id}`, { method: "POST" });
export const proposeRemediation = (incidentId: number) => request<any>(`${apiUrl}/remediation/propose/${incidentId}`, { method: "POST" });
export const approveRemediation = (actionId: number, approvedBy: string) => request<any>(`${apiUrl}/remediation/${actionId}/approve`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ approved_by: approvedBy }) });
export const rejectRemediation = (actionId: number, rejectedBy: string) => request<any>(`${apiUrl}/remediation/${actionId}/reject`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ rejected_by: rejectedBy }) });
export const executeRemediation = (actionId: number) => request<any>(`${apiUrl}/remediation/${actionId}/execute`, { method: "POST" });
export const getIncidentRemediation = (incidentId: number) => request<RemediationAction | null>(`${apiUrl}/incidents/${incidentId}/remediation`);
export const runVerification = (incidentId: number) => request<any>(`${apiUrl}/verification/run/${incidentId}`, { method: "POST" });
export const getIncidentVerification = (incidentId: number) => request<VerificationResult | null>(`${apiUrl}/incidents/${incidentId}/verification`);
export const sendRazorpayDemoWebhook = (variant: "valid" | "tampered" | "duplicate") => request<any>(`${simulatorUrl}/simulate/razorpay-webhook?variant=${encodeURIComponent(variant)}`, { method: "POST" });
export const getIncidentReport = (incidentId: number) => request<IncidentReport>(`${apiUrl}/incidents/${incidentId}/report`);
