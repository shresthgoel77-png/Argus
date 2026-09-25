import { SignIn } from "@clerk/nextjs";
import { isClerkEnabled } from "@/lib/auth/config";
import { redirect } from "next/navigation";

export default function SignInPage() {
    if (!isClerkEnabled()) {
        redirect("/login");
    }

    return (
        <main className="flex min-h-screen items-center justify-center p-6 bg-muted/30">
            <SignIn />
        </main>
    );
}
