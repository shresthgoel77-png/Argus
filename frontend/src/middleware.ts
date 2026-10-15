import { NextResponse, type NextRequest } from "next/server";

const isClerkEnabled =
    typeof process !== "undefined" &&
    typeof process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY === "string" &&
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY.length > 0;

export default async function middleware(request: NextRequest) {
    if (!isClerkEnabled) {
        throw new Error(
            "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY is required; authentication cannot be bypassed.",
        );
    }

    // Dynamically import Clerk after validating its required configuration.
    const { clerkMiddleware, createRouteMatcher } = await import(
        "@clerk/nextjs/server"
    );

    const isPublicRoute = createRouteMatcher([
        "/",
        "/login",
        "/sign-in(.*)",
        "/sign-up(.*)",
        "/api(.*)",
    ]);

    const handler = clerkMiddleware(async (auth, req) => {
        const authObj = await auth();
        if (!isPublicRoute(req)) {
            await auth.protect();
        } else if (req.nextUrl.pathname === "/" && authObj.userId) {
            return NextResponse.redirect(new URL("/dashboard", req.url));
        }
    });

    return handler(request, {} as any);
}

export const config = {
    matcher: [
        "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
        "/(api|trpc)(.*)",
    ],
};
