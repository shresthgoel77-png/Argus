import type { Metadata } from "next";
import "./globals.css";
import { geistMono, geistSans } from "./fonts";

export const metadata: Metadata = {
  title: "RepoMedic",
  description: "Engineering intelligence platform",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
