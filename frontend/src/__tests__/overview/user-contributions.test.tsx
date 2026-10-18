import * as React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ContributionCalendar, ContributionHeatmap } from "@/components/activity/contribution-heatmap";
import { useUserContributions } from "@/components/activity/use-user-contributions";
import { calendarCells, currentStreak, fetchUserContributions, parseContributions, unavailableContributions, utcDate, type UserContributions } from "@/components/activity/user-contributions";
import { getClerkAuthorizationHeaders } from "@/lib/auth/clerk-token";

let userId = "person-a";
vi.mock("@/lib/auth/use-auth", () => ({ useAuth: () => ({ isAuthenticated: true, user: { id: userId } }) }));
vi.mock("@/lib/auth/clerk-token", () => ({ getClerkAuthorizationHeaders: vi.fn() }));

function calendar(year: number, today = `${year}-12-31`): UserContributions {
    const days = [];
    for (let day = Date.UTC(year, 0, 1); utcDate(new Date(day)) <= today && new Date(day).getUTCFullYear() === year; day += 86400000) {
        const date = utcDate(new Date(day));
        days.push({ date, count: date === "2024-02-29" ? 3 : 0, level: date === "2024-02-29" ? 2 : 0 });
    }
    return { status: "available", year, as_of_date: today, days, total: days.reduce((sum, day) => sum + day.count, 0), login: "verified-person", github_user_id: "42", access_context: "a".repeat(64) };
}
beforeEach(() => { vi.resetAllMocks(); userId = "person-a"; vi.mocked(getClerkAuthorizationHeaders).mockResolvedValue({ Authorization: "Bearer fixture-session" }); });
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it("aligns exact calendar years to Sunday columns, includes leap days, and allocates a required 54th week", () => {
    const leap = calendarCells(2024, calendar(2024));
    expect(leap).toHaveLength(53 * 7);
    expect(leap.filter((day) => day.state !== "padding")).toHaveLength(366);
    expect(leap.findIndex((day) => day.date === "2024-01-01") % 7).toBe(1);
    expect(leap.find((day) => day.date === "2024-02-29")).toMatchObject({ state: "covered", count: 3 });
    expect(calendarCells(2025, calendar(2025)).filter((day) => day.state !== "padding")).toHaveLength(365);
    expect(calendarCells(2028, calendar(2028))).toHaveLength(54 * 7); // Leap year starting Saturday.
    const thursday = calendarCells(2026, calendar(2026));
    expect(thursday.findIndex((day) => day.date === "2026-01-01") % 7).toBe(4);
    expect(thursday.filter((day) => day.state !== "padding").at(-1)?.date).toBe("2026-12-31");
});

it("keeps zero, missing, future, and padding separate; never turns an unavailable year into zero", () => {
    const data = calendar(2024, "2024-03-01");
    data.days = data.days.filter((day) => day.date !== "2024-02-28");
    const cells = calendarCells(2024, data);
    expect(cells[0].state).toBe("padding");
    expect(cells.find((day) => day.date === "2024-02-27")).toMatchObject({ state: "covered", count: 0 });
    expect(cells.find((day) => day.date === "2024-02-28")).toMatchObject({ state: "missing", count: undefined });
    expect(cells.find((day) => day.date === "2024-03-02")).toMatchObject({ state: "future", count: undefined });
    expect(calendarCells(2024, unavailableContributions(2024)).some((day) => day.state === "covered")).toBe(false);
});

it("only reports a current streak with a covered stopping boundary and never labels a historical streak current", () => {
    const data = calendar(2026, "2026-01-05");
    for (const date of ["2026-01-03", "2026-01-04"]) Object.assign(data.days.find((day) => day.date === date)!, { count: 1, level: 1 });
    expect(currentStreak(data, 2026, "2026-01-05")).toEqual({ days: 2, through: "2026-01-04" });
    Object.assign(data.days.at(-1)!, { count: 1, level: 1 });
    expect(currentStreak(data, 2026, "2026-01-05")).toEqual({ days: 3, through: "2026-01-05" });
    data.days = data.days.filter((day) => day.date !== "2026-01-02");
    expect(currentStreak(data, 2026, "2026-01-05")).toBeNull();
    expect(currentStreak(calendar(2024), 2024, "2026-01-05")).toBeNull();
    expect(currentStreak(calendar(2026, "2026-01-04"), 2026, "2026-01-05")).toBeNull();
    const january = calendar(2026, "2026-01-01");
    january.days[0] = { date: "2026-01-01", count: 2, level: 1 };
    expect(currentStreak(january, 2026, "2026-01-01")).toBeNull(); // Prior year is unknown, not a reset.
});

it("validates dates, totals, duplicate days, identity/access markers, and genuine zero data", () => {
    const data = calendar(2024);
    expect(parseContributions(data, 2024).total).toBe(3);
    for (const bad of [{ ...data, year: 2023 }, { ...data, total: 100 }, { ...data, github_user_id: undefined },
        { ...data, days: [...data.days, data.days[0]] }, { ...data, days: [{ date: "2024-02-30", count: 0, level: 0 }] }]) {
        expect(parseContributions(bad, 2024).status).toBe("unavailable");
    }
    expect(parseContributions(calendar(2025), 2025).total).toBe(0);
    expect(parseContributions({ ...unavailableContributions(2024), reason: "constructor" }, 2024).reason).toBe("calendar_access_failed");
});

it("renders seven rows, month/day labels, count/date tooltips, roving keyboard focus, and the light legend", () => {
    const { container } = render(<ContributionCalendar year={2024} data={calendar(2024)} />);
    expect(screen.getByRole("group", { name: /53 weeks, seven weekday rows/ })).toBeInTheDocument();
    for (const text of ["Mon", "Wed", "Fri", "Jan", "Dec", "Less", "More"]) expect(screen.getByText(text)).toBeInTheDocument();
    const leap = screen.getByRole("button", { name: "3 contributions on February 29, 2024" });
    fireEvent.focus(leap);
    expect(screen.getByRole("tooltip")).toHaveTextContent("3 contributions on February 29, 2024");
    expect(leap).toHaveAttribute("aria-describedby", screen.getByRole("tooltip").id);
    fireEvent.keyDown(leap, { key: "ArrowRight" });
    expect(document.activeElement).toHaveAttribute("data-date", "2024-03-07");
    expect(container.querySelectorAll('button[tabindex="0"]')).toHaveLength(1);
    expect(container.querySelectorAll('[data-state="padding"]')).toHaveLength(5);
});

it("loads the personal read with Clerk authorization, and preserves unavailable access rather than zero", async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => calendar(2024) });
    vi.stubGlobal("fetch", fetcher);
    expect((await fetchUserContributions(2024)).total).toBe(3);
    expect(fetcher).toHaveBeenCalledExactlyOnceWith(expect.stringMatching(/\/api\/v1\/github\/contributions\?year=2024$/), {
        headers: { Authorization: "Bearer fixture-session" }, credentials: "include", cache: "no-store",
    });
    fetcher.mockResolvedValue({ ok: false, status: 403 });
    expect(await fetchUserContributions(2024)).toMatchObject({ status: "unavailable", total: null, days: [] });
});

it("ignores stale year/account results and revalidates access when returning to a cached year", async () => {
    let release!: (value: unknown) => void;
    const request = vi.fn().mockResolvedValue({ ok: true, json: async () => calendar(2023) });
    request.mockReturnValueOnce(new Promise((resolve) => { release = resolve; }));
    vi.stubGlobal("fetch", request);
    function Harness({ year }: { year: number }) { const data = useUserContributions(year, 0); return <p>{data ? `${data.year}:${data.total}` : "loading"}</p>; }
    const view = render(<Harness year={2024} />);
    await waitFor(() => expect(request).toHaveBeenCalledTimes(1));
    view.rerender(<Harness year={2023} />);
    expect(await screen.findByText("2023:0")).toBeInTheDocument();
    await act(async () => release({ ok: true, json: async () => calendar(2024) }));
    expect(screen.queryByText("2024:3")).not.toBeInTheDocument();
    userId = "person-b";
    request.mockResolvedValue({ ok: true, json: async () => unavailableContributions(2023, "identity_unavailable") });
    view.rerender(<Harness year={2023} />);
    expect(screen.getByText("loading")).toBeInTheDocument();
    expect(await screen.findByText("2023:null")).toBeInTheDocument();
    expect(request).toHaveBeenCalledTimes(3);
    fireEvent(window, new Event("focus"));
    await waitFor(() => expect(request).toHaveBeenCalledTimes(4));
});

it("shows dynamic year headings, honest unavailability, and historical-year totals without a current streak", async () => {
    const current = new Date().getUTCFullYear();
    const request = vi.fn().mockImplementation(async (url: string) => {
        const year = Number(new URL(url).searchParams.get("year"));
        return { ok: true, json: async () => year === current ? unavailableContributions(year, "identity_unavailable") : calendar(year) };
    });
    vi.stubGlobal("fetch", request);
    render(<ContributionHeatmap />);
    expect(await screen.findByText(`Contributions unavailable in ${current}`)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("verified linked GitHub user is not available");
    const select = screen.getByLabelText("Calendar year");
    expect(select).toHaveValue(String(current));
    fireEvent.change(select, { target: { value: current - 1 } });
    expect(await screen.findByText(`0 contributions in ${current - 1}`)).toBeInTheDocument();
    expect(screen.getByText(/Historical year/)).toHaveTextContent("current streak is not shown");
    expect(screen.queryByText(/Current streak:/)).not.toBeInTheDocument();
});
