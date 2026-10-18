"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { createFindingIssue, previewFindingIssue, type FindingIssuePreview, type GitHubWorkItem } from "@/lib/api/repository-work-items";

export function FindingIssuePreviewPanel({ findingId, triggerLabel = "Generate issue preview", actions }: { findingId: string; triggerLabel?: string; actions?: React.ReactNode }) {
    const [preview, setPreview] = React.useState<FindingIssuePreview | null>(null);
    const [created, setCreated] = React.useState<GitHubWorkItem | null>(null);
    const [pending, setPending] = React.useState(false);
    const [error, setError] = React.useState<string | null>(null);
    const [approved, setApproved] = React.useState(false);

    async function generate() {
        setPending(true); setError(null); setApproved(false); setPreview(null);
        try { setPreview(await previewFindingIssue(findingId)); }
        catch (e) { setError(e instanceof Error ? e.message : "The issue preview could not be generated."); }
        finally { setPending(false); }
    }
    async function publish() {
        if (!preview || !approved || pending) return;
        setPending(true); setError(null);
        try { setCreated(await createFindingIssue(findingId, preview.preview_token)); }
        catch (e) { setError(e instanceof Error ? e.message : "GitHub did not confirm issue creation."); }
        finally { setPending(false); setApproved(false); }
    }
    return <section className="space-y-3 rounded-md border p-4" aria-label="GitHub issue from finding">
        <h4 className="text-sm font-semibold">GitHub issue</h4>
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        {created ? <a className="text-sm text-primary underline" href={created.html_url} target="_blank" rel="noreferrer">View issue #{created.number} on GitHub</a> : <>
            <div className="flex flex-wrap gap-2">
                <Button variant="outline" onClick={generate} disabled={pending} className="h-auto min-h-10 whitespace-normal">{pending ? "Working..." : triggerLabel}</Button>
                {actions}
            </div>
            {preview && <>
                <p className="text-sm">Repository: <strong>{preview.repository}</strong></p>
                <p className="font-medium">{preview.title}</p>
                <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-md bg-muted p-3 text-xs">{preview.body}</pre>
                <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={approved} disabled={pending} onChange={event => setApproved(event.target.checked)} />I approve creating this issue with the exact title and body above on GitHub.</label>
                <Button onClick={publish} disabled={!approved || pending} className="h-auto min-h-10 whitespace-normal">Create approved issue on GitHub</Button>
            </>}
        </>}
    </section>;
}
