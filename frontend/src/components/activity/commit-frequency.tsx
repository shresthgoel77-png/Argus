import * as React from "react";
import type { RepositoryContributions } from "@/lib/types/repository-contributions";
import { contributionDate } from "./contribution-presentation";

export function CommitFrequency({ data }: { data?: RepositoryContributions }) {
    const id = React.useId();
    const buckets = data?.frequency ?? [];
    const available = !!data?.metrics && buckets.length > 0;
    const total = buckets.reduce((sum, bucket) => sum + bucket.commits, 0);
    const peak = Math.max(0, ...buckets.map((bucket) => bucket.commits));
    const partial = data && !data.history_complete;
    return <section aria-labelledby={`${id}-heading`} className="min-w-0 space-y-3 rounded-lg border p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h4 id={`${id}-heading`} className="text-sm font-semibold">Commit frequency</h4>
            {available && <p className="text-xs text-muted-foreground">Daily · UTC · peak {peak}/day</p>}
        </div>
        {!available ? <p className="text-sm text-muted-foreground">Commit frequency unavailable.</p> : <>
            <p className="text-sm text-muted-foreground">{total} {partial ? "retrieved " : ""}{total === 1 ? "commit" : "commits"} across {buckets.length} UTC dates.</p>
            <div className="rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" role="region" aria-label="Daily commit frequency chart" tabIndex={0}>
                <svg viewBox="0 0 720 160" className="h-40 w-full" role="img" aria-labelledby={`${id}-title`} aria-describedby={`${id}-description`} preserveAspectRatio="none">
                    <title id={`${id}-title`}>{total} {partial ? "retrieved " : ""}commits; daily peak {peak}</title>
                    <desc id={`${id}-description`}>Daily commit counts from {data.scope.start_date} through {data.scope.end_date}, UTC. {partial ? "Partial history: zero buckets are not confirmed zero days." : "Complete history for this window."} Exact values are in Daily commit counts below.</desc>
                    {[10, 75, 140].map((y) => <line key={y} x1="8" x2="712" y1={y} y2={y} stroke="hsl(var(--border))" strokeDasharray="3 4" />)}
                    {buckets.map((bucket, index) => {
                        const step = 704 / buckets.length;
                        const height = peak ? bucket.commits / peak * 130 : 0;
                        return <rect key={bucket.date} x={8 + index * step + 1} y={140 - height} width={Math.max(1, step - 2)} height={height} rx="1" fill="hsl(var(--accent))">
                            <title>{contributionDate(bucket.date)}: {bucket.commits} {partial ? "retrieved " : ""}commits</title>
                        </rect>;
                    })}
                </svg>
            </div>
            <div className="flex justify-between gap-3 text-xs text-muted-foreground"><span>{contributionDate(data.scope.start_date)}</span><span>{contributionDate(data.scope.end_date)}</span></div>
            {partial && <p className="text-xs text-muted-foreground">Counts cover retrieved commits only. Zero buckets may have uncovered activity.</p>}
            <details className="text-xs">
                <summary className="cursor-pointer rounded-sm text-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">Daily commit counts</summary>
                <div className="mt-2 max-h-60 overflow-auto rounded-md border p-3" tabIndex={0} role="region" aria-label="Daily commit counts table">
                    <table className="w-full text-left tabular-nums"><caption className="pb-2 text-left text-muted-foreground">{partial ? "Retrieved subset" : "Window"} counts · UTC · total {total}</caption>
                        <thead><tr><th scope="col" className="pb-2">Date</th><th scope="col" className="pb-2 text-right">Commits</th></tr></thead>
                        <tbody>{buckets.map((bucket) => <tr key={bucket.date}><th scope="row" className="py-1 font-normal">{bucket.date}</th><td className="text-right">{bucket.commits}</td></tr>)}</tbody>
                    </table>
                </div>
            </details>
        </>}
    </section>;
}
