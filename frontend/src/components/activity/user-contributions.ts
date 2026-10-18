import { getClerkAuthorizationHeaders } from "@/lib/auth/clerk-token";

export interface ContributionDay { date: string; count: number; level: number }
export interface UserContributions {
    status: "available" | "unavailable"; year: number; as_of_date: string;
    reason?: string; login?: string; github_user_id?: string; access_context?: string;
    total: number | null; days: ContributionDay[];
}
export const utcDate = (value: Date) => value.toISOString().slice(0, 10);
const timestamp = (day: string) => Date.parse(`${day}T00:00:00Z`);
export function validDate(day: unknown): day is string {
    return typeof day === "string" && /^\d{4}-\d{2}-\d{2}$/.test(day)
        && Number.isFinite(timestamp(day)) && utcDate(new Date(timestamp(day))) === day;
}
export function unavailableContributions(year: number, reason = "calendar_access_failed"): UserContributions {
    return { status: "unavailable", year, reason, as_of_date: utcDate(new Date()), total: null, days: [] };
}
export function parseContributions(value: unknown, year: number): UserContributions {
    if (!value || typeof value !== "object") return unavailableContributions(year);
    const data = value as UserContributions;
    if (data.year !== year || !validDate(data.as_of_date)) return unavailableContributions(year);
    if (data.status === "unavailable") {
        const reason = ["identity_unavailable", "user_access_unavailable", "identity_check_failed", "calendar_access_failed"].includes(data.reason ?? "") ? data.reason : "calendar_access_failed";
        return { ...unavailableContributions(year, reason), as_of_date: data.as_of_date };
    }
    if (data.status !== "available" || typeof data.login !== "string" || !/^[A-Za-z0-9-]{1,39}$/.test(data.login)
        || typeof data.github_user_id !== "string" || !/^\d+$/.test(data.github_user_id)
        || typeof data.access_context !== "string" || !/^[a-f0-9]{64}$/.test(data.access_context) || !Array.isArray(data.days)
        || !Number.isSafeInteger(data.total) || data.total! < 0) return unavailableContributions(year);
    const dates = new Set<string>();
    for (const day of data.days) {
        if (!day || typeof day !== "object" || !validDate(day.date) || !day.date.startsWith(`${year}-`) || day.date > data.as_of_date || dates.has(day.date)
            || !Number.isSafeInteger(day.count) || day.count < 0 || !Number.isInteger(day.level)
            || day.level < 0 || day.level > 4 || (day.count === 0) !== (day.level === 0)) return unavailableContributions(year);
        dates.add(day.date);
    }
    if (data.days.reduce((sum, day) => sum + day.count, 0) !== data.total) return unavailableContributions(year);
    return data;
}
export async function fetchUserContributions(year: number): Promise<UserContributions> {
    try {
        const headers = await getClerkAuthorizationHeaders();
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/github/contributions?year=${year}`, {
            headers, credentials: "include", cache: "no-store",
        });
        return response.ok ? parseContributions(await response.json(), year) : unavailableContributions(year);
    } catch { return unavailableContributions(year); }
}

export type CalendarCell = { date: string; state: "padding" | "future" | "missing" | "covered"; count?: number; level?: number };
export function calendarCells(year: number, data?: UserContributions): CalendarCell[] {
    const first = Date.UTC(year, 0, 1), last = Date.UTC(year, 11, 31);
    const start = first - new Date(first).getUTCDay() * 86400000;
    const columns = Math.ceil(((last - start) / 86400000 + 1) / 7);
    const days = new Map(data?.status === "available" ? data.days.map((day) => [day.date, day]) : []);
    const today = data?.as_of_date ?? utcDate(new Date());
    return Array.from({ length: columns * 7 }, (_, index) => {
        const time = start + index * 86400000, date = utcDate(new Date(time)), day = days.get(date);
        return { date, state: time < first || time > last ? "padding" : date > today ? "future" : day ? "covered" : "missing",
            count: day?.count, level: day?.level };
    });
}
export function currentStreak(data: UserContributions, selectedYear: number, today = utcDate(new Date())): { days: number; through: string } | null {
    // Snapshot must cover today. Historical year views never describe a streak as current.
    if (data.status !== "available" || selectedYear !== Number(today.slice(0, 4)) || data.as_of_date !== today) return null;
    const counts = new Map(data.days.map((day) => [day.date, day.count]));
    const todayCount = counts.get(today);
    if (todayCount === undefined) return null;
    let cursor = timestamp(today);
    if (todayCount === 0) cursor -= 86400000; // Allow the current UTC day to remain in progress.
    const through = utcDate(new Date(cursor));
    let days = 0;
    for (;;) {
        const date = utcDate(new Date(cursor)), count = counts.get(date);
        if (count === undefined) return null; // Includes a streak crossing an uncovered Jan 1 boundary.
        if (count === 0) return { days, through };
        days++; cursor -= 86400000;
    }
}
export function cellLabel(cell: CalendarCell) {
    const date = new Date(timestamp(cell.date)).toLocaleDateString("en-US", { timeZone: "UTC", month: "long", day: "numeric", year: "numeric" });
    return cell.state === "covered" ? `${cell.count} ${cell.count === 1 ? "contribution" : "contributions"} on ${date}`
        : cell.state === "future" ? `${date}: future date` : `${date}: contribution data missing`;
}
