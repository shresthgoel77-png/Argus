import { SignUp } from "@clerk/nextjs";
import { isClerkEnabled } from "@/lib/auth/config";
import { redirect } from "next/navigation";

export default function SignUpPage() {
    if (!isClerkEnabled()) {
        redirect("/login");
    }

    return (
        <main className="flex min-h-screen items-center justify-center p-6 bg-muted/30">
            <SignUp />
        </main>
    );
}
