import * as React from "react";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ActivityRepositoryCard } from "@/components/activity/activity-repository-card";
import { LanguageFootprint } from "@/components/activity/language-footprint";
import { useActivityMetadata } from "@/components/activity/use-activity-metadata";
import { byteLanguageDistribution, createActivityMetadataLoader, fetchActivityMetadata, languageColor, parseActivityMetadata, primaryLanguageDistribution, unavailableMetadata, type ActivityMetadata } from "@/components/activity/activity-metadata";
import { getClerkAuthorizationHeaders } from "@/lib/auth/clerk-token";
import type { Repository } from "@/lib/types/github";

vi.mock("@/lib/auth/clerk-token", () => ({ getClerkAuthorizationHeaders: vi.fn() }));
const repo = (id: string) => ({ id, full_name: `owner/${id}`, default_branch: "main", private: false, monitoring_enabled: true, created_at: "2026-01-01" }) as Repository;
const metadata = (id: string, language: string | null = "TypeScript"): ActivityMetadata => ({ ...unavailableMetadata(id), metadata_status: "available", primary_language_status: language === null ? "none" : "known", primary_language: language, description: "Description from GitHub", topics: ["testing", "github"], stars: 0, forks: 3, open_issues_and_pull_requests: 7, updated_at: "2026-10-18T00:00:00Z", languages_status: "available", language_bytes: { TypeScript: 900, CSS: 100 }, fetched_at: "2026-10-18T00:00:00Z" });

beforeEach(() => { vi.resetAllMocks(); vi.mocked(getClerkAuthorizationHeaders).mockResolvedValue({ Authorization: "Bearer test-clerk-session" }); });
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it("counts every unique connected repository once and keeps unknown and confirmed no-language in the same denominator", () => {
    const repositories = [repo("a"), repo("b"), repo("c"), repo("d"), repo("e"), repo("a")];
    const values = { a: metadata("a"), b: metadata("b"), c: metadata("c", "Python"), d: metadata("d", null), e: unavailableMetadata("e") };
    const result = primaryLanguageDistribution(repositories, values);
    expect(result.total).toBe(5); expect(result.known).toBe(4);
    expect(result.rows.map(({ label, count, percentage }) => ({ label, count, percentage }))).toEqual([
        { label: "TypeScript", count: 2, percentage: 40 }, { label: "No primary language", count: 1, percentage: 20 },
        { label: "Python", count: 1, percentage: 20 }, { label: "Unknown", count: 1, percentage: 20 },
    ]);
    expect(result.rows.reduce((sum, row) => sum + row.percentage, 0)).toBe(100);
    render(<LanguageFootprint repositories={repositories} metadata={values} loading={false} error={false} />);
    expect(screen.getByText("5 connected repositories")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Partial coverage: 4/5");
    const row = screen.getByText("TypeScript").closest("li")!;
    expect(row).toHaveTextContent("2 repos · 40.0%");
    expect(row.querySelector('[aria-hidden="true"]')).toHaveStyle({ backgroundColor: languageColor("TypeScript") });
    const bar = screen.getByRole("img", { name: /Primary-language distribution/ });
    expect(bar.children[0]).toHaveStyle({ width: "40%", backgroundColor: languageColor("TypeScript") });
});

it("does not reinterpret failed, missing, or malformed metadata as no language or zero counters", () => {
    const missing = parseActivityMetadata({ repository_id: "a", metadata_status: "available", stars: -1, forks: true, open_issues_and_pull_requests: "3" }, "a");
    expect(missing.primary_language_status).toBe("unknown");
    expect(missing.stars).toBeNull(); expect(missing.forks).toBeNull(); expect(missing.open_issues_and_pull_requests).toBeNull();
    expect(parseActivityMetadata({ ...metadata("a"), repository_id: "another" }, "a")).toEqual(unavailableMetadata("a"));
    expect(parseActivityMetadata({ ...metadata("a"), language_bytes: { TypeScript: -1 } }, "a").languages_status).toBe("unavailable");
    render(<LanguageFootprint repositories={[repo("a"), repo("b")]} metadata={{ a: missing }} loading={false} error={false} />);
    expect(screen.getByRole("status")).toHaveTextContent("Partial coverage: 0/2");
    expect(screen.getByText("Unknown").closest("li")).toHaveTextContent("2 repos · 100.0%");
    expect(screen.queryByText("No primary language")).not.toBeInTheDocument();
});

it("renders real metadata, combined open-item counters, matching dots, and a separate byte denominator", () => {
    const item = metadata("a");
    expect(byteLanguageDistribution(item).map((row) => row.percentage)).toEqual([90, 10]);
    render(<ActivityRepositoryCard repository={repo("a")} selected metadata={item} onSelect={() => {}} />);
    const card = screen.getByRole("button", { name: "Select owner/a" });
    expect(card).toHaveTextContent("Stars: 0"); expect(card).toHaveTextContent("Forks: 3");
    expect(card).toHaveTextContent("Open issues + PRs: 7");
    expect(card).not.toHaveTextContent("Open issues: 7");
    expect(card).toHaveTextContent("Description from GitHub"); expect(card).toHaveTextContent("testing");
    expect(card).toHaveTextContent("TypeScript 90.0%"); expect(card).toHaveTextContent("CSS 10.0%");
    const bar = within(card).getByRole("img", { name: "Language bytes for owner/a" });
    expect(bar.children[0]).toHaveStyle({ width: "90%", backgroundColor: languageColor("TypeScript") });
    expect(card.querySelector('time[datetime="2026-10-18T00:00:00Z"]')).toBeInTheDocument();
});

it("renders no-language, unavailable metadata, genuinely empty collections, and discovery failure honestly", () => {
    const view = render(<ActivityRepositoryCard repository={repo("a")} selected={false} metadata={{ ...metadata("a", null), language_bytes: {} }} onSelect={() => {}} />);
    expect(screen.getByText("No primary language")).toBeInTheDocument();
    expect(screen.getByText("No language bytes reported")).toBeInTheDocument();
    view.rerender(<ActivityRepositoryCard repository={repo("a")} selected={false} metadata={unavailableMetadata("a")} onSelect={() => {}} />);
    expect(screen.getByText("Primary language unknown")).toBeInTheDocument();
    expect(screen.getByText("Stars: unavailable")).toBeInTheDocument();
    view.rerender(<LanguageFootprint repositories={[]} metadata={{}} loading={false} error={false} />);
    expect(screen.getByText("0 connected repositories")).toBeInTheDocument(); expect(screen.queryByRole("img")).not.toBeInTheDocument();
    view.rerender(<LanguageFootprint repositories={[]} metadata={{}} loading={false} error />);
    expect(screen.queryByText("0 connected repositories")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Repository count and language coverage unavailable");
});

it("uses Clerk authorization only for the local metadata endpoint and does not request issue/PR lists", async () => {
    const request = vi.fn().mockResolvedValue({ ok: true, json: async () => metadata("a") });
    vi.stubGlobal("fetch", request);
    expect((await fetchActivityMetadata(repo("a"))).stars).toBe(0);
    expect(request).toHaveBeenCalledExactlyOnceWith(expect.stringMatching(/\/api\/v1\/repositories\/a\/activity-metadata$/), {
        headers: { Authorization: "Bearer test-clerk-session" }, credentials: "include", cache: "no-store",
    });
    request.mockResolvedValueOnce({ ok: false, status: 403 });
    expect((await fetchActivityMetadata(repo("b"))).primary_language_status).toBe("unknown");
});

it("deduplicates in-flight/cached reads, bounds concurrency across scopes, and keeps one failure isolated", async () => {
    const releases: (() => void)[] = [];
    let active = 0; let maximum = 0;
    const fetcher = vi.fn(async (repository: Repository) => {
        active++; maximum = Math.max(active, maximum);
        await new Promise<void>((resolve) => releases.push(resolve));
        active--;
        if (repository.id === "1") throw new Error("Permission denied");
        return metadata(repository.id);
    });
    const loader = createActivityMetadataLoader(fetcher);
    const reads = Array.from({ length: 8 }, (_, index) => loader.load(repo(String(index))));
    expect(loader.load(repo("0"))).toBe(reads[0]);
    expect(fetcher).toHaveBeenCalledTimes(4);
    releases.splice(0).forEach((release) => release());
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(8));
    releases.splice(0).forEach((release) => release());
    const results = await Promise.all(reads);
    expect(maximum).toBe(4); expect(results[1].primary_language_status).toBe("unknown"); expect(results[7].primary_language).toBe("TypeScript");
    await loader.load(repo("0")); expect(fetcher).toHaveBeenCalledTimes(8);
    loader.invalidate();
    const refresh = loader.load(repo("0")); releases.splice(0).forEach((release) => release()); await refresh;
    expect(fetcher).toHaveBeenCalledTimes(9);
});

it("does not stop at 30/100 repositories, reports loading partial coverage, and ignores obsolete hook results", async () => {
    const repositories = Array.from({ length: 105 }, (_, index) => repo(String(index)));
    let finishFirst!: () => void;
    const request = vi.fn().mockImplementation(async (url: string) => {
        const id = url.match(/repositories\/([^/]+)\/activity-metadata/)![1];
        if (id === "0") await new Promise<void>((resolve) => { finishFirst = resolve; });
        return { ok: true, json: async () => metadata(id, id === "104" ? null : "Python") };
    });
    vi.stubGlobal("fetch", request);
    function Harness({ list }: { list: Repository[] }) {
        const values = useActivityMetadata(list, 0);
        return <LanguageFootprint repositories={list} metadata={values} loading={false} error={false} />;
    }
    const view = render(<Harness list={repositories} />);
    expect(screen.getByText("105 connected repositories")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Partial coverage: 0/105");
    await waitFor(() => expect(request).toHaveBeenCalledTimes(105));
    await waitFor(() => expect(screen.getByText("No primary language")).toBeInTheDocument());
    expect(screen.getByRole("status")).toHaveTextContent("Partial coverage: 104/105");
    view.rerender(<Harness list={[repo("current")]} />);
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Complete primary-language coverage: 1/1"));
    await act(async () => finishFirst());
    expect(screen.getByText("1 connected repository")).toBeInTheDocument();
    expect(screen.queryByText("No primary language")).not.toBeInTheDocument();
});
