"use client";

import * as React from "react";
import { CalendarDays } from "lucide-react";
import { Button } from "@/components/ui/button";
import { calendarCells, cellLabel, currentStreak, utcDate, type UserContributions } from "./user-contributions";
import { useUserContributions } from "./use-user-contributions";

const colors = ["#ebedf0", "#b9e4c9", "#78c99a", "#3b9d68", "#216e45"];
const reasons: Record<string, string> = {
    identity_unavailable: "A verified linked GitHub user is not available for this account. Your personal calendar cannot be read.",
    user_access_unavailable: "The verified GitHub link has no matching existing user access token. Your personal calendar cannot be read with the current access.",
    identity_check_failed: "Your linked GitHub identity could not be verified right now. Try again.",
    calendar_access_failed: "GitHub could not return a verified personal calendar with the existing access. Try again.",
};

export function ContributionCalendar({ year, data }: { year: number; data?: UserContributions }) {
    const cells = calendarCells(year, data), columns = cells.length / 7;
    const firstDay = cells.findIndex((cell) => cell.state !== "padding");
    const [focusedDate, setFocusedDate] = React.useState("");
    const [tooltip, setTooltip] = React.useState("");
    const tooltipId = React.useId();
    const buttons = React.useRef(new Map<string, HTMLButtonElement>());
    const focusDate = cells.some((cell) => cell.date === focusedDate && cell.state !== "padding") ? focusedDate : cells[firstDay].date;
    const months = Array.from({ length: 12 }, (_, month) => {
        const date = `${year}-${String(month + 1).padStart(2, "0")}-01`;
        return { label: new Date(`${date}T00:00:00Z`).toLocaleString("en-US", { month: "short", timeZone: "UTC" }), column: Math.floor(cells.findIndex((cell) => cell.date === date) / 7) + 2 };
    });
    function move(event: React.KeyboardEvent, index: number) {
        const offset = { ArrowRight: 7, ArrowLeft: -7, ArrowDown: 1, ArrowUp: -1 }[event.key];
        if (offset === undefined) return;
        event.preventDefault();
        const target = cells[Math.max(firstDay, Math.min(cells.findLastIndex((cell) => cell.state !== "padding"), index + offset))];
        setFocusedDate(target.date);
        buttons.current.get(target.date)?.focus();
    }
    return <>
        <div role="region" aria-label={`Contribution calendar for ${year}; scroll to view all weeks`} tabIndex={0} className="max-w-full overflow-x-auto pb-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <div role="group" aria-label={`${columns} weeks, seven weekday rows, Sunday through Saturday`} className="grid min-w-[650px] gap-x-0.5 gap-y-1 text-[10px] text-muted-foreground" style={{ gridTemplateColumns: `28px repeat(${columns}, minmax(9px, 1fr))`, gridTemplateRows: "18px repeat(7, 11px)" }}>
                {months.map((month) => <span key={month.label} aria-hidden="true" style={{ gridColumn: `${month.column} / span 3`, gridRow: 1 }}>{month.label}</span>)}
                {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((label, index) => <span key={label} aria-hidden="true" style={{ gridColumn: 1, gridRow: index + 2 }}>{[1, 3, 5].includes(index) ? label : ""}</span>)}
                {cells.map((cell, index) => cell.state === "padding" ? <span key={cell.date} data-state="padding" aria-hidden="true" style={{ gridColumn: Math.floor(index / 7) + 2, gridRow: index % 7 + 2 }} /> : <button key={cell.date} type="button"
                    ref={(element) => { if (element) buttons.current.set(cell.date, element); else buttons.current.delete(cell.date); }}
                    tabIndex={cell.date === focusDate ? 0 : -1} aria-label={cellLabel(cell)} aria-describedby={tooltip === cell.date ? tooltipId : undefined}
                    data-state={cell.state} data-date={cell.date}
                    className="min-w-0 rounded-[2px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1"
                    style={{ gridColumn: Math.floor(index / 7) + 2, gridRow: index % 7 + 2,
                        backgroundColor: cell.state === "covered" ? colors[cell.level!] : "transparent",
                        border: cell.state === "missing" ? "1px dashed #94a3b8" : cell.state === "future" ? "1px solid #e2e8f0" : undefined }}
                    onFocus={() => { setFocusedDate(cell.date); setTooltip(cell.date); }} onBlur={() => setTooltip("")}
                    onMouseEnter={() => setTooltip(cell.date)} onMouseLeave={() => setTooltip(document.activeElement instanceof HTMLElement ? document.activeElement.dataset.date ?? "" : "")} onKeyDown={(event) => move(event, index)} />)}
            </div>
        </div>
        <div className="min-h-5 text-xs text-muted-foreground">{tooltip ? <span role="tooltip" id={tooltipId}>{cellLabel(cells.find((cell) => cell.date === tooltip)!)}</span> : "Focus or hover a date for details. Use arrow keys to move between dates."}</div>
        <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground">
            <span>Dashed: missing · Outline: future · Blank: outside year</span>
            <span className="inline-flex items-center gap-1.5" aria-label="Contribution intensity: Less to More"><span>Less</span>{colors.map((color, index) => <span key={color} aria-hidden="true" className="size-2.5 rounded-[2px]" style={{ backgroundColor: color }} title={index === 0 ? "Zero contributions" : `Intensity ${index} of 4`} />)}<span>More</span></span>
        </div>
    </>;
}

export function ContributionHeatmap() {
    const today = utcDate(new Date()), currentYear = Number(today.slice(0, 4));
    const [year, setYear] = React.useState(currentYear);
    const [revision, setRevision] = React.useState(0);
    const data = useUserContributions(year, revision);
    const cells = calendarCells(year, data);
    const complete = data?.status === "available" && !cells.some((cell) => cell.state === "missing");
    const streak = data ? currentStreak(data, year, today) : null;
    return <section className="min-w-0 space-y-4 rounded-xl border bg-card p-5 shadow-soft" aria-labelledby="contribution-heatmap-title" aria-busy={!data}>
        <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2"><CalendarDays className="size-4 text-accent" aria-hidden="true" /><h2 id="contribution-heatmap-title" className="font-semibold">Your contribution heatmap</h2></div>
            <label className="flex items-center gap-2 text-xs text-muted-foreground">Calendar year<select aria-label="Calendar year" value={year} onChange={(event) => setYear(Number(event.target.value))} className="rounded-md border bg-background px-2 py-1.5 text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                {Array.from({ length: currentYear - 2007 }, (_, index) => currentYear - index).map((value) => <option key={value} value={value}>{value}</option>)}
            </select></label>
        </div>
        <h3 className="text-sm font-medium">{!data ? `Loading contributions in ${year}…` : data.status !== "available" ? `Contributions unavailable in ${year}` : `${data.total!.toLocaleString()}${complete ? "" : " reported"} contributions in ${year}`}</h3>
        {!data ? <p role="status" className="text-xs text-muted-foreground">Verifying personal GitHub calendar access…</p> : data.status === "unavailable" ? <div className="space-y-2"><p role="status" className="text-sm text-muted-foreground">{reasons[data.reason ?? ""] ?? reasons.calendar_access_failed}</p><Button variant="outline" size="sm" onClick={() => setRevision((value) => value + 1)}>Retry calendar</Button></div> : <p role="status" className="text-xs text-muted-foreground">{complete ? "Complete date coverage" : "Partial date coverage; missing dates are not zero"} through {data.as_of_date < `${year}-12-31` ? data.as_of_date : `${year}-12-31`} · @{data.login} · GitHub-visible contributions. Private visibility depends on existing access and GitHub settings.</p>}
        <ContributionCalendar key={year} year={year} data={data} />
        {year !== currentYear ? <p className="text-xs text-muted-foreground">Historical year · current streak is not shown.</p> : <p className="text-xs text-muted-foreground">{streak ? `Current streak: ${streak.days} ${streak.days === 1 ? "day" : "days"} · through ${streak.through}` : "Current streak unavailable: today or a preceding streak boundary is not covered."}</p>}
        <p className="text-xs text-muted-foreground">Dates follow GitHub’s daily buckets; today uses UTC. A zero today allows a streak through yesterday. A streak continuing before January 1 is unavailable until earlier coverage exists.</p>
    </section>;
}
