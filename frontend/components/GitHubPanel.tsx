import React, { useEffect, useState, useCallback } from "react";
import { getIncidentReport, IncidentReport, getGitHubStatus, getGitHubIssue, createGitHubIssue, GitHubIssue } from "@/lib/api";

type Props = {
    incidentId: number;
    incidentStatus: string;
};

export default function GitHubPanel({ incidentId, incidentStatus }: Props) {
    const [report, setReport] = useState<IncidentReport | null>(null);
    const [loading, setLoading] = useState(false);
    const [errorMsg, setErrorMsg] = useState<string | null>(null);
    const [requiresRCA, setRequiresRCA] = useState(false);

    // GitHub Integration State
    const [githubConfigured, setGithubConfigured] = useState<boolean | null>(null);
    const [githubIssue, setGithubIssue] = useState<GitHubIssue | null>(null);
    const [creatingIssue, setCreatingIssue] = useState(false);
    const [issueError, setIssueError] = useState<string | null>(null);

    const fetchReport = useCallback(async () => {
        setLoading(true);
        setErrorMsg(null);
        setRequiresRCA(false);
        try {
            const data = await getIncidentReport(incidentId);
            setReport(data);
        } catch (err: any) {
            // Handle 409 status code logic correctly through error boundaries
            const msg = err.message || String(err);
            if (msg.includes("409")) {
                setRequiresRCA(true);
            } else if (msg.includes("404")) {
                setErrorMsg("Incident not found.");
            } else {
                setErrorMsg(msg);
            }
        } finally {
            setLoading(false);
        }
    }, [incidentId]);

    const fetchGitHubData = useCallback(async () => {
        try {
            const status = await getGitHubStatus();
            setGithubConfigured(status.configured);
            if (status.configured) {
                const issue = await getGitHubIssue(incidentId);
                setGithubIssue(issue);
            }
        } catch (err) {
            console.error("Failed to fetch GitHub data:", err);
        }
    }, [incidentId]);

    // Initial fetch
    useEffect(() => {
        void fetchReport();
        void fetchGitHubData();
    }, [fetchReport, fetchGitHubData, incidentStatus]);

    const handleCreateIssue = async () => {
        setCreatingIssue(true);
        setIssueError(null);
        try {
            const result = await createGitHubIssue(incidentId);
            setGithubIssue(result);
        } catch (err: any) {
            setIssueError(err.message || String(err));
        } finally {
            setCreatingIssue(false);
        }
    };

    // Loading state inline spinner for clean UI
    const renderSpinner = () => (
        <div className="flex items-center gap-2">
            <div className="animate-spin h-4 w-4 border-2 border-slate-500 border-t-transparent rounded-full"></div>
            <span className="text-sm text-slate-400 font-medium">Generating report...</span>
        </div>
    );

    // State 1: 409 requires RCA message (as expected behavior)
    if (requiresRCA) {
        return (
            <div className="mt-4 p-5 border border-slate-700 bg-slate-800 rounded">
                <div className="flex items-center justify-between">
                    <div>
                        <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
                            <svg className="w-5 h-5 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                            Incident Report
                        </h3>
                        <p className="text-slate-400 text-sm mt-1">Run RCA to generate a report.</p>
                    </div>
                </div>
            </div>
        );
    }

    // State 2: General Error
    if (errorMsg && !loading) {
        return (
            <div className="mt-4 p-4 border border-rose-900 bg-rose-950/30 text-rose-300 rounded text-sm flex justify-between items-center">
                <span>Failed to load report: {errorMsg}</span>
                <button
                    onClick={fetchReport}
                    className="px-3 py-1 bg-rose-900 hover:bg-rose-800 rounded transition text-xs font-medium"
                >
                    Retry
                </button>
            </div>
        );
    }

    // State 3: Report Display
    return (
        <div className="mt-4 p-5 border border-slate-700 bg-slate-800 rounded space-y-4">
            <div className="flex items-center justify-between border-b border-slate-700 pb-3">
                <div className="flex items-center gap-3">
                    <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
                        <svg className="w-5 h-5 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        Incident Report
                    </h3>
                    {loading && renderSpinner()}
                </div>

                <button
                    onClick={fetchReport}
                    disabled={loading}
                    className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded text-sm font-medium transition disabled:opacity-50 flex items-center gap-2"
                >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    Regenerate
                </button>
            </div>

            {report ? (
                <div className="bg-slate-900 border border-slate-700 rounded-md overflow-hidden relative">
                    {/* The plain monospace block as requested */}
                    <pre className="p-4 overflow-y-auto max-h-[600px] text-sm text-slate-300 whitespace-pre-wrap font-mono leading-relaxed custom-scrollbar">
                        {report.markdown}
                    </pre>
                </div>
            ) : (
                !loading && <div className="text-slate-400 text-sm">No report available.</div>
            )}

            {report && (
                <p className="text-xs text-slate-500 italic">
                    Last updated: {new Date(report.generated_at).toLocaleString()}
                </p>
            )}

            {/* GitHub Issue Section */}
            <div className="mt-6 border-t border-slate-700 pt-5">
                <h3 className="text-md font-semibold text-slate-100 flex items-center gap-2 mb-3">
                    <svg className="w-5 h-5 text-slate-400" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
                    </svg>
                    GitHub Issue Integration
                </h3>

                {githubConfigured === false ? (
                    <div className="text-sm text-slate-400">
                        GitHub integration not configured
                    </div>
                ) : githubConfigured === true ? (
                    githubIssue ? (
                        <div className="text-sm">
                            <span className="text-slate-300 mr-2">Issue created:</span>
                            <a
                                href={githubIssue.issue_url}
                                target="_blank"
                                rel="noreferrer"
                                className="text-indigo-400 hover:text-indigo-300 transition underline font-medium"
                            >
                                #{githubIssue.issue_number}
                            </a>
                        </div>
                    ) : report ? (
                        <div className="space-y-3">
                            <button
                                onClick={handleCreateIssue}
                                disabled={creatingIssue}
                                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium rounded shadow transition flex items-center gap-2"
                            >
                                {creatingIssue ? "Creating Issue..." : "Create GitHub Issue"}
                            </button>
                            {issueError && (
                                <div className="text-rose-400 text-sm mt-2">
                                    {issueError}
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="text-sm text-slate-400">
                            Run RCA to generate a report before creating an issue.
                        </div>
                    )
                ) : (
                    <div className="text-sm text-slate-500 italic">Checking GitHub configuration...</div>
                )}
            </div>
        </div>
    );
}
