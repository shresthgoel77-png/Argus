import { Check, CircleDot, GitFork, Star } from "lucide-react";
import type { Repository } from "@/lib/types/github";
import { cn } from "@/lib/utils";
import { byteLanguageDistribution, languageColor, type ActivityMetadata } from "./activity-metadata";
import { LanguageBar, LanguageDot } from "./language-footprint";

export function ActivityRepositoryCard({ repository, selected, metadata, onSelect }: {
    repository: Repository; selected: boolean; metadata?: ActivityMetadata; onSelect: () => void;
}) {
    const [owner, ...name] = repository.full_name.split("/");
    const rows = metadata ? byteLanguageDistribution(metadata) : [];
    return <button type="button" aria-label={`Select ${repository.full_name}`} aria-pressed={selected} aria-controls="repository-workspace" onClick={onSelect}
        style={selected ? { borderColor: "hsl(var(--accent))" } : undefined}
        className={cn("h-full w-full min-w-0 space-y-3 rounded-xl border bg-card p-5 text-left shadow-soft transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2", selected ? "bg-accent/5" : "hover:bg-muted/50")}>
        <span className="flex items-start justify-between gap-3">
            <span className={cn("min-w-0 break-words font-semibold [overflow-wrap:anywhere]", selected && "text-accent")}><span className="font-normal text-muted-foreground">{owner}/</span>{name.join("/")}</span>
            {selected && <Check className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden="true" />}
        </span>
        <span className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground"><span>{repository.private ? "Private" : "Public"}</span><span className="break-all">{repository.default_branch ? `Branch: ${repository.default_branch}` : "Default branch unavailable"}</span></span>
        {!metadata ? <span className="block text-xs text-muted-foreground">Loading repository metadata…</span> : <>
            <span className="line-clamp-2 text-sm text-muted-foreground [overflow-wrap:anywhere]" title={metadata.description ?? undefined}>{metadata.description || (metadata.metadata_status === "available" ? "No description provided." : "Description unavailable.")}</span>
            {metadata.topics?.length ? <span className="flex flex-wrap gap-1.5" aria-label="Repository topics">{metadata.topics.map((topic) => <span key={topic} className="max-w-full break-all rounded-full border bg-muted px-2 py-0.5 text-xs">{topic}</span>)}</span> : metadata.topics === null ? <span className="block text-xs text-muted-foreground">Topics unavailable</span> : null}
            <span className="flex items-center gap-2 text-xs"><LanguageDot color={metadata.primary_language ? languageColor(metadata.primary_language) : metadata.primary_language_status === "none" ? "#cbd5e1" : "#64748b"} />{metadata.primary_language ?? (metadata.primary_language_status === "none" ? "No primary language" : "Primary language unknown")}</span>
            <span className="flex flex-wrap gap-x-4 gap-y-2 text-xs text-muted-foreground">
                <span className="inline-flex items-center gap-1"><Star className="size-3.5" aria-hidden="true" />Stars: {metadata.stars?.toLocaleString() ?? "unavailable"}</span>
                <span className="inline-flex items-center gap-1"><GitFork className="size-3.5" aria-hidden="true" />Forks: {metadata.forks?.toLocaleString() ?? "unavailable"}</span>
                <span className="inline-flex items-center gap-1"><CircleDot className="size-3.5" aria-hidden="true" />Open issues + PRs: {metadata.open_issues_and_pull_requests?.toLocaleString() ?? "unavailable"}</span>
            </span>
            <span className="block text-xs text-muted-foreground">{metadata.updated_at ? <>Updated <time dateTime={metadata.updated_at} title={new Date(metadata.updated_at).toLocaleString()}>{new Date(metadata.updated_at).toLocaleDateString()}</time></> : "Update time unavailable"}</span>
            {metadata.languages_status === "available" ? rows.length ? <span className="block space-y-2">
                <span className="block text-xs text-muted-foreground">Code languages · by bytes</span>
                <LanguageBar rows={rows} label={`Language bytes for ${repository.full_name}`} />
                <span className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">{rows.map((row) => <span key={row.key} className="inline-flex items-center gap-1"><LanguageDot color={row.color} />{row.label} {row.percentage.toFixed(1)}%</span>)}</span>
            </span> : <span className="block text-xs text-muted-foreground">No language bytes reported</span> : <span className="block text-xs text-muted-foreground">Language bytes unavailable</span>}
            {metadata.metadata_status === "unavailable" && <span className="block text-xs text-muted-foreground">Metadata unavailable. Check GitHub access or refresh to retry.</span>}
            {metadata.fetched_at && <span className="block text-xs text-muted-foreground">Metadata checked <time dateTime={metadata.fetched_at}>{new Date(metadata.fetched_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time></span>}
        </>}
        <span className={cn("block text-xs font-medium", selected ? "text-accent" : "text-muted-foreground")}>{selected ? "Selected" : "Open workspace"}</span>
    </button>;
}
