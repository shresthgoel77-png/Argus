import { afterEach, describe, expect, it } from "vitest";
import {
    clearClerkTokenGetter,
    getClerkAuthorizationHeaders,
    setClerkTokenGetter,
} from "../../lib/auth/clerk-token";

afterEach(() => {
    setClerkTokenGetter(null);
});

describe("Clerk API authorization", () => {
    it("uses the active Clerk session token as a bearer header", async () => {
        const getToken = async () => "session-token";
        setClerkTokenGetter(getToken);

        await expect(getClerkAuthorizationHeaders()).resolves.toEqual({
            Authorization: "Bearer session-token",
        });
    });

    it("does not retain a token getter after its provider is cleared", async () => {
        const getToken = async () => "stale-token";
        setClerkTokenGetter(getToken);
        clearClerkTokenGetter(getToken);

        const headersPromise = getClerkAuthorizationHeaders();
        setClerkTokenGetter(async () => "fresh-token");
        await expect(headersPromise).resolves.toEqual({
            Authorization: "Bearer fresh-token",
        });
    });

    it("omits the bearer header when the Clerk session is signed out", async () => {
        setClerkTokenGetter(async () => null);

        await expect(getClerkAuthorizationHeaders()).resolves.toEqual({});
    });
});
