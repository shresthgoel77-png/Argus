import { NextResponse, type NextFetchEvent, type NextRequest } from "next/server";

const isClerkEnabled =
    typeof process !== "undefined" &&
    typeof process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY === "string" &&
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY.length > 0;

export default async function middleware(request: NextRequest, event: NextFetchEvent) {
    if (!isClerkEnabled) {
        throw new Error(
            "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY is required; authentication cannot be bypassed.",
        );
    }

    // Dynamically import Clerk after validating its required configuration.
    const { clerkMiddleware } = await import(
        "@clerk/nextjs/server"
    );

    const handler = clerkMiddleware(async (auth, req) => {
        // Resource auth lives in server pages and the backend API. Keep only
        // the existing signed-in landing-page redirect here.
        if (req.nextUrl.pathname === "/") {
            const { userId } = await auth();
            if (userId) {
                return NextResponse.redirect(new URL("/dashboard", req.url));
            }
        }
    });

    return handler(request, event);
}

export const config = {
    matcher: [
        "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
        "/(api|trpc)(.*)",
    ],
};
