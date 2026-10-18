import { Code2 } from "lucide-react";
import type { Repository } from "@/lib/types/github";
import { primaryLanguageDistribution, type ActivityMetadata, type LanguageSegment } from "./activity-metadata";

export function LanguageBar({ rows, label }: { rows: LanguageSegment[]; label: string }) {
    return <span role="img" aria-label={label} className="flex h-2 w-full overflow-hidden rounded-full bg-muted">
        {rows.map((row) => <span key={row.key} aria-hidden="true" style={{ width: `${row.percentage}%`, backgroundColor: row.color }} title={`${row.label}: ${row.percentage.toFixed(1)}%`} />)}
    </span>;
}

export function LanguageDot({ color }: { color: string }) {
    return <span aria-hidden="true" className="inline-block size-2.5 shrink-0 rounded-full" style={{ backgroundColor: color }} />;
}

export function LanguageFootprint({ repositories, metadata, loading, error }: {
    repositories: Repository[]; metadata: Record<string, ActivityMetadata | undefined>; loading: boolean; error: boolean;
}) {
    const { total, known, rows } = primaryLanguageDistribution(repositories, metadata);
    const pending = repositories.some((repository) => !metadata[repository.id]);
    return <section className="min-h-48 min-w-0 space-y-4 rounded-xl border bg-card p-5 shadow-soft" aria-labelledby="language-footprint-title">
        <div className="flex items-center gap-2"><Code2 className="size-4 text-accent" aria-hidden="true" /><h2 id="language-footprint-title" className="font-semibold">Language footprint</h2></div>
        {loading ? <p role="status" className="text-sm text-muted-foreground">Loading connected repository count…</p>
            : error ? <p role="status" className="text-sm text-muted-foreground">Repository count and language coverage unavailable.</p>
                : <>
                    <p className="text-sm font-medium">{total} connected {total === 1 ? "repository" : "repositories"}</p>
                    <p className="text-xs text-muted-foreground">Primary language · each repository counts once</p>
                    {total === 0 ? <p className="text-sm text-muted-foreground">Connect a repository to see its primary language.</p> : <>
                        <p role="status" className="text-xs text-muted-foreground">{known === total ? `Complete primary-language coverage: ${known}/${total}.` : `Partial coverage: ${known}/${total} repositories confirmed.${pending ? " Loading metadata…" : " Unknown metadata can be retried with Refresh repositories."}`}</p>
                        <LanguageBar rows={rows} label={`Primary-language distribution across ${total} connected repositories`} />
                        <ul className="space-y-2 text-xs" aria-label="Primary languages">
                            {rows.map((row) => <li key={row.key} className="flex min-w-0 items-center justify-between gap-3">
                                <span className="flex min-w-0 items-center gap-2"><LanguageDot color={row.color} /><span className="break-words">{row.label}</span></span>
                                <span className="shrink-0 tabular-nums">{row.count} {row.count === 1 ? "repo" : "repos"} · {row.percentage.toFixed(1)}%</span>
                            </li>)}
                        </ul>
                        <p className="text-xs text-muted-foreground">Percentages use all {total} connected repositories, including confirmed no-language and unknown metadata.</p>
                    </>}
                </>}
    </section>;
}
