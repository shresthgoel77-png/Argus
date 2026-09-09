import type { Metadata } from "next";
import "./globals.css";
import { geistMono, geistSans } from "./fonts";
import { AuthProvider } from "@/lib/auth/auth-context";

export const metadata: Metadata = {
  title: "RepoMedic",
  description: "Engineering intelligence platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
